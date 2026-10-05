#!/usr/bin/env python3
"""Qualify serial_test 4 synchronization on pinned DAW and systemwide sources."""
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

OUT = ROOT / "target/release-gitea/serial-test-4"
STOP = False
OWNED = nih_macos_artifact_check if sys.platform == "darwin" else nih_native_artifact_check
REQUIRED = {
    "engine-cache-entries": {
        "manager::tests::verified_rate_cache_stores_multiple_device_channel_entries",
    },
    "engine-cache-reuse": {
        "manager::tests::repeated_request_reuses_verified_fallback_without_reprobe",
    },
    "engine-resolver": {
        "decoder::core::tests::test_create_decoder_from_source_service_stream",
    },
    "plugin-reset": {
        "aud143_populated_lr24_reset_has_zero_allocations_control",
    },
    "daemon-concurrent": {
        "tests::testkit_concurrent_add_plugin_preserves_both_mutations",
    },
    "daemon-rack": {
        "tests::testkit_live_rack_state_promotion_and_graph_reorder_preserve_node_state",
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


def parse_tests(log: str, required: set[str]) -> dict:
    passed = re.findall(r"^test (\S+) \.\.\. ok$", log, re.MULTILINE)
    ignored = re.findall(r"^test (\S+) \.\.\. ignored", log, re.MULTILINE)
    summaries = re.findall(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", log, re.MULTILINE)
    if len(summaries) != 1:
        raise ValueError("expected exactly one libtest summary")
    verdict, count, failures, skipped = summaries[0]
    if verdict != "ok" or int(count) <= 0 or int(failures) != 0 or int(skipped) != len(ignored):
        raise ValueError("libtest summary is failing or incomplete")
    if int(count) != len(passed) or len(passed) != len(set(passed)):
        raise ValueError("named passing tests do not match summary")
    if set(passed) != required or ignored:
        raise ValueError(f"test inventory differs: expected {sorted(required)}, got {passed}, ignored {ignored}")
    return {"passed": passed, "ignored": ignored, "summary": summaries[0]}


def main() -> int:
    if sys.platform == "linux":
        if os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1" or not Path("/.dockerenv").exists() or Path("/dev/snd").exists():
            raise RuntimeError("Linux gate requires a disposable audio-device-free container")
    elif sys.platform == "darwin":
        if os.environ.get("SOTF_MAC_NONHARDWARE") != "1":
            raise RuntimeError("macOS gate requires the non-hardware QA lane")
    else:
        raise RuntimeError("serial-test 4 gate supports Linux and macOS only")
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
            ("engine-cache-entries", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-engine", "--lib", "verified_rate_cache_stores_multiple_device_channel_entries", "--", "--test-threads=2"]),
            ("engine-cache-reuse", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-engine", "--lib", "repeated_request_reuses_verified_fallback_without_reprobe", "--", "--test-threads=2"]),
            ("engine-resolver", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-engine", "--lib", "test_create_decoder_from_source_service_stream", "--", "--test-threads=2"]),
            ("plugin-reset", ["cargo", "test", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "-p", "sotf-plugins", "--test", "aud143_bandsplit_host_chain", "aud143_populated_lr24_reset_has_zero_allocations_control", "--", "--test-threads=2"]),
            ("daemon-concurrent", ["cargo", "test", "--locked", "--manifest-path", "sotf-systemwide/Cargo.toml", "-p", "sotf-daemon", "--bin", "sotf-daemon", "testkit_concurrent_add_plugin_preserves_both_mutations", "--", "--test-threads=2"]),
            ("daemon-rack", ["cargo", "test", "--locked", "--manifest-path", "sotf-systemwide/Cargo.toml", "-p", "sotf-daemon", "--bin", "sotf-daemon", "testkit_live_rack_state_promotion_and_graph_reorder_preserve_node_state", "--", "--test-threads=2"]),
        ]
        for name, argv in commands:
            entry = OWNED.run_owned(name, argv, report, os.environ.copy())
            if entry["status"] != "PASS":
                raise ValueError(f"{name} failed")
            entry["tests"] = parse_tests(Path(entry["log"]).read_text(errors="replace"), REQUIRED[name])
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
        report["status"] = "PASS" if len(report["commands"]) == 6 and not STOP and not OWNED.STOP and not report.get("failure") and not report["source_issues"] else "FAIL"
        save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
