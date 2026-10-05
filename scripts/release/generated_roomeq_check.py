#!/usr/bin/env python3
"""Generate real AutoEQ RoomEQ artifacts and test the daemon's graph importer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import clean_group, enable_subreaper
from scripts.release.qa import ROOT, source_issues, source_state

INTERRUPTED = False


def write_report(path: Path, report: dict) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(path)


def run(name: str, argv: list[str], cwd: Path, log: Path, env: dict[str, str],
        report: dict, report_path: Path) -> dict:
    if INTERRUPTED:
        raise KeyboardInterrupt("interrupted before next command")
    with log.open("w", encoding="utf-8") as stream:
        child = None
        code = 130
        entry = {"name": name, "argv": argv, "exit_code": None, "status": "RUNNING",
                 "log": str(log.relative_to(ROOT))}
        try:
            report["active_command"] = entry
            write_report(report_path, report)
            child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            entry["owned_pgid"] = child.pid
            write_report(report_path, report)
            heartbeat = time.monotonic() + 30
            while not INTERRUPTED:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= heartbeat:
                        print(f"[{name}] still running; owned leader PID {child.pid}", flush=True)
                        heartbeat = time.monotonic() + 30
        except OSError as exc:
            entry["start_error"] = str(exc)
            code = 127
        finally:
            if child is not None:
                cleanup = clean_group(child)
            else:
                cleanup = {"ok": False, "remaining": [], "errors": ["command did not start"]}
            report.pop("active_command", None)
        entry.update({"exit_code": code, "cleanup_ok": cleanup["ok"],
                      "interrupted": INTERRUPTED, "owned_group_survivors": cleanup["remaining"],
                      "cleanup_inspection_errors": cleanup["errors"],
                      "status": "PASS" if code == 0 and cleanup["ok"] and not INTERRUPTED else "FAIL"})
        report["commands"].append(entry)
        write_report(report_path, report)
        return entry


def main() -> int:
    def interrupted(_signum: int, _frame: object) -> None:
        global INTERRUPTED
        INTERRUPTED = True

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    evidence = ROOT / "target/release-gitea/generated-roomeq-evidence"
    evidence.mkdir(parents=True, exist_ok=False)
    report_path = evidence / "report.json"
    root_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                            text=True).strip()
    manifest_sha256 = hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest()
    before = source_state(ROOT, list(workspace_map()), "linux")
    (evidence / "sources-before.json").write_text(json.dumps(before, indent=2))
    report: dict = {"status": "RUNNING", "root_revision": root_revision,
                    "sources_manifest_sha256": manifest_sha256,
                    "sources_before": before, "commands": [], "artifacts": [], "error": None}
    write_report(report_path, report)
    files: list[dict] = []
    error = None
    try:
        enable_subreaper()
        if not Path("/.dockerenv").exists() or os.geteuid() != 0 or Path("/dev/snd").exists():
            raise RuntimeError("audio-device-free disposable Linux container required")
        if source_issues(before, before, require_clean=True):
            raise RuntimeError("source checkout is not clean")
        _, _, pinned = read_manifest(ROOT / "scripts/release/sources.json")
        layout = root_layout_status(ROOT, pinned)
        report["root_layout_before"] = layout
        write_report(report_path, report)
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            raise RuntimeError(f"root layout is not exact pinned gitlinks: {layout}")
        for name, revision in pinned.items():
            if before[name]["revision"] != revision:
                raise RuntimeError(f"{name} checkout does not match pinned revision")
        with tempfile.TemporaryDirectory(prefix="roomeq-generated-") as private:
            private_root = Path(private)
            output = private_root / "artifacts"
            home = private_root / "home"
            runtime = private_root / "runtime"
            output.mkdir(mode=0o700)
            home.mkdir(mode=0o700)
            runtime.mkdir(mode=0o700)
            autoeq = ROOT / "autoeq"
            config = autoeq / "data_tests/roomeq/generate/fem/small_stereo_2_0/config.json"
            overrides = autoeq / "data_tests/roomeq/generate/optimiser-config/small_stereo_2_0"
            env = os.environ.copy()
            env.pop("SOTF_OUTPUT_DEVICE", None)
            env.pop("PULSE_COOKIE", None)
            env["HOME"] = str(home)
            env["XDG_RUNTIME_DIR"] = str(runtime)
            env["PULSE_SERVER"] = f"unix:{runtime}/no-pulse-server"
            env["PIPEWIRE_REMOTE"] = "no-pipewire-server"
            env["PIPEWIRE_RUNTIME_DIR"] = str(runtime)
            env["JACK_NO_START_SERVER"] = "1"
            for method in ("iir", "fir", "mixed"):
                artifact = output / f"dsp_{method}.json"
                argv = ["cargo", "run", "--locked", "--features", "cli", "--bin", "roomeq",
                        "--release", "--", "--config", str(config), "--override-config",
                        str(overrides / f"optimiser-{method}.json"), "--output", str(artifact)]
                result = run(f"generate-{method}", argv, autoeq,
                             evidence / f"generate-{method}.log", env, report, report_path)
                if result["exit_code"] or not result["cleanup_ok"]:
                    raise RuntimeError(f"AutoEQ {method} generator failed")
            # Retain the complete native bundles, including metadata and WAV
            # sidecars, before a failed handoff check can remove the tempdir.
            shutil.copytree(output, evidence / "generated-artifacts")
            published = sorted(path for path in output.rglob("*") if path.is_file())
            observed = [{"path": str(path.relative_to(output)), "bytes": path.stat().st_size}
                        for path in published]
            (evidence / "published-inventory.json").write_text(json.dumps(observed, indent=2))
            graph_handoff = private_root / "graph-handoff"
            graph_handoff.mkdir(mode=0o700)
            for method in ("iir", "fir", "mixed"):
                path = output / f"dsp_{method}.json"
                if path.is_symlink() or not path.is_file():
                    raise RuntimeError(f"missing canonical DSP output: {path.name}")
                data = path.read_bytes()
                if not data:
                    raise RuntimeError(f"empty generated artifact: {path.name}")
                copied = graph_handoff / path.name
                copied.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                if hashlib.sha256(copied.read_bytes()).hexdigest() != digest:
                    raise RuntimeError(f"graph handoff changed DSP bytes: {path.name}")
                files.append({"name": path.name, "bytes": len(data), "sha256": digest})
            report["artifacts"] = files
            write_report(report_path, report)
            if sorted(path.name for path in graph_handoff.rglob("*.json")) != [
                    "dsp_fir.json", "dsp_iir.json", "dsp_mixed.json"]:
                raise RuntimeError("expected exactly three generated DSP JSON artifacts")
            (evidence / "artifact-inventory.json").write_text(json.dumps(files, indent=2))
            env["SOTF_GENERATED_ROOM_EQ_DIR"] = str(graph_handoff)
            argv = ["cargo", "test", "--locked", "-p", "sotf-daemon", "--bin", "sotf-daemon",
                    "plugin_artifact::tests::all_generated_room_eq_files_build_graphs", "--",
                    "--ignored", "--exact"]
            result = run("systemwide-graph", argv, ROOT / "sotf-systemwide",
                         evidence / "systemwide-graph.log", env, report, report_path)
            if result["exit_code"] or not result["cleanup_ok"]:
                raise RuntimeError("generated RoomEQ graph test failed")
            text = (evidence / "systemwide-graph.log").read_text(errors="replace")
            if not re.search(r"test plugin_artifact::tests::all_generated_room_eq_files_build_graphs \.\.\. ok", text):
                raise RuntimeError("named ignored graph test did not run and pass")
            if not re.search(r"test result: ok\. 1 passed; 0 failed; 0 ignored;", text):
                raise RuntimeError("graph test summary did not report one passing test")
    except (KeyboardInterrupt, Exception) as exc:
        error = str(exc)
    issues = []
    after = None
    layout_after = None
    try:
        after = source_state(ROOT, list(workspace_map()), "linux")
        issues.extend(source_issues(before, after, require_clean=True))
        (evidence / "sources-after.json").write_text(json.dumps(after, indent=2))
        if INTERRUPTED:
            issues.append("job interrupted")
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip() != root_revision:
            issues.append("root revision changed")
        if hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest() != manifest_sha256:
            issues.append("source manifest changed")
        if "pinned" in locals():
            layout_after = root_layout_status(ROOT, pinned)
            if layout_after["missing"] or layout_after["unexpected"] or layout_after["allowed_siblings"]:
                issues.append(f"root layout changed: {layout_after}")
    except Exception as exc:
        issues.append(f"final source guard failed: {exc}")
    report.update({"status": "PASS" if not error and not issues else "FAIL",
                   "error": error, "source_issues": issues, "sources_after": after,
                   "root_layout_after": layout_after, "artifacts": files})
    write_report(report_path, report)
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
