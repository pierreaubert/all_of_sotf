#!/usr/bin/env python3
"""Align external dependency versions across the six sibling Rust workspaces.

The repository contains six independent Cargo workspaces (no top-level
Cargo.toml). This script scans every Cargo.toml under those roots, finds
external crates that are declared with different version requirements, and
optionally rewrites them all to use a single chosen version.

Usage:
    python3 scripts/align_crate_versions.py            # report only
    python3 scripts/align_crate_versions.py --apply    # rewrite files

Path dependencies and git dependencies without a `version` key are ignored,
because their effective version is determined by the source, not the version
requirement string. Packages that are referenced from both crates.io and git
sources are reported as skipped, because aligning their version strings would
change the effective source for at least one workspace.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import tomllib
from packaging.version import InvalidVersion, Version

try:
    import tomlkit
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "tomlkit is required for --apply; install it with: pip install tomlkit"
    ) from exc

ROOTS = [
    "sotf",
    "autoeq",
    "math-audio",
    "gpui-toolkit",
    "sofa-reader",
    "symphonia-add-ons",
]

# Directories that are git worktrees, experiment worktrees, build output, or
# vendored forks used as [patch] sources. Their dependency versions are
# intentionally independent of the main workspace declarations.
IGNORED_DIR_PARTS = {"target", ".git", ".worktrees", ".evo", "3rdparties"}


def find_cargo_tomls(repo_root: Path) -> list[Path]:
    """Return every Cargo.toml under the six workspace roots, excluding ignored dirs."""
    files: list[Path] = []
    for name in ROOTS:
        root = repo_root / name
        if not root.is_dir():
            continue
        for path in root.rglob("Cargo.toml"):
            if not IGNORED_DIR_PARTS.isdisjoint(path.parts):
                continue
            files.append(path)
    files.sort()
    return files


def dependency_sections(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a flat mapping of section-name -> deps-dict."""
    sections: dict[str, dict[str, Any]] = {}
    if "dependencies" in doc:
        sections["dependencies"] = doc["dependencies"]
    if "dev-dependencies" in doc:
        sections["dev-dependencies"] = doc["dev-dependencies"]
    if "build-dependencies" in doc:
        sections["build-dependencies"] = doc["build-dependencies"]
    if "workspace" in doc and isinstance(doc["workspace"], dict):
        ws = doc["workspace"]
        if "dependencies" in ws:
            sections["workspace.dependencies"] = ws["dependencies"]
    # Target-specific dependency sections are ignored for version alignment:
    # they almost always use `workspace = true` in this repo, and handling their
    # cfg keys adds complexity without changing the alignment outcome.
    return sections


def package_info(key: str, value: Any) -> tuple[str, str, str] | None:
    """Return (package_name, version_string, source_key) for a dependency.

    Returns None for path-only dependencies or for workspace/git references
    that do not carry an explicit version requirement.

    source_key is "crates.io" for registry dependencies or "git:<url>" for
    git dependencies. Mixed source_keys for the same package prevent alignment.
    """
    if isinstance(value, str):
        return key, value, "crates.io"
    if not isinstance(value, dict):
        return None
    if "path" in value:
        return None
    pkg = value.get("package", key)
    version = value.get("version")
    if version is None:
        return None
    if "git" in value:
        source_key = f"git:{value['git']}"
    else:
        source_key = "crates.io"
    return pkg, version, source_key


def collect_versions(
    repo_root: Path,
) -> dict[str, list[tuple[Path, str, str, str]]]:
    """Map package name -> list of (file, section, version, source_key)."""
    by_package: dict[str, list[tuple[Path, str, str, str]]] = defaultdict(list)
    for path in find_cargo_tomls(repo_root):
        with path.open("rb") as f:
            doc = tomllib.load(f)
        for section, deps in dependency_sections(doc).items():
            for key, value in deps.items():
                info = package_info(key, value)
                if info is None:
                    continue
                pkg, version, source_key = info
                by_package[pkg].append((path, section, version, source_key))
    return by_package


def normalize_version(version: str) -> Version:
    """Turn a Cargo version requirement like '=21.0.0' into a sortable Version."""
    v = version.lstrip("=^~<>!")
    v = v.split(",")[0].strip()
    return Version(v)


def version_sort_key(v: str) -> tuple[int, Version]:
    try:
        return 0, normalize_version(v)
    except InvalidVersion:
        return 1, Version("0")


