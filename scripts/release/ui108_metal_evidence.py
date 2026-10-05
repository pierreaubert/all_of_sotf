#!/usr/bin/env python3
"""Retain strict 108-case Metal baseline, actual and diff evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
from scripts.release import nih_macos_artifact_check as owned
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import enable_subreaper

OUTPUT = ROOT / "target/release-gitea/ui108-metal"
ARCHIVE_SHA = "0bedd66ab4425f92e2a0f6e0451f63450081086a6b76c7b3902f9b2dd222c45f"
FEATURES = "autoeq,gpu-2d,gpu-3d,reqwest,showcase,spinorama,tokio,urlencoding"
STOP = False


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    owned.interrupted(_signum, _frame)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if (len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n"
            or header[12:16] != b"IHDR"):
        raise ValueError(f"invalid PNG header: {path}")
    return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")


def save(report: dict) -> None:
    pending = OUTPUT / "report.json.pending"
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(OUTPUT / "report.json")


def snapshot(pins: dict[str, str]) -> dict:
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": digest(ROOT / "scripts/release/sources.json"),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": qa.source_state(ROOT, list(workspace_map()), "macos"),
    }


def source_errors(before: dict, after: dict, pins: dict[str, str]) -> list[str]:
    errors = qa.source_issues(before["workspaces"], after["workspaces"], True)
    if before["root_revision"] != after["root_revision"]:
        errors.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        errors.append("sources.json changed")
    if before["root_layout"] != after["root_layout"]:
        errors.append("root checkout layout changed")
    for label, state in (("before", before), ("after", after)):
        layout = state["root_layout"]
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            errors.append(f"{label}: root layout differs from pinned gitlinks: {layout}")
        if set(layout["tracked_gitlinks"]) != set(pins):
            errors.append(f"{label}: nine pinned gitlinks are incomplete")
        for name, revision in pins.items():
            item = state["workspaces"].get(name, {})
            if item.get("revision") != revision or not item.get("lock_sha256"):
                errors.append(f"{label}: {name} revision or lock differs from pin")
            if name == "autoeq" and not item.get("nested_lock_sha256"):
                errors.append(f"{label}: AutoEQ nested lock is missing")
    return errors


def run_owned(name: str, argv: list[str], cwd: Path, env: dict[str, str],
              report: dict) -> dict:
    # The reviewed helper owns the exact process group exercised by its seven
    # supervisor regressions. Positional arguments keep CWD and argv separate
    # from the shell program; exec retains the command in that owned group.
    wrapper = ["bash", "-c", 'cd "$1" || exit 1; shift; exec "$@"',
               "ui108", str(cwd), *argv]
    return owned.run_owned(name, wrapper, report, env)


def cases(data: dict, kind: str) -> list[dict]:
    if data.get("report_type") != kind or not isinstance(data.get("cases"), list):
        raise ValueError(f"{kind}: wrong report type or cases")
    return data["cases"]


def evidence(report: dict, visual_root: Path, archive: Path) -> None:
    gpui = ROOT / "gpui-toolkit"
    env = os.environ.copy()
    original_home = Path.home()
    env.setdefault("CARGO_HOME", str(original_home / ".cargo"))
    env.setdefault("RUSTUP_HOME", str(original_home / ".rustup"))
    private = OUTPUT / "private-home"
    private.mkdir(exist_ok=True)
    env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
               XDG_CACHE_HOME=str(private / "cache"), XDG_DATA_HOME=str(private / "data"),
               PULSE_SERVER=f"unix:{OUTPUT}/no-pulse", PIPEWIRE_REMOTE="no-pipewire",
               JACK_NO_START_SERVER="1", QA_VISUAL_UPDATE_BASELINES="0")
    (private / ".cargo").mkdir(exist_ok=True)
    if digest(archive) != ARCHIVE_SHA:
        raise ValueError("reviewed baseline archive hash differs")
    report["baseline_archive_sha256"] = ARCHIVE_SHA
    listing = run_owned("baseline-list", ["tar", "-tf", str(archive)], gpui, env, report)
    if listing["status"] != "PASS":
        raise ValueError("baseline archive listing failed")
    names = Path(listing["log"]).read_text().splitlines()
    png_names = [name for name in names if name.endswith(".png")]
    if (len(names) != 110 or len(png_names) != 108 or len(set(names)) != len(names)
            or any(not name.startswith("metal/baseline/") or ".." in Path(name).parts
                   for name in png_names)
            or set(names) - set(png_names) != {"metal/", "metal/baseline/"}):
        raise ValueError("original archive entry inventory differs from 108 PNGs")
    extracted = run_owned("baseline-extract",
                          ["tar", "-xf", str(archive), "-C", str(visual_root)], gpui, env, report)
    if extracted["status"] != "PASS":
        raise ValueError("baseline extraction failed")
    baseline_files = [visual_root / name for name in png_names]
    if (any(path.is_symlink() or not path.is_file()
            or not path.resolve().is_relative_to(visual_root.resolve()) for path in baseline_files)
            or (visual_root / "metal").is_symlink()
            or (visual_root / "metal/baseline").is_symlink()):
        raise ValueError("original baseline PNG missing, linked or outside evidence")
    baseline = {str(path.resolve()) for path in baseline_files}
    baseline_hashes = {path: digest(Path(path)) for path in baseline}
    manifest_path = OUTPUT / "component-lab-manifest.json"
    base_args = ["cargo", "run", "--locked", "-p", "gpui-component-lab",
                 "--bin", "gpui-component-lab", "--features", FEATURES, "--"]
    manifest_run = run_owned("manifest", base_args + [
        "--visual-output-root", str(visual_root), "--visual-renderer", "metal",
        "--visual-pixel-scale", "2", "--visual-manifest-json", str(manifest_path),
        "--visual-manifest-markdown", str(OUTPUT / "component-lab-manifest.md")],
        gpui, env, report)
    if manifest_run["status"] != "PASS":
        raise ValueError("component-lab manifest failed")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != 2 or manifest.get("renderer_id") != "metal":
        raise ValueError("Metal manifest schema or renderer differs")
    selected = [case for case in manifest["cases"]
                if case["story_id"].startswith("px.mesh_plot")]
    ids = [case["capture_id"] for case in selected]
    if (len(ids) != 108 or len(set(ids)) != 108
            or any(case.get("renderer_id") != "metal" or case.get("pixel_scale") != 2
                   for case in selected)):
        raise ValueError("MeshPlot manifest does not contain 108 unique IDs")
    expected_baselines = {str((gpui / case["baseline_path"]).resolve()) for case in selected}
    if expected_baselines != baseline:
        raise ValueError("manifest baseline path set differs from original archive")
    selected_args = sum((["--visual-case", item] for item in ids), [])
    capture_path = OUTPUT / "component-lab-capture.json"
    capture_args = ["cargo", "run", "--locked", "-p", "gpui-component-lab",
                    "--bin", "gpui-component-lab", "--features", FEATURES + ",visual-capture", "--"]
    capture = run_owned("capture", capture_args + [
        "--visual-capture", "--visual-capture-limit", "0", "--visual-gallery",
        "--visual-output-root", str(visual_root), "--visual-renderer", "metal",
        "--visual-pixel-scale", "2", "--visual-capture-json", str(capture_path),
        "--visual-capture-markdown", str(OUTPUT / "component-lab-capture.md")] + selected_args,
        gpui, env, report)
    capture_report = json.loads(capture_path.read_text())
    captured = cases(capture_report, "gpui-component-lab-render-capture")
    if (capture_report.get("renderer_id") != "metal" or capture_report.get("passed") is not True
            or capture_report.get("requested_count") != 108
            or capture_report.get("captured_count") != 108
            or capture_report.get("failed_count") != 0
            or len(captured) != 108
            or {case["capture_id"] for case in captured} != set(ids)
            or any(case.get("status") != "Captured" for case in captured)
            or not capture["owned_group_cleanup"]["ok"]):
        raise ValueError("real Metal capture inventory is incomplete")
    diff_path = OUTPUT / "component-lab-diff.json"
    diff = run_owned("diff", base_args + [
        "--visual-output-root", str(visual_root), "--visual-renderer", "metal",
        "--visual-pixel-scale", "2", "--visual-diff", "--visual-diff-limit", "0",
        "--visual-diff-max-changed-pixels", "0", "--visual-diff-json", str(diff_path),
        "--visual-diff-markdown", str(OUTPUT / "component-lab-diff.md")] + selected_args,
        gpui, env, report)
    differences = json.loads(diff_path.read_text())
    compared = cases(differences, "gpui-component-lab-visual-diff")
    image_ledger = {}
    if len(compared) != 108 or {case["capture_id"] for case in compared} != set(ids):
        raise ValueError("visual diff report inventory differs from 108 cases")
    manifest_by_id = {case["capture_id"]: case for case in selected}
    for case in compared:
        expected = manifest_by_id[case["capture_id"]]
        dimensions = (expected["viewport_width"] * 2, expected["viewport_height"] * 2)
        for label in ("baseline_path", "actual_path", "diff_path"):
            raw_path = gpui / case[label]
            path = raw_path.resolve()
            if (raw_path.is_symlink() or not path.is_relative_to(visual_root.resolve())
                    or not path.is_file()):
                raise ValueError(f"{case['capture_id']}: {label} missing or outside evidence")
            if case[label] != expected[label] or png_dimensions(path) != dimensions:
                raise ValueError(f"{case['capture_id']}: {label} path or dimensions differ")
            image_ledger[str(path.relative_to(visual_root))] = digest(path)
    report["images"] = image_ledger
    if {path: digest(Path(path)) for path in baseline} != baseline_hashes:
        raise ValueError("original extracted baseline PNG bytes changed during capture or diff")
    report["diff"] = {"passed": differences.get("passed"),
                      "failed_count": differences.get("failed_count"),
                      "compared_count": differences.get("compared_count"),
                      "max_changed_pixels": differences.get("max_changed_pixels")}
    save(report)
    if len(image_ledger) != 324 or any(case.get("status") != "Passed" or case.get("changed_pixels") != 0
                                       for case in compared):
        raise ValueError("one or more original baseline pixels differ")
    if (differences.get("passed") is not True or differences.get("failed_count") != 0
            or differences.get("compared_count") != 108
            or differences.get("max_changed_pixels") != 0
            or diff["status"] != "PASS" or capture["status"] != "PASS"):
        raise ValueError("strict zero-pixel Metal comparison failed")


def main() -> int:
    if (os.environ.get("CI") != "true" or os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1"
            or sys.platform != "darwin" or platform.machine() != "arm64"
            or sys.flags.optimize != 0):
        print("disposable unoptimized Gitea Apple Silicon runner required", file=sys.stderr)
        return 2
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    owned.OUTPUT = OUTPUT
    enable_subreaper()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=False)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {"status": "RUNNING", "commands": [], "errors": []}
    before = None
    try:
        before = snapshot(pins)
        report["before"] = before
        save(report)
        report["errors"].extend(source_errors(before, before, pins))
        if report["errors"]:
            return 1
        visual_root = OUTPUT / "component-lab"
        visual_root.mkdir()
        archive = ROOT / "gpui-toolkit/qa/visual/baselines/component-lab-metal-pr-v1.tar.zst"
        evidence(report, visual_root, archive)
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if STOP:
            report["errors"].append("interrupted")
        try:
            after = snapshot(pins)
            report["after"] = after
            if before is not None:
                report["errors"].extend(source_errors(before, after, pins))
        except Exception as error:
            report["errors"].append(f"after snapshot: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not report["errors"] and not STOP else "FAIL"
        save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
