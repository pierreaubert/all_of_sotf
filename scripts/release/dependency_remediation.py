#!/usr/bin/env python3
"""Plan remediation for strict ten-lock dependency findings.

Read-only planner layered on :mod:`dependency_graph`. It never edits
Cargo manifests or lockfiles. It computes exact reverse parents from each
lockfile's dependency edges, attributes direct manifest declarers, separates
version splits from source splits and coexisting scopes from cross-lock-only
families, groups semver-compatible versions, clusters families by shared
parent, and emits minimal lock-only convergence steps plus owner actions.

No finding is waived: every aggregate family appears in the report with an
actionable attribution or an explicit owner action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts"))
import dependency_graph as graph
from workspaces import workspace_names

NESTED_SCOPE = "autoeq-gpui-examples"
PATH_SOURCE = "path/local"
CRATES_IO = "registry+https://github.com/rust-lang/crates.io-index"
VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)

SCHEMA_VERSION = 1


def lock_scopes(root: Path, names: list[str]) -> list[tuple[str, Path]]:
    scopes = [(name, root / name / "Cargo.lock") for name in names]
    if "autoeq" in names:
        scopes.append((NESTED_SCOPE, root / "autoeq" / "crates" /
                       NESTED_SCOPE / "Cargo.lock"))
    return scopes


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_lock_dep(spec: str) -> tuple[str, str | None, str | None]:
    """Split a Cargo.lock dependency entry into name, version, source."""
    parts = spec.split(" ")
    if len(parts) == 1:
        return parts[0], None, None
    if len(parts) == 2:
        return parts[0], parts[1], None
    if len(parts) == 3 and parts[2].startswith("(") and parts[2].endswith(")"):
        return parts[0], parts[1], parts[2][1:-1]
    raise ValueError(f"unrecognized lock dependency entry: {spec!r}")


def version_key(raw: str) -> tuple[int, int, int] | None:
    match = VERSION.fullmatch(raw)
    if not match or match.group(4):
        return None
    return tuple(int(match.group(i)) for i in (1, 2, 3))  # type: ignore[return-value]


def compatibility(raw: str) -> tuple[int, ...] | None:
    """Cargo semver compatibility group; None for prerelease/invalid."""
    parsed = version_key(raw)
    if parsed is None:
        return None
    major, minor, patch = parsed
    if major:
        return (major,)
    if minor:
        return (0, minor)
    return (0, 0, patch)


def source_class(source: str) -> str:
    if source in (PATH_SOURCE, ""):
        return "path"
    if source.startswith("registry+"):
        return "registry"
    if source.startswith("git+"):
        return "git"
    return "other"


def load_scope(lock: Path) -> dict:
    """Parse one lockfile into nodes plus resolved reverse-parent edges."""
    packages = tomllib.loads(lock.read_text(encoding="utf-8")).get("package", [])
    nodes = []
    by_name: dict[str, list[int]] = defaultdict(list)
    for package in packages:
        node = {
            "name": package["name"],
            "version": package["version"],
            "source": package.get("source", PATH_SOURCE),
            "deps": list(package.get("dependencies", [])),
        }
        by_name[node["name"]].append(len(nodes))
        nodes.append(node)
    parents: dict[int, list[int]] = defaultdict(list)
    quality: list[dict] = []
    for index, node in enumerate(nodes):
        for spec in node["deps"]:
            try:
                name, version, source = parse_lock_dep(spec)
            except ValueError:
                quality.append({"code": "unparsed_lock_edge",
                                "parent": node["name"], "entry": spec})
                continue
            candidates = by_name.get(name, [])
            if version is not None:
                candidates = [i for i in candidates
                              if nodes[i]["version"] == version]
            if source is not None:
                candidates = [i for i in candidates
                              if nodes[i]["source"] == source]
            if not candidates:
                quality.append({"code": "unresolved_lock_edge",
                                "parent": node["name"], "entry": spec})
            elif len(candidates) > 1:
                quality.append({"code": "ambiguous_lock_edge",
                                "parent": node["name"], "entry": spec,
                                "candidates": len(candidates)})
            for target in candidates:
                parents[target].append(index)
    return {"nodes": nodes, "parents": parents, "quality": quality}


def describe(node: dict) -> dict:
    return {"name": node["name"], "version": node["version"],
            "source": node["source"]}


def find_declarers(root: Path, names: list[str],
                   wanted: set[str]) -> dict[str, list[dict]]:
    """Map family package names to direct manifest declarations."""
    declarers: dict[str, list[dict]] = defaultdict(list)
    for owner, path, doc in graph.manifests(root, names):
        if doc is None:
            continue
        for section, dependencies in graph.dependency_tables(doc):
            for alias, raw in dependencies.items():
                value = {"version": raw} if isinstance(raw, str) else raw
                if not isinstance(value, dict):
                    continue
                source_manifest = path
                inherited_from = None
                if value.get("workspace") is True:
                    inherited, workspace_manifest = graph.inherited_dependencies(
                        path, root / owner)
                    inherited = inherited.get(alias)
                    if inherited is None:
                        continue
                    value = {"version": inherited} if isinstance(inherited, str) else inherited
                    source_manifest = workspace_manifest
                    inherited_from = str(workspace_manifest)
                package = value.get("package", alias)
                if package not in wanted:
                    continue
                if "path" in value:
                    requirement = f"path {value['path']}"
                elif "git" in value:
                    requirement = (f"git {value['git']}@"
                                   f"{value.get('rev') or value.get('tag') or value.get('branch') or 'unbound'}")
                else:
                    requirement = f"version {value.get('version', '*')}"
                declarers[package].append({
                    "workspace": owner,
                    "manifest": str(source_manifest),
                    "declared_in": str(path),
                    "section": section,
                    "alias": alias,
                    "requirement": requirement,
                    "inherited_from": inherited_from,
                    "role": ("source_override" if section.startswith("patch.")
                             else "dependency"),
                })
    for entries in declarers.values():
        entries.sort(key=lambda item: (item["workspace"], item["manifest"],
                                       item["section"], item["alias"]))
    return declarers


def classify(package: str, locations: list[dict]) -> dict:
    versions = sorted({item["version"] for item in locations})
    sources_by_version: dict[str, list[str]] = {}
    for version in versions:
        sources_by_version[version] = sorted(
            {item["source"] for item in locations if item["version"] == version})
    has_version_split = len(versions) > 1
    has_source_split = any(len(sources) > 1 for sources in sources_by_version.values())
    kind = ("version+source" if has_version_split and has_source_split
            else "source" if has_source_split else "version")
    per_scope: dict[str, set[str]] = defaultdict(set)
    per_scope_sources: dict[str, set[str]] = defaultdict(set)
    for item in locations:
        per_scope[item["scope"]].add(item["version"])
        per_scope_sources[item["scope"]].add(item["source"])
    coexisting = sorted(scope for scope in per_scope
                        if len(per_scope[scope]) > 1 or len(per_scope_sources[scope]) > 1)
    groups: dict[str, list[str]] = defaultdict(list)
    ungrouped: list[str] = []
    for version in versions:
        compat = compatibility(version)
        if compat is None:
            ungrouped.append(version)
        else:
            groups[".".join(str(part) for part in compat)].append(version)
    for members in groups.values():
        members.sort(key=lambda value: (version_key(value), value))
    classes = {source_class(item["source"]) for item in locations}
    convergent = (has_version_split and not has_source_split
                  and not ungrouped and len(groups) == 1 and classes == {"registry"})
    target = None
    if convergent:
        only = next(iter(groups.values()))
        target = only[-1]
    return {
        "package": package,
        "versions": versions,
        "sources_by_version": sources_by_version,
        "kind": kind,
        "coexisting_scopes": coexisting,
        "cross_lock_only": not coexisting,
        "compat_groups": dict(sorted(groups.items())),
        "prerelease_or_invalid": sorted(ungrouped),
        "source_classes": sorted(classes),
        "convergent": convergent,
        "target": target,
    }


def rank_family(family: dict, has_local_parent: bool) -> int:
    if family["convergent"] and family["cross_lock_only"]:
        return 1
    if family["convergent"]:
        return 2
    if family["kind"] in ("source", "version+source"):
        return 5
    return 3 if has_local_parent else 4


def plan(root: Path, names: list[str] | None = None) -> dict:
    names = names or workspace_names()
    gate = graph.audit(root, names)
    scopes = lock_scopes(root, names)
    scope_reports = []
    aggregate: dict[str, list[dict]] = defaultdict(list)
    quality: list[dict] = []
    for scope, lock in scopes:
        if not lock.is_file():
            scope_reports.append({"scope": scope, "lockfile": str(lock),
                                  "sha256": None, "missing": True})
            continue
        data = load_scope(lock)
        scope_reports.append({"scope": scope, "lockfile": str(lock),
                              "sha256": sha256(lock), "missing": False,
                              "nodes": len(data["nodes"])})
        for key, issue in enumerate(data["quality"]):
            quality.append({"scope": scope, **issue, "index": key})
        for index, node in enumerate(data["nodes"]):
            seen: set[tuple[str, str, str]] = set()
            parents = []
            for parent in sorted(data["parents"].get(index, []),
                                 key=lambda i: (data["nodes"][i]["name"],
                                                data["nodes"][i]["version"],
                                                data["nodes"][i]["source"])):
                key = (data["nodes"][parent]["name"],
                       data["nodes"][parent]["version"],
                       data["nodes"][parent]["source"])
                if key not in seen:
                    seen.add(key)
                    parents.append(describe(data["nodes"][parent]))
            aggregate[node["name"]].append({
                "scope": scope, "version": node["version"],
                "source": node["source"], "parents": parents,
            })
    families = []
    for package in sorted(aggregate):
        versions = {item["version"] for item in aggregate[package]}
        source_split = any(
            len({item["source"] for item in aggregate[package]
                 if item["version"] == version}) > 1 for version in versions)
        if len(versions) < 2 and not source_split:
            continue
        family = classify(package, aggregate[package])
        family["locations"] = sorted(aggregate[package],
                                     key=lambda item: (item["scope"], item["version"]))
        families.append(family)
    declarers = find_declarers(root, names, {family["package"] for family in families})
    for family in families:
        family["declarers"] = declarers.get(family["package"], [])
        local_parent = any(
            parent["source"] == PATH_SOURCE
            for location in family["locations"] for parent in location["parents"])
        local_declarer = any(entry["workspace"] in set(names)
                             for entry in family["declarers"])
        family["has_local_parent"] = bool(local_parent or local_declarer)
        family["rank"] = rank_family(family, family["has_local_parent"])
        if family["convergent"]:
            family["action"] = {"type": "lock_converge", "target": family["target"]}
        elif family["kind"] in ("source", "version+source"):
            family["action"] = {"type": "source_change",
                                "reason": "same version resolves from multiple sources; "
                                          "align patch/vendor/git declarations before locking"}
        elif family["prerelease_or_invalid"]:
            family["action"] = {"type": "owner_port",
                                "reason": "prerelease or invalid versions need manual review"}
        else:
            family["action"] = {"type": "owner_port",
                                "reason": "multiple semver-incompatible groups; "
                                          "port compatible owning parents without substituting "
                                          "unrelated satellite crates"}
    families.sort(key=lambda item: (item["rank"], item["package"]))
    clusters: dict[tuple[str, str], dict] = {}
    for family in families:
        seen_parents = {(parent["name"], parent["source"])
                        for location in family["locations"] for parent in location["parents"]}
        for key in seen_parents:
            cluster = clusters.setdefault(key, {"parent": key[0], "parent_source": key[1],
                                                "families": [], "scopes": set()})
            cluster["families"].append(family["package"])
            for location in family["locations"]:
                if any((parent["name"], parent["source"]) == key
                       for parent in location["parents"]):
                    cluster["scopes"].add(location["scope"])
    cluster_list = [{"parent": cluster["parent"], "parent_source": cluster["parent_source"],
                     "families": sorted(set(cluster["families"])),
                     "scopes": sorted(cluster["scopes"])}
                    for cluster in clusters.values() if len(set(cluster["families"])) > 1]
    cluster_list.sort(key=lambda item: (-len(item["families"]), item["parent"]))
    steps = []
    for family in families:
        if not family["convergent"]:
            continue
        assert family["target"] is not None
        for location in family["locations"]:
            if location["version"] == family["target"]:
                continue
            lock = next(path for scope, path in scopes if scope == location["scope"])
            steps.append({
                "rank": family["rank"],
                "package": family["package"],
                "scope": location["scope"],
                "lockfile": str(lock),
                "from": location["version"],
                "to": family["target"],
                "gpui_owned": location["scope"] == "gpui-toolkit",
                "command": ["cargo", "update", "-p",
                            f"{family['package']}@{location['version']}",
                            "--precise", family["target"]],
                "cwd": str(lock.parent if location["scope"] != NESTED_SCOPE
                           else root / "autoeq" / "crates" / NESTED_SCOPE),
            })
    steps.sort(key=lambda item: (item["rank"], item["scope"], item["package"], item["from"]))
    owner_actions = [{"package": family["package"], "rank": family["rank"],
                      "kind": family["kind"], "versions": family["versions"],
                      "action": family["action"],
                      "scopes": sorted({location["scope"] for location in family["locations"]})}
                     for family in families if not family["convergent"]]
    summary = {
        "aggregate_families": len(families),
        "version_kind": sum(family["kind"] == "version" for family in families),
        "source_kind": sum(family["kind"] == "source" for family in families),
        "version_and_source_kind": sum(family["kind"] == "version+source" for family in families),
        "cross_lock_only": sum(family["cross_lock_only"] for family in families),
        "with_coexisting_scope": sum(not family["cross_lock_only"] for family in families),
        "convergent": sum(family["convergent"] for family in families),
        "owner_action": len(owner_actions),
        "lock_steps": len(steps),
        "shared_parent_clusters": len(cluster_list),
        "data_quality_issues": len(quality),
    }
    return {"schema_version": SCHEMA_VERSION, "tool": "dependency_remediation.py",
            "read_only": True, "root": str(root), "scopes": scope_reports,
            "gate": gate["summary"], "summary": summary, "families": families,
            "clusters": cluster_list, "steps": steps, "owner_actions": owner_actions,
            "vendors": gate["vendors"], "data_quality": quality}


def render_markdown(report: dict) -> str:
    lines = ["# Dependency remediation plan",
             "",
             f"Scopes: {len(report['scopes'])} lockfiles. "
             f"Gate: {report['gate']['errors']} errors, {report['gate']['reports']} reports. "
             f"Aggregate families: {report['summary']['aggregate_families']} "
             f"({report['summary']['convergent']} semver-convergent, "
             f"{report['summary']['owner_action']} owner actions).",
             "",
             "Rank 1 = convergent cross-lock-only; 2 = convergent coexisting; "
             "3 = incompatible groups with local parents; 4 = incompatible groups, "
             "external parents only; 5 = source splits. No family is waived.",
             "",
             "## Lock hashes",
             "",
             "| Scope | SHA-256 |",
             "| --- | --- |"]
    for scope in report["scopes"]:
        lines.append(f"| {scope['scope']} | `{scope['sha256'] or 'MISSING'}` |")
    lines += ["", "## Minimal lock-only steps",
              "",
              "Run each command in its `cwd` after review, then re-run locked metadata. "
              "Steps marked GPUI-owned belong to the GPUI worker; do not execute them here.",
              ""]
    if report["steps"]:
        lines += ["| Rank | Scope | Package | From | To | Owner | Command |",
                  "| ---: | --- | --- | --- | --- | --- | --- |"]
        for step in report["steps"]:
            owner = "GPUI" if step["gpui_owned"] else "parent"
            command = " ".join(step["command"])
            lines.append(f"| {step['rank']} | {step['scope']} | {step['package']} | "
                         f"{step['from']} | {step['to']} | {owner} | `{command}` |")
    else:
        lines.append("None: no semver-convergent family remains.")
    lines += ["", "## Shared-parent clusters",
              "",
              "One parent migration can converge several families in the same cluster.",
              ""]
    if report["clusters"]:
        lines += ["| Parent | Families | Scopes |",
                  "| --- | --- | --- |"]
        for cluster in report["clusters"]:
            lines.append(f"| {cluster['parent']} | {', '.join(cluster['families'])} | "
                         f"{', '.join(cluster['scopes'])} |")
    else:
        lines.append("None: no parent spans more than one family.")
    lines += ["", "## All aggregate families", ""]
    for family in report["families"]:
        lines.append(f"### {family['package']} (rank {family['rank']}, {family['kind']})")
        lines.append("")
        lines.append(f"Versions: {', '.join(family['versions'])}. "
                     f"Target: {family['action'].get('target', family['action'].get('reason', ''))}.")
        coexisting = ", ".join(family["coexisting_scopes"]) or "none (cross-lock-only)"
        lines.append(f"Coexisting scopes: {coexisting}.")
        parents: dict[str, list[str]] = defaultdict(list)
        for location in family["locations"]:
            for parent in location["parents"][:8]:
                parents[f"{parent['name']} {parent['version']}"].append(location["scope"])
        if parents:
            lines.append("Key parents:")
            for parent, scopes in sorted(parents.items())[:12]:
                lines.append(f"- {parent} in {', '.join(sorted(set(scopes)))}")
        if family["declarers"]:
            lines.append("Direct declarers:")
            for entry in family["declarers"][:12]:
                lines.append(f"- {entry['workspace']}:{entry['declared_in']} "
                             f"[{entry['section']}] {entry['requirement']}")
        lines.append("")
    lines += ["## Vendors retained", "",
              f"{len(report['vendors'])} vendored packages require ownership/patch/license review.",
              ""]
    for vendor in report["vendors"]:
        copies = "; ".join(f"{copy['owner']} {copy['version']}" for copy in vendor["copies"])
        lines.append(f"- {vendor['package']}: {copies}")
    lines += ["", "## Data quality", "",
              f"{len(report['data_quality'])} lock-edge issues.", ""]
    for issue in report["data_quality"][:20]:
        lines.append(f"- {issue['scope']}: {issue['code']} {issue.get('entry', '')}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args(argv)
    report = plan(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    summary = report["summary"]
    print(f"{summary['aggregate_families']} families, "
          f"{summary['convergent']} convergent, {summary['owner_action']} owner actions, "
          f"{summary['lock_steps']} lock steps; {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