def find_conflicts(
    by_package: dict[str, list[tuple[Path, str, str, str]]],
) -> tuple[dict[str, dict[str, list[tuple[Path, str]]]], dict[str, set[str]]]:
    """Return (conflicts, skipped) where conflicts are alignable mismatches.

    skipped maps package name -> set of source keys for packages that appear
    with mixed sources (e.g. crates.io and git) and therefore cannot be safely
    aligned by changing version strings alone.
    """
    conflicts: dict[str, dict[str, list[tuple[Path, str]]]] = {}
    skipped: dict[str, set[str]] = {}
    for pkg, entries in by_package.items():
        sources = {source_key for _path, _section, _version, source_key in entries}
        if len(sources) > 1:
            skipped[pkg] = sources
            continue

        versions: dict[str, list[tuple[Path, str]]] = defaultdict(list)
        for path, section, version, _source_key in entries:
            versions[version].append((path, section))
        if len(versions) > 1:
            conflicts[pkg] = dict(versions)
    return conflicts, skipped


def pick_target(version_entries: dict[str, list[tuple[Path, str]]]) -> str:
    """Choose the highest normalized SemVer version as the alignment target."""
    return max(version_entries.keys(), key=version_sort_key)


def report_conflicts(
    conflicts: dict[str, dict[str, list[tuple[Path, str]]]],
    skipped: dict[str, set[str]],
) -> int:
    if skipped:
        print(f"Skipped {len(skipped)} package(s) with mixed sources:\n")
        for pkg in sorted(skipped):
            print(f"  {pkg}: {', '.join(sorted(skipped[pkg]))}")
        print()

    if not conflicts:
        if not skipped:
            print("No version mismatches found across the six workspaces.")
        else:
            print("No additional alignable version mismatches found.")
        return 0

    print(f"Found {len(conflicts)} package(s) with mismatched versions:\n")
    for pkg in sorted(conflicts):
        versions = conflicts[pkg]
        target = pick_target(versions)
        print(f"{pkg}  -> align to {target}")

        for version in sorted(versions, key=version_sort_key):
            marker = " *" if version == target else ""
            try:
                normalize_version(version)
            except InvalidVersion:
                marker += " (unparseable)"
            print(f"    {version}{marker}")
            for path, section in versions[version]:
                rel = path.relative_to(Path.cwd())
                print(f"        {rel}  [{section}]")
        print()
    return 1


def build_change_map(
    conflicts: dict[str, dict[str, list[tuple[Path, str]]]],
) -> dict[Path, dict[str, dict[str, str]]]:
    """Map file -> section -> package-name -> target-version."""
    targets = {pkg: pick_target(versions) for pkg, versions in conflicts.items()}
    changes: dict[Path, dict[str, dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for pkg, versions in conflicts.items():
        target = targets[pkg]
        for version, locations in versions.items():
            if version == target:
                continue
            for path, section in locations:
                changes[path][section][pkg] = target
    return changes


def align_versions(
    repo_root: Path,
    conflicts: dict[str, dict[str, list[tuple[Path, str]]]],
) -> int:
    if not conflicts:
        print("No version mismatches to fix.")
        return 0

    changes = build_change_map(conflicts)
    for path, sections in changes.items():
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
        for section, deps in sections.items():
            container: tomlkit.items.Table
            if section == "workspace.dependencies":
                ws = doc.setdefault("workspace", tomlkit.table())
                container = ws.setdefault("dependencies", tomlkit.table())
            else:
                container = doc.setdefault(section, tomlkit.table())

            for pkg, target in deps.items():
                value = container.get(pkg)
                if value is None:
                    continue
                if isinstance(value, tomlkit.items.String):
                    container[pkg] = target
                elif isinstance(value, tomlkit.items.InlineTable):
                    if "version" in value:
                        value["version"] = target
                    # If the table only has `package = "..."` and no version,
                    # there is nothing to align.
                # else: unexpected shape, leave untouched
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")
        print(f"updated {path.relative_to(repo_root)}")

    print(f"\nAligned {len(conflicts)} package(s) across {len(changes)} file(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite Cargo.toml files to use the chosen target version.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing the six workspace directories.",
    )
    args = parser.parse_args()

    by_package = collect_versions(args.root)
    conflicts, skipped = find_conflicts(by_package)

    if not args.apply:
        return report_conflicts(conflicts, skipped)

    return align_versions(args.root, conflicts)


if __name__ == "__main__":
    sys.exit(main())
