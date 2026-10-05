#!/usr/bin/env python3
"""Repeat the unchanged AAE release QA on an otherwise idle Linux runner."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import enable_subreaper
from scripts.release import nih_native_artifact_check as owned

OUT = ROOT / "target/release-gitea/aae-isolated-linux"
STOP = False


def stop(_signal: int, _frame: object) -> None:
    global STOP
    STOP = True
    owned.STOP = True


def write(report: dict) -> None:
    pending = OUT / "report.pending"
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(OUT / "report.json")


def snapshot(pins: dict[str, str]) -> dict:
    source = ROOT / "scripts/release/sources.json"
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": qa.source_state(ROOT, list(workspace_map()), "linux"),
    }


def issues(before: dict, after: dict, pins: dict[str, str]) -> list[str]:
    result = qa.source_issues(before["workspaces"], after["workspaces"], True)
    if before["root_revision"] != after["root_revision"]:
        result.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        result.append("source manifest changed")
    for state in (before, after):
        layout = state["root_layout"]
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            result.append(f"root gitlink layout differs: {layout}")
        if set(layout["tracked_gitlinks"]) != set(pins):
            result.append("pinned nine-source gitlink inventory incomplete")
        for name, pin in pins.items():
            source = state["workspaces"].get(name, {})
            if source.get("revision") != pin or not source.get("lock_sha256"):
                result.append(f"{name}: source pin or lock mismatch")
            if name == "autoeq" and not source.get("nested_lock_sha256"):
                result.append("autoeq: nested lock missing")
    if before["root_layout"] != after["root_layout"]:
        result.append("root gitlink layout changed")
    return result


def telemetry() -> dict:
    paths = ("/sys/fs/cgroup/cpu.stat", "/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/cpuset.cpus.effective")
    values = {path: Path(path).read_text().strip() if Path(path).is_file() else None for path in paths}
    values["affinity"] = sorted(os.sched_getaffinity(0))
    values["processes"] = subprocess.check_output(["ps", "-eo", "pid=,ppid=,pgid=,comm="], text=True).splitlines()
    values["loadavg"] = Path("/proc/loadavg").read_text().strip()
    return values


def quiet_window() -> dict:
    # This checks the owned container immediately before a benchmark. The
    # dispatcher must separately confirm no other Gitea jobs share its host.
    start = telemetry()
    time.sleep(3)
    end = telemetry()
    busy = [row for row in end["processes"] if re.search(r"\b(cargo|rustc|qa-aae)\b", row)]
    throttle = throttled_delta(start, end)
    evidence = {"start": start, "end": end, "visible_competitors": busy,
                "nr_throttled_delta": throttle,
                "host_sibling_jobs_visible": False}
    if STOP or owned.STOP or busy or throttle is None or throttle != 0:
        raise ValueError(f"container not quiet immediately before AAE benchmark: {evidence}")
    return evidence


def run_once(index: int, report: dict, argv: list[str]) -> dict:
    if STOP or owned.STOP:
        raise KeyboardInterrupt("interrupted before launch")
    quiet = quiet_window() if index else None
    before = telemetry()
    entry = owned.run_owned(f"qa-aae-{index}", argv, report, os.environ.copy())
    entry["quiet_window"] = quiet
    entry["telemetry_before"] = before
    entry["telemetry_after"] = telemetry()
    entry["cgroup_throttled_delta"] = throttled_delta(before, entry["telemetry_after"])
    write(report)
    return entry


def throttled_delta(before: dict, after: dict) -> int | None:
    def count(state: dict) -> int | None:
        value = state["/sys/fs/cgroup/cpu.stat"]
        if value is None:
            return None
        match = re.search(r"^nr_throttled (\d+)$", value, re.MULTILINE)
        return int(match.group(1)) if match else None
    start, end = count(before), count(after)
    return end - start if start is not None and end is not None else None


def qa_result(log: str) -> dict:
    numbers = re.findall(r"^\[Test (\d+)\]", log, re.MULTILINE)
    if numbers != [str(i) for i in range(1, 11)]:
        raise ValueError("AAE QA lacks the exact ten ordered tests")
    labels = re.findall(r"^  ([^\n:]+): PASS$", log, re.MULTILINE)
    expected = ["Reverb Tail", "Channel Energy Distribution", "RT60 Parameter",
                "12-channel processing", "Bypass Transparency", "No NaN/Inf",
                "Energy Bounded", "Latency", "Zero Allocations", "Performance"]
    if labels != expected or re.search(r"^  [^\n:]+: (?:FAIL|ERROR)$", log, re.MULTILINE):
        raise ValueError(f"AAE QA positive inventory differs: {labels}")
    usage = re.findall(r"Estimated CPU Usage: ([0-9.]+)%", log)
    callback = re.findall(r"callback p50/p95/max: ([0-9.]+)/([0-9.]+)/([0-9.]+) ms \(deadline ([0-9.]+) ms\)", log)
    if len(usage) != 1 or len(callback) != 1:
        raise ValueError("AAE performance telemetry missing or ambiguous")
    cpu = float(usage[0])
    p50, p95, maximum, deadline = map(float, callback[0])
    if not (cpu < 5.0 and maximum < deadline and p50 <= p95 <= maximum):
        raise ValueError("AAE original performance thresholds failed")
    return {"tests": numbers, "pass_labels": labels, "estimated_cpu_percent": cpu,
            "callback_ms": {"p50": p50, "p95": p95, "max": maximum, "deadline": deadline}}


def main() -> int:
    if os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1" or not Path("/.dockerenv").exists() or Path("/dev/snd").exists():
        raise RuntimeError("AAE diagnostic requires a disposable audio-device-free Gitea container")
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "logs").mkdir()
    owned.OUTPUT = OUT
    owned.STOP = False
    enable_subreaper()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    before = snapshot(pins)
    report = {"status": "RUNNING", "source_before": before, "commands": []}
    write(report)
    try:
        preflight = issues(before, before, pins)
        if preflight:
            raise ValueError(f"source preflight failed: {preflight}")
        build = run_once(0, report, ["cargo", "build", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "--release", "-p", "sotf-plugin-aae", "--bin", "qa-aae", "--features", "qa"])
        if build["status"] != "PASS":
            raise ValueError("AAE release binary build failed")
        # Exact first command of sotf-plugins/Justfile:qa-plugins-diagnostics.
        recipe = ["cargo", "run", "--locked", "--manifest-path", "sotf-daw/Cargo.toml", "--release", "-p", "sotf-plugin-aae", "--bin", "qa-aae", "--features", "qa"]
        for index in range(1, 4):
            entry = run_once(index, report, recipe)
            try:
                entry["qa"] = qa_result(Path(entry["log"]).read_text(errors="replace"))
            except ValueError as error:
                entry["qa_error"] = str(error)
            write(report)
            if STOP or owned.STOP or not entry["owned_group_cleanup"]["ok"]:
                raise ValueError(f"AAE QA run {index} did not clean its owned process group")
        if any(entry["status"] != "PASS" or entry.get("qa_error") for entry in report["commands"][1:]):
            raise ValueError("one or more AAE QA repetitions failed")
    except (Exception, KeyboardInterrupt) as error:
        report["failure"] = str(error)
    finally:
        try:
            after = snapshot(pins)
            report["source_after"] = after
            report["source_issues"] = issues(before, after, pins)
        except Exception as error:
            report["source_issues"] = [f"final source snapshot failed: {error}"]
        report["status"] = "PASS" if len(report["commands"]) == 4 and not STOP and not owned.STOP and not report.get("failure") and not report["source_issues"] else "FAIL"
        write(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
