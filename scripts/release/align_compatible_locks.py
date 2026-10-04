#!/usr/bin/env python3
"""Propose compatible registry lock updates across the ten release lockfiles.

This is a Gitea preparation lane. Its output requires separate package/edge
review before any Cargo.lock is committed. It never edits manifests.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "release"))
from checkout_sources import read_manifest

WORKSPACES = (
    "math-audio", "gpui-toolkit", "sofa-reader", "symphonia-add-ons",
    "autoeq", "sotf-daw", "sotf-capture", "sotf", "sotf-systemwide",
)
NESTED = "autoeq-gpui-examples"
VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)
WASM_FAMILY = {"wasm-bindgen", "wasm-bindgen-futures", "wasm-bindgen-macro",
               "wasm-bindgen-macro-support", "wasm-bindgen-shared", "js-sys", "web-sys"}
CRATES_IO = "registry+https://github.com/rust-lang/crates.io-index"
ACTIVE: subprocess.Popen | None = None


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def version_key(raw: str) -> tuple[int, int, int] | None:
    match = VERSION.fullmatch(raw)
    if not match or match.group(4):
        return None
    return tuple(int(match.group(i)) for i in (1, 2, 3))


def compatibility(raw: str) -> tuple[int, ...] | None:
    parsed = version_key(raw)
    if parsed is None:
        return None
    major, minor, patch = parsed
    if major:
        return (major,)
    if minor:
        return (0, minor)
    return (0, 0, patch)


def lock_specs(root: Path) -> list[tuple[str, Path, Path]]:
    specs = [(name, root / name, root / name / "Cargo.lock") for name in WORKSPACES]
    specs.append((NESTED, root / "autoeq" / "crates" / NESTED,
                  root / "autoeq" / "crates" / NESTED / "Cargo.lock"))
    return specs


def registry_versions(lock: Path) -> dict[str, set[str]]:
    packages = tomllib.loads(lock.read_text(encoding="utf-8")).get("package", [])
    found: dict[str, set[str]] = defaultdict(set)
    for package in packages:
        if package.get("source") == CRATES_IO:
            found[package["name"]].add(package["version"])
    return found


def package_ids(lock: Path) -> set[tuple[str, str, str]]:
    return {
        (item["name"], item["version"], item.get("source", ""))
        for item in tomllib.loads(lock.read_text(encoding="utf-8")).get("package", [])
    }


def family_versions(lock: Path) -> dict[str, list[str]]:
    versions = registry_versions(lock)
    return {name: sorted(versions[name]) for name in sorted(WASM_FAMILY) if name in versions}


def plans(specs: list[tuple[str, Path, Path]]) -> tuple[list[dict], list[dict]]:
    all_versions: dict[tuple[str, tuple[int, ...]], set[str]] = defaultdict(set)
    rejected: list[dict] = []
    for name, _, lock in specs:
        for package, versions in registry_versions(lock).items():
            for version in versions:
                group = compatibility(version)
                if group is None:
                    rejected.append({"workspace": name, "package": package,
                                     "version": version, "reason": "prerelease or invalid semver"})
                else:
                    all_versions[(package, group)].add(version)
    updates: list[dict] = []
    for (package, group), versions in sorted(all_versions.items()):
        if len(versions) < 2:
            continue
        target = max(versions, key=lambda value: (version_key(value), value))
        for name, _, lock in specs:
            present = registry_versions(lock).get(package, set())
            for old in sorted(present & (versions - {target}), key=lambda value: (version_key(value), value)):
                updates.append({"workspace": name, "package": package, "from": old,
                                "to": target, "compatibility": group,
                                "coupled_wasm_family": package in WASM_FAMILY})
    updates.sort(key=lambda item: (not item["coupled_wasm_family"], item["workspace"],
                                   item["package"], version_key(item["from"])))
    return updates, rejected


def stop_group(process: subprocess.Popen) -> bool:
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            process.wait(timeout=1)
            return True
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            continue
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return True
    return False


def interrupted(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt("release alignment interrupted")


def command(argv: list[str], cwd: Path, log: Path, timeout: int) -> dict:
    global ACTIVE
    start = time.monotonic()
    with log.open("wb") as stream:
        ACTIVE = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                  start_new_session=True)
        try:
            code = ACTIVE.wait(timeout=timeout)
            clean = stop_group(ACTIVE)
            return {"argv": argv, "exit_code": code, "cleanup_ok": clean,
                    "duration_seconds": round(time.monotonic()-start, 2), "log": str(log)}
        except subprocess.TimeoutExpired:
            clean = stop_group(ACTIVE)
            return {"argv": argv, "exit_code": None, "timeout": True, "cleanup_ok": clean,
                    "duration_seconds": round(time.monotonic()-start, 2), "log": str(log)}
        except KeyboardInterrupt:
            clean = stop_group(ACTIVE)
            if not clean:
                raise RuntimeError("alignment child process group survived interruption")
            raise
        finally:
            ACTIVE = None


def write_report(path: Path, report: dict) -> None:
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "release-compatible-locks")
    parser.add_argument("--timeout-per-update", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.timeout_per_update <= 900:
        parser.error("timeout-per-update must be 1..900 seconds")
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "logs").mkdir()
    (output / "locks").mkdir()
    manifest = root / "scripts" / "release" / "sources.json"
    signal.signal(signal.SIGTERM, interrupted)
    report: dict = {"started_at": utc(), "status": "RUNNING", "release_qa": False,
                    "commands": [], "issues": [], "sources_before": {}, "sources_after": {},
                    "root_before": git(root, "rev-parse", "HEAD"),
                    "manifest_before_sha256": sha(manifest), "locks": {},
                    "package_changes": {}, "wasm_family": {}}
    report_path = output / "report.json"
    write_report(report_path, report)
    specs = lock_specs(root)
    revisions: dict[str, str] = {}
    try:
        _, _, revisions = read_manifest(manifest)
        for name in WORKSPACES:
            repo = root / name
            actual = git(repo, "rev-parse", "HEAD")
            dirty = git(repo, "status", "--porcelain")
            report["sources_before"][name] = {"revision": actual, "dirty": bool(dirty)}
            if actual != revisions[name] or dirty:
                report["issues"].append(f"{name}: pinned revision or clean checkout mismatch")
        for name, _, lock in specs:
            if not lock.is_file():
                report["issues"].append(f"{name}: Cargo.lock missing")
                continue
            report["locks"][name] = {"before_sha256": sha(lock)}
            report["wasm_family"][name] = {"before": family_versions(lock)}
            destination = output / "locks" / name
            destination.mkdir()
            shutil.copy2(lock, destination / "Cargo.lock.before")
        if report["issues"]:
            raise RuntimeError("source or lock preflight failed")
        proposed, rejected = plans(specs)
        report["plan"] = proposed
        report["manual_review"] = rejected
        if rejected:
            report["issues"].append("prerelease or invalid registry versions require manual compatibility review")
            raise RuntimeError("automatic alignment refuses unclassified prerelease compatibility")
        write_report(report_path, report)
        for number, item in enumerate(proposed):
            name = item["workspace"]
            _, cwd, lock = next(spec for spec in specs if spec[0] == name)
            if item["from"] not in registry_versions(lock).get(item["package"], set()):
                present = registry_versions(lock).get(item["package"], set())
                if item["to"] in present:
                    item["status"] = "TARGET_ALREADY_PRESENT"
                elif not present:
                    item["status"] = "PACKAGE_PRUNED"
                else:
                    item["status"] = "FAIL"
                    report["issues"].append(
                        f"{name}: {item['package']} old version vanished but target was not selected"
                    )
                    break
                continue
            argv = ["cargo", "update", "-p", f"{item['package']}@{item['from']}",
                    "--precise", item["to"]]
            result = command(argv, cwd, output / "logs" / f"{number:03d}-{name}-{item['package']}.log",
                             args.timeout_per_update)
            report["commands"].append(result)
            item["status"] = "UPDATED" if result["exit_code"] == 0 and result["cleanup_ok"] else "FAIL"
            write_report(report_path, report)
            if item["status"] == "FAIL":
                report["issues"].append(f"{name}: {item['package']} alignment failed; partial locks retained")
                break
        if not report["issues"]:
            for name, cwd, _ in specs:
                result = command(["cargo", "metadata", "--locked", "--all-features",
                                  "--format-version", "1", "--no-deps"],
                                 cwd, output / "logs" / f"metadata-{name}.log", 300)
                report["commands"].append(result)
                if result["exit_code"] != 0 or not result["cleanup_ok"]:
                    report["issues"].append(f"{name}: final locked metadata failed")
                    break
    except KeyboardInterrupt as error:
        report["issues"].append(str(error))
        report["interrupted"] = True
        if ACTIVE is not None:
            report["cleanup_ok"] = stop_group(ACTIVE)
    except Exception as error:
        report["issues"].append(str(error))
    finally:
        for name, _, lock in specs:
            try:
                if not lock.is_file():
                    raise FileNotFoundError("Cargo.lock missing")
                report["locks"].setdefault(name, {})["after_sha256"] = sha(lock)
                destination = output / "locks" / name
                destination.mkdir(exist_ok=True)
                shutil.copy2(lock, destination / "Cargo.lock")
                before_ids = package_ids(destination / "Cargo.lock.before") if (destination / "Cargo.lock.before").is_file() else set()
                after_ids = package_ids(lock)
                planned_targets = {
                    (item["package"], item["to"], CRATES_IO)
                    for item in report.get("plan", []) if item["workspace"] == name
                }
                report["package_changes"][name] = {
                    "added": sorted(after_ids - before_ids),
                    "removed": sorted(before_ids - after_ids),
                    "unexpected_additions": sorted((after_ids - before_ids) - planned_targets),
                }
                report["wasm_family"].setdefault(name, {})["after"] = family_versions(lock)
            except OSError as error:
                report["issues"].append(f"{name}: could not preserve partial lock: {error}")
        for item in report.get("plan", []):
            name = item["workspace"]
            lock = next(path for label, _, path in specs if label == name)
            if not lock.is_file():
                continue
            present = registry_versions(lock).get(item["package"], set())
            if item["from"] in present:
                report["issues"].append(f"{name}: {item['package']} old compatible version remains")
            elif item["to"] in present:
                item["final_observation"] = "TARGET_PRESENT"
            elif not present:
                item["final_observation"] = "PACKAGE_PRUNED"
            else:
                report["issues"].append(
                    f"{name}: {item['package']} target absent after alignment despite package remaining"
                )
        metadata_results = [result for result in report["commands"]
                            if result["argv"][:2] == ["cargo", "metadata"]]
        report["wasm_family_consistent"] = (
            len(metadata_results) == len(specs)
            and all(result["exit_code"] == 0 and result["cleanup_ok"]
                    for result in metadata_results)
            and not any(item["coupled_wasm_family"] and "final_observation" not in item
                        for item in report.get("plan", []))
        )
        for name in WORKSPACES:
            try:
                repo = root / name
                actual = git(repo, "rev-parse", "HEAD")
                changed = git(repo, "status", "--porcelain")
                report["sources_after"][name] = {"revision": actual, "status": changed}
                allowed = {"Cargo.lock"}
                if name == "autoeq":
                    allowed.add("crates/autoeq-gpui-examples/Cargo.lock")
                paths = set(git(repo, "diff", "--name-only").splitlines())
                paths |= set(git(repo, "diff", "--cached", "--name-only").splitlines())
                paths |= set(git(repo, "ls-files", "--others", "--exclude-standard").splitlines())
                if name in revisions and (actual != revisions[name] or paths - allowed):
                    report["issues"].append(f"{name}: source changed outside allowed locks")
            except (OSError, subprocess.CalledProcessError) as error:
                report["issues"].append(f"{name}: source after-state unavailable: {error}")
        try:
            report["root_after"] = git(root, "rev-parse", "HEAD")
            report["manifest_after_sha256"] = sha(manifest)
            if (report["root_after"] != report["root_before"]
                    or report["manifest_after_sha256"] != report["manifest_before_sha256"]):
                report["issues"].append("root revision or source manifest changed during alignment")
        except (OSError, subprocess.CalledProcessError) as error:
            report["issues"].append(f"root after-state unavailable: {error}")
        report["status"] = "FAIL" if report["issues"] else "PROPOSED"
        report["finished_at"] = utc()
        write_report(report_path, report)
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
