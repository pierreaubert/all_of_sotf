#!/usr/bin/env python3
"""Run the Linux systemwide recipes inside a private, audio-device-free container."""

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
from scripts.release.qa import ROOT, source_issues, source_state


def snapshot() -> dict[str, object]:
    return source_state(ROOT, list(workspace_map()), "linux")


def run_check(name: str, argv: list[str], output: Path, runtime: Path, timeout: int) -> dict[str, object]:
    log = output / f"{name}.log"
    env = os.environ.copy()
    env.pop("SOTF_OUTPUT_DEVICE", None)
    env.pop("PULSE_COOKIE", None)
    env.pop("ALSA_CONFIG_PATH", None)
    env["SOTF_SYSTEMWIDE_STATE_PATH"] = str(runtime / "systemwide-state.json")
    env["SOTF_SYSTEMWIDE_RUNTIME_DIR"] = str(runtime / "systemwide")
    env["HOME"] = str(runtime / "home")
    env["XDG_CONFIG_HOME"] = str(runtime / "config")
    env["XDG_CACHE_HOME"] = str(runtime / "cache")
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env["PULSE_SERVER"] = f"unix:{runtime}/no-pulse-server"
    env["PULSE_RUNTIME_PATH"] = str(runtime)
    env["PIPEWIRE_REMOTE"] = "no-pipewire-server"
    env["PIPEWIRE_RUNTIME_DIR"] = str(runtime)
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime}/no-session-bus"
    env["JACK_NO_START_SERVER"] = "1"
    print(f"[{name}] {' '.join(argv)}", flush=True)
    interrupted = False
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            argv,
            cwd=ROOT / "sotf-systemwide",
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = 124
            print(f"[{name}] timed out", flush=True)
        except KeyboardInterrupt:
            status = 130
            interrupted = True
            print(f"[{name}] interrupted", flush=True)
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[{name}] owned process did not reap after SIGKILL", flush=True)
                status = 1
    text = log.read_text(encoding="utf-8", errors="replace")
    test_summaries = re.findall(r"^test result: (?:ok|FAILED)\..*$", text, re.MULTILINE)
    passed_tests = re.findall(r"^test (\S+) \.\.\. ok$", text, re.MULTILINE)
    result = {
        "name": name,
        "command": argv,
        "exit_code": status,
        "test_summaries": test_summaries,
        "passed_tests": passed_tests,
        "log": str(log.relative_to(ROOT)),
    }
    print(f"[{name}] exit={status}; test binaries={len(test_summaries)}", flush=True)
    if status:
        print("\n".join(text.splitlines()[-80:]), flush=True)
    if interrupted:
        raise KeyboardInterrupt(f"{name} interrupted after owned process cleanup")
    return result


def main() -> int:
    def interrupt(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    if len(sys.argv) != 2:
        print("usage: systemwide_linux_full_check.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    evidence = (ROOT / sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "sources.json").write_bytes((ROOT / "scripts/release/sources.json").read_bytes())
    (evidence / "root-revision.txt").write_text(
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True)
    )
    (evidence / "toolchain.txt").write_text(
        subprocess.check_output(["rustc", "--version"], text=True)
        + subprocess.check_output(["cargo", "--version"], text=True)
        + subprocess.check_output(["just", "--version"], text=True)
    )
    before = snapshot()
    (evidence / "sources-before.json").write_text(json.dumps(before, indent=2) + "\n")
    results: list[dict[str, object]] = []
    error: str | None = None
    issues: list[str] = []
    try:
        runtime = evidence / "private-runtime"
        runtime.mkdir(mode=0o700, exist_ok=False)
        for name in ("home", "config", "cache", "systemwide"):
            (runtime / name).mkdir(mode=0o700)
        if not Path("/.dockerenv").exists() or os.geteuid() != 0 or Path("/dev/snd").exists():
            raise RuntimeError("Linux systemwide QA requires a root-owned container without /dev/snd")
        (evidence / "isolation.json").write_text(json.dumps({
            "container_marker": Path("/.dockerenv").exists(),
            "root_owned": os.geteuid() == 0,
            "dev_snd_absent": not Path("/dev/snd").exists(),
            "private_runtime": str(runtime),
            "private_state": str(runtime / "systemwide-state.json"),
            "audio_servers": "private nonexistent PulseAudio/PipeWire endpoints; JACK autostart disabled",
            "device_streams": "no /dev/snd is mounted into the disposable container",
        }, indent=2) + "\n")
        initial_issues = source_issues(before, before, require_clean=True)
        if initial_issues:
            raise RuntimeError(f"source checkout is already dirty: {initial_issues}")
        results.append(run_check("check", ["just", "check"], evidence, runtime, 3600))
        results.append(run_check("qa", ["just", "qa"], evidence, runtime, 7200))
    except (KeyboardInterrupt, Exception) as exc:
        error = str(exc)
        print(f"runner error: {exc}", file=sys.stderr, flush=True)
    finally:
        try:
            after = snapshot()
            (evidence / "sources-after.json").write_text(json.dumps(after, indent=2) + "\n")
            issues = source_issues(before, after, require_clean=True)
        except Exception as exc:
            issues = [f"source guard failed: {exc}"]
        (evidence / "source-issues.json").write_text(json.dumps(issues, indent=2) + "\n")

    qa_summaries = results[1]["test_summaries"] if len(results) == 2 else []
    qa_tests = results[1]["passed_tests"] if len(results) == 2 else []
    required_safety_tests = (
        "testkit_concurrent_add_plugin_preserves_both_mutations",
        "testkit_idle_driver_config_change_updates_spec_without_engine_ready",
        "systemwide_lab_scenario_matrix_over_unix_socket",
        "systemwide_lab_restarts_with_a_fresh_coherent_snapshot",
        "decoder_retries_hal_reader_after_late_shared_memory_creation",
    )
    missing_safety_tests = [
        name for name in required_safety_tests
        if not any(test.endswith(name) for test in qa_tests)
    ]
    passed_counts = [
        int(match.group(1))
        for summary in qa_summaries
        if (match := re.search(r"(\d+) passed;", summary))
    ]
    positive_counts = len(passed_counts) == len(qa_summaries) and sum(passed_counts) > 0
    verdict = (
        "PASS"
        if not error and not issues and len(results) == 2
        and all(result["exit_code"] == 0 for result in results)
        and positive_counts and not missing_safety_tests
        and all(summary.startswith("test result: ok.") for summary in qa_summaries)
        else "FAIL"
    )
    (evidence / "report.json").write_text(
        json.dumps({"verdict": verdict, "results": results, "source_issues": issues,
                    "missing_safety_tests": missing_safety_tests, "error": error}, indent=2) + "\n"
    )
    print(f"Linux systemwide recipes: {verdict}", flush=True)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
