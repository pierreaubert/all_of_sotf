#!/usr/bin/env python3
"""Collect rustfmt patches for parent review without publishing source changes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release import nih_native_artifact_check as owned
from scripts.release.checkout_sources import read_manifest

OUTPUT = ROOT / "target/release-gitea/format-evidence"
WORKSPACES = ("autoeq", "gpui-toolkit", "math-audio", "sofa-reader", "sotf",
              "sotf-capture", "sotf-daw", "sotf-systemwide", "symphonia-add-ons")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_paths(workspace: str) -> list[str]:
    result = subprocess.check_output(
        ["git", "diff", "--name-only", "-z", "HEAD", "--"], cwd=ROOT / workspace
    )
    return [name.decode() for name in result.split(b"\0") if name]


def dirty_untracked(workspace: str) -> list[str]:
    result = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=ROOT / workspace)
    return [name.decode() for name in result.split(b"\0") if name]


def capture_patch(workspace: str) -> dict:
    path = OUTPUT / "patches" / f"{workspace}.patch"
    with path.open("wb") as stream:
        subprocess.run(["git", "diff", "--binary", "HEAD", "--"], cwd=ROOT / workspace, stdout=stream, check=True)
    names = changed_paths(workspace)
    blobs = []
    for name in names:
        before = subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=ROOT / workspace)
        after = (ROOT / workspace / name).read_bytes()
        blobs.append({"path": name, "before_sha256": hashlib.sha256(before).hexdigest(),
                      "after_sha256": hashlib.sha256(after).hexdigest()})
    return {"workspace": workspace, "paths": names, "tracked_blobs": blobs, "sha256": sha(path),
            "bytes": path.stat().st_size,
            "vendor_paths": [name for name in names if name.startswith("crates/3rdparties/")]}


def format_errors(before: dict, after: dict, pins: dict[str, str], patches: list[dict]) -> list[str]:
    errors: list[str] = []
    if before["root_revision"] != after["root_revision"]:
        errors.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        errors.append("sources.json changed")
    previous = before["root_layout"]
    current = after["root_layout"]
    for label, layout in (("before", previous), ("after", current)):
        if layout["missing"] or layout["allowed_siblings"] or set(layout["tracked_gitlinks"]) != set(pins):
            errors.append(f"{label}: root gitlink layout changed")
    if previous["unexpected"]:
        errors.append("root was dirty before formatting")
    if current["tracked_gitlinks"] != previous["tracked_gitlinks"]:
        errors.append("indexed root gitlinks changed")
    by_owner = {entry["workspace"]: entry for entry in patches}
    if set(by_owner) != set(pins) or len(patches) != len(pins):
        errors.append("patch inventory does not cover nine owners exactly")
    expected_root_dirty: set[str] = set()
    for workspace in pins:
        patch = by_owner.get(workspace, {})
        paths = patch.get("paths", [])
        blobs = patch.get("tracked_blobs", [])
        if len(paths) != len(set(paths)) or {item.get("path") for item in blobs} != set(paths) or len(blobs) != len(paths):
            errors.append(f"{workspace}: tracked blob inventory differs from patch paths")
        if workspace not in WORKSPACES and paths:
            errors.append(f"{workspace}: unexpected formatting owner")
        if any(not name.endswith(".rs") for name in paths):
            errors.append(f"{workspace}: non-Rust file in formatting patch")
        if any(len(item.get("before_sha256", "")) != 64 or len(item.get("after_sha256", "")) != 64 or
               item.get("before_sha256") == item.get("after_sha256") for item in blobs):
            errors.append(f"{workspace}: missing or unchanged tracked blob digest")
        old = before["workspaces"].get(workspace, {})
        new = after["workspaces"].get(workspace, {})
        if old.get("revision") != pins[workspace] or new.get("revision") != pins[workspace]:
            errors.append(f"{workspace}: pinned child revision changed")
        if old.get("dirty") is not False or new.get("dirty") is not bool(paths):
            errors.append(f"{workspace}: child cleanliness differs from tracked patch")
        for key in ("lock_sha256", "nested_lock_sha256"):
            if old.get(key) != new.get(key):
                errors.append(f"{workspace}: {key} changed")
        if not old.get("lock_sha256") or not new.get("lock_sha256"):
            errors.append(f"{workspace}: canonical Cargo.lock missing")
        if workspace == "autoeq" and (not old.get("nested_lock_sha256") or not new.get("nested_lock_sha256")):
            errors.append("AutoEQ nested Cargo.lock missing")
        if paths:
            expected_root_dirty.add(f"m {workspace}")
    # checkout_sources.git() strips only the beginning of its multiline output;
    # gitlink worktree modifications therefore appear as `m name` (or ` m name`).
    actual_root_dirty = {line[1:] if line.startswith(" m ") else line for line in current["unexpected"]}
    if actual_root_dirty != expected_root_dirty or len(current["unexpected"]) != len(expected_root_dirty):
        errors.append("root contains unexpected, staged, or missing dirty gitlinks")
    return errors


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1" or sys.platform != "linux":
        print("Disposable Gitea Linux runner required", file=sys.stderr)
        return 2
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=True)
    (OUTPUT / "patches").mkdir(exist_ok=True)
    owned.OUTPUT = OUTPUT
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    owned.enable_subreaper()
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {"status": "RUNNING", "commands": [], "errors": [], "patches": []}
    before = None
    try:
        before = owned.snapshot(pins)
        report["before"] = before
        owned.save(report)
        report["errors"].extend(owned.source_errors(before, before, pins))
        if report["errors"]:
            return 1
        home = OUTPUT / "private-home"
        home.mkdir(exist_ok=True)
        (home / ".cargo").mkdir(exist_ok=True)
        env = os.environ.copy()
        original_home = Path.home()
        env.setdefault("CARGO_HOME", str(original_home / ".cargo"))
        env.setdefault("RUSTUP_HOME", str(original_home / ".rustup"))
        if not all(Path(env[key]).is_absolute() for key in ("CARGO_HOME", "RUSTUP_HOME")):
            raise ValueError("toolchain homes must be absolute")
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
                   XDG_CACHE_HOME=str(home / "cache"), XDG_DATA_HOME=str(home / "data"))
        for workspace in pins:
            if owned.STOP:
                raise KeyboardInterrupt("stopped before formatting")
            entry = owned.run_owned(f"fmt-{workspace}", ["bash", "-c", f"cd {workspace} && cargo fmt --all"], report, env)
            if entry["status"] != "PASS":
                report["errors"].append(f"{workspace} rustfmt command or cleanup failed")
                break
        for workspace in pins:
            patch = capture_patch(workspace)
            report["patches"].append(patch)
            if dirty_untracked(workspace):
                report["errors"].append(f"untracked files appeared in {workspace}")
            if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT / workspace).returncode != 0:
                report["errors"].append(f"staged change appeared in {workspace}")
    except KeyboardInterrupt:
        report["errors"].append("interrupted")
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if owned.STOP:
            report["errors"].append("interrupted")
        try:
            after = owned.snapshot(pins)
            report["after"] = after
            if before is not None:
                report["errors"].extend(format_errors(before, after, pins, report["patches"]))
        except Exception as error:
            report["errors"].append(f"after snapshot failed: {type(error).__name__}: {error}")
        report["status"] = "REVIEW_REQUIRED" if not owned.STOP and not report["errors"] and len(report["commands"]) == len(pins) else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "REVIEW_REQUIRED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
