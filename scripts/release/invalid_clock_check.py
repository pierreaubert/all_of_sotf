#!/usr/bin/env python3
"""Qualify live output-clock validation on the pinned DAW source."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import enable_subreaper
from scripts.release import nih_macos_artifact_check, nih_native_artifact_check

OUT = ROOT / "target/release-gitea/invalid-clock"
STOP = False
OWNED = nih_macos_artifact_check if sys.platform == "darwin" else nih_native_artifact_check
REQUIRED = {
    "engine-frame-format": {
        "engine::processing_thread::tests::frame_format::invalid_runtime_clock_returns_error_and_retires_the_host",
        "engine::processing_thread::tests::frame_format::rate_only_commit_discards_old_clock_pending_output",
    },
    "host-lib": {
        "host::tests::mixed_rate_timing::identity_graph_queries_live_output_rate_without_allocating",
        "host::tests::mixed_rate_timing::fractional_host_rate_reaches_both_clocks_without_integer_rounding",
        "host::tests::mixed_rate_timing::mixed_rate_processing_and_latent_event_splits_do_not_allocate",
        "host::tests::mixed_rate_timing::bypassed_rate_converter_keeps_downstream_clock_and_frame_count",
        "host::tests::mixed_rate_timing::fractional_and_buffered_clocks_follow_accepted_frames_through_drain",
        "host::tests::mixed_rate_timing::invalid_host_clock_is_refused_before_plugin_initialization",
    },
    "engine-clock-transition": {
        "engine::processing_thread::tests::crossfade_clock::invalid_prepared_clock_cannot_commit_or_replace_the_active_host",
        "engine::processing_thread::tests::crossfade_clock::prepared_integer_clock_is_reported_without_conversion",
        "engine::processing_thread::tests::crossfade_clock::crossfade_new_update_restarts_clock_and_empty_callbacks_preserve_it",
    },
}


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    OWNED.STOP = True


def save(report: dict) -> None:
    pending = OUT / "report.pending"
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(OUT / "report.json")


def snapshot(pins: dict[str, str]) -> dict:
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest(),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": qa.source_state(ROOT, list(workspace_map()), sys.platform.replace("darwin", "macos")),
    }


def source_errors(before: dict, after: dict, pins: dict[str, str]) -> list[str]:
    errors = qa.source_issues(before["workspaces"], after["workspaces"], True)
    if before["root_revision"] != after["root_revision"]:
        errors.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        errors.append("source manifest changed")
    for state in (before, after):
        layout = state["root_layout"]
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            errors.append(f"root gitlink layout differs: {layout}")
        if set(layout["tracked_gitlinks"]) != set(pins):
            errors.append("nine pinned gitlinks incomplete")
        for name, pin in pins.items():
            source = state["workspaces"].get(name, {})
            if source.get("revision") != pin or not source.get("lock_sha256"):
                errors.append(f"{name}: source or lock mismatch")
            if name == "autoeq" and not source.get("nested_lock_sha256"):
                errors.append("autoeq nested lock missing")
    if before["root_layout"] != after["root_layout"]:
        errors.append("root layout changed")
    return errors


HOST_MANUAL_IGNORE = {
    "analyzer_loudness_monitor::true_peak_tests::pre_aud123_published_kernel_cpu_control":
        "manual matched pre-AUD123 kernel-only CPU control; run with --ignored --nocapture",
}


def parse_tests(log: str, required: set[str], allowed_ignored: dict[str, str] | None = None) -> dict:
    passed = re.findall(r"^test (\S+)(?: - should panic)? \.\.\. ok$", log, re.MULTILINE)
    ignored = re.findall(r"^test (\S+) \.\.\. ignored, ([^\n]+)$", log, re.MULTILINE)
    expected_ignored = allowed_ignored or {}
    summaries = re.findall(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", log, re.MULTILINE)
    if len(summaries) != 1:
        raise ValueError("expected exactly one libtest summary")
    verdict, count, failures, skipped = summaries[0]
    if verdict != "ok" or int(count) <= 0 or int(failures) != 0 or int(skipped) != len(ignored):
        raise ValueError("libtest summary is failing or incomplete")
    if int(count) != len(passed) or len(passed) != len(set(passed)):
        raise ValueError("named passing tests do not match summary")
    if not required.issubset(set(passed)) or dict(ignored) != expected_ignored or len(ignored) != len(expected_ignored):
        raise ValueError(f"required tests missing or ignored inventory differs: {sorted(required - set(passed))}, {ignored}")
    limits = (["Pre-AUD123 kernel-only CPU control is manual and remains unqualified by this gate"]
              if expected_ignored else [])
    return {"passed": passed, "ignored": ignored, "summary": summaries[0], "coverage_limits": limits}


def main() -> int:
    if sys.platform == "linux":
        if os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1" or not Path("/.dockerenv").exists() or Path("/dev/snd").exists():
            raise RuntimeError("Linux gate requires a disposable audio-device-free container")
    elif sys.platform == "darwin":
        if os.environ.get("SOTF_MAC_NONHARDWARE") != "1":
            raise RuntimeError("macOS gate requires the non-hardware QA lane")
    else:
        raise RuntimeError("live output clock gate supports Linux and macOS only")
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "logs").mkdir()
    OWNED.OUTPUT = OUT
    OWNED.STOP = False
    enable_subreaper()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    before = snapshot(pins)
    report = {"status": "RUNNING", "source_before": before, "commands": []}
    save(report)
    try:
        if source_errors(before, before, pins):
            raise ValueError("pinned source preflight failed")
        commands = [
            ("engine-frame-format", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-engine", "--lib",
                                     "engine::processing_thread::tests::frame_format::", "--", "--test-threads=1"]),
            ("engine-clock-transition", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-engine", "--lib",
                                         "engine::processing_thread::tests::crossfade_clock::", "--", "--test-threads=1"]),
            ("host-lib", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-host", "--lib", "--", "--test-threads=1"]),
        ]
        for name, argv in commands:
            entry = OWNED.run_owned(name, argv, report, os.environ.copy())
            if entry["status"] != "PASS":
                raise ValueError(f"{name} failed")
            entry["tests"] = parse_tests(Path(entry["log"]).read_text(errors="replace"), REQUIRED[name],
                                         HOST_MANUAL_IGNORE if name == "host-lib" else {})
            save(report)
    except (Exception, KeyboardInterrupt) as error:
        report["failure"] = str(error)
    finally:
        try:
            after = snapshot(pins)
            report["source_after"] = after
            report["source_issues"] = source_errors(before, after, pins)
        except Exception as error:
            report["source_issues"] = [f"final source snapshot failed: {error}"]
        report["status"] = "PASS" if len(report["commands"]) == 3 and not STOP and not OWNED.STOP and not report.get("failure") and not report["source_issues"] else "FAIL"
        save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
