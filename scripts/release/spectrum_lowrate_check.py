#!/usr/bin/env python3
"""Check Spectrum Analyzer low-rate host and native CLAP behavior on Gitea."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.clap_activation_matrix_check import RATES, run_case
from scripts.release.qa import ROOT, source_issues, source_state

HOST_TESTS = {
    "initialize_rejects_zero_rate_and_minimum_above_nyquist",
    "requested_maximum_survives_low_rate_and_frequency_labels_follow_reinitialization",
    "low_rate_tone_uses_effective_bins_without_old_rate_history",
}


def snapshot() -> dict:
    return source_state(ROOT, list(workspace_map()), "linux")


def stop_group(child: subprocess.Popen) -> bool:
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            child.wait(timeout=1)
            return True
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            continue
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return True
    return False


def run_host(command: list[str], log: Path) -> tuple[int, bool]:
    with log.open("w", encoding="utf-8") as stream:
        child = subprocess.Popen(command, cwd=ROOT / "sotf-daw", stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = child.wait(timeout=1200)
            return code, stop_group(child)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            if not stop_group(child):
                raise RuntimeError("sotf-host test process group did not stop")
            raise


def main() -> int:
    def interrupted(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    if len(sys.argv) != 2:
        print("usage: spectrum_lowrate_check.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    evidence = ROOT / sys.argv[1]
    (evidence / "logs").mkdir(parents=True, exist_ok=False)
    (evidence / "sources.json").write_bytes((ROOT / "scripts/release/sources.json").read_bytes())
    (evidence / "root-revision.txt").write_text(
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
    )
    (evidence / "toolchain.txt").write_text(
        subprocess.check_output(["rustc", "--version"], text=True)
        + subprocess.check_output(["cargo", "--version"], text=True)
    )
    before = snapshot()
    (evidence / "sources-before.json").write_text(json.dumps(before, indent=2) + "\n")
    results: dict = {}
    errors: list[str] = []
    try:
        errors.extend(source_issues(before, before, require_clean=True))
        if errors:
            raise RuntimeError("pinned source checkout is dirty")
        host_command = ["cargo", "test", "--locked", "-p", "sotf-host", "--lib",
                        "analyzer_spectrum::tests::", "--", "--show-output", "--test-threads=1"]
        host_log = evidence / "logs" / "sotf-host-analyzer.log"
        try:
            host_exit, host_cleanup = run_host(host_command, host_log)
        except subprocess.TimeoutExpired:
            host_exit = 124
            host_cleanup = True
            errors.append("sotf-host analyzer tests timed out")
        output = host_log.read_text(encoding="utf-8", errors="replace")
        passed = set(re.findall(r"^test ([^\n ]+) \.\.\. ok$", output, flags=re.MULTILINE))
        named = {test for test in HOST_TESTS if any(item.endswith("::" + test) for item in passed)}
        results["host"] = {"command": host_command, "exit_code": host_exit,
                           "cleanup_ok": host_cleanup,
                           "named_passed": sorted(named), "positive_count": len(passed),
                           "log": str(host_log.relative_to(ROOT))}
        if host_exit or not host_cleanup or named != HOST_TESTS or not passed:
            errors.append("sotf-host analyzer tests or three named low-rate cases failed")
        native = run_case("spectrum-analyzer", "spectrum_analyzer_activation_matrix",
                          evidence / "logs" / "spectrum-native-clap.log")
        results["native_clap"] = native
        if (native["exit_code"] != 0 or native["test_result"] != "ok"
                or not native["exact_rates"] or not native["positive_control"]
                or tuple(row["rate"] for row in native["outcomes"]) != RATES
                or not all(row["initialized"] and row["activated"] for row in native["outcomes"])):
            errors.append("Spectrum native CLAP activation did not pass all 13 rates")
    except KeyboardInterrupt as error:
        errors.append(f"interrupted: {error}")
    except Exception as error:
        errors.append(f"runner error: {error}")
    finally:
        try:
            after = snapshot()
            (evidence / "sources-after.json").write_text(json.dumps(after, indent=2) + "\n")
            errors.extend(source_issues(before, after, require_clean=True))
        except Exception as error:
            errors.append(f"source after-state unavailable: {error}")
        report = {"status": "PASS" if not errors else "FAIL", "results": results,
                  "errors": errors, "required_host_tests": sorted(HOST_TESTS), "rates": RATES}
        (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
