#!/usr/bin/env python3
"""Run the Linux systemwide recipes inside a private, audio-device-free container."""

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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.qa import ROOT, source_issues, source_state
from scripts.release.librespot_candidate_check import clean_group, enable_subreaper
from scripts.release.checkout_sources import read_manifest, root_layout_status


STOP = False


def save(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def snapshot() -> dict[str, object]:
    return source_state(ROOT, list(workspace_map()), "linux")


def positive_qa_inventory(summaries: list[str]) -> tuple[bool, int]:
    if not summaries:
        return False, 0
    passed = 0
    ignored = 0
    for summary in summaries:
        if not summary.startswith("test result: ok."):
            return False, ignored
        passed_match = re.search(r"(\d+) passed;", summary)
        failed_match = re.search(r";\s*(\d+) failed;", summary)
        ignored_match = re.search(r";\s*(\d+) ignored;", summary)
        if passed_match is None or failed_match is None or ignored_match is None:
            return False, ignored
        if int(failed_match.group(1)) != 0:
            return False, ignored
        passed += int(passed_match.group(1))
        ignored += int(ignored_match.group(1))
    # The single fixture-dependent RoomEQ case is proved by the required
    # generated-artifact step before this full QA recipe runs.
    return passed > 0 and ignored <= 1, ignored


def generated_coverage(generated: dict | None, current: dict, root_revision: str,
                       manifest: bytes, root_layout: dict, evidence: Path) -> list[str]:
    issues: list[str] = []
    if not isinstance(generated, dict) or generated.get("status") != "PASS":
        return ["generated RoomEQ report is missing or not PASS"]
    if generated.get("root_revision") != root_revision:
        issues.append("generated RoomEQ root revision differs")
    if generated.get("sources_manifest_sha256") != hashlib.sha256(manifest).hexdigest():
        issues.append("generated RoomEQ source manifest differs")
    if generated.get("source_issues") != []:
        issues.append("generated RoomEQ source guard did not pass")
    if (generated.get("root_layout_before") != root_layout
            or generated.get("root_layout_after") != root_layout):
        issues.append("generated RoomEQ root layout differs")
    for phase in ("sources_before", "sources_after"):
        sources = generated.get(phase)
        if (not isinstance(sources, dict) or set(sources) != set(current)
                or any(not isinstance(item, dict) for item in sources.values())):
            issues.append(f"generated RoomEQ {phase} inventory differs")
            continue
        for name, state in current.items():
            for key in ("revision", "dirty", "lock_sha256", "nested_lock_sha256"):
                if sources[name].get(key) != state.get(key):
                    issues.append(f"generated RoomEQ {phase} differs: {name}/{key}")
    commands = generated.get("commands")
    expected_commands = ["generate-iir", "generate-fir", "generate-mixed", "systemwide-graph"]
    if (not isinstance(commands, list) or len(commands) != 4
            or any(not isinstance(item, dict) for item in commands)
            or [item.get("name") for item in commands] != expected_commands):
        issues.append("generated RoomEQ did not run all four commands")
    elif any(item.get("status") != "PASS" or item.get("exit_code") != 0
             or item.get("cleanup_ok") is not True
             or item.get("owned_group_survivors") != [] for item in commands):
        issues.append("generated RoomEQ command or owned cleanup failed")
    artifacts = generated.get("artifacts")
    expected_artifacts = {f"dsp_{mode}.json" for mode in ("iir", "fir", "mixed")}
    if (not isinstance(artifacts, list) or len(artifacts) != 3
            or any(not isinstance(item, dict) for item in artifacts)
            or {item.get("name") for item in artifacts} != expected_artifacts):
        issues.append("generated RoomEQ JSON inventory differs")
    else:
        for item in artifacts:
            path = evidence / "generated-artifacts" / item["name"]
            data = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
            if (not data or len(data) != item.get("bytes")
                    or hashlib.sha256(data).hexdigest() != item.get("sha256")):
                issues.append(f"generated RoomEQ retained bytes differ: {item['name']}")
    graph_log = evidence / "systemwide-graph.log"
    if not graph_log.is_file():
        issues.append("generated RoomEQ native test log is missing")
    else:
        text = graph_log.read_text(encoding="utf-8", errors="replace")
        if not re.search(
            r"(?m)^test plugin_artifact::tests::all_generated_room_eq_files_build_graphs \.\.\. ok$",
            text,
        ) or not re.search(r"test result: ok\. 1 passed; 0 failed; 0 ignored;", text):
            issues.append("generated RoomEQ native test lacks one named positive result")
    return issues


def run_check(name: str, argv: list[str], output: Path, runtime: Path,
              report: dict[str, object]) -> dict[str, object]:
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
    if STOP:
        raise KeyboardInterrupt("interrupted before command launch")
    entry: dict[str, object] = {
        "name": name, "command": argv, "log": str(log.relative_to(ROOT)),
        "status": "RUNNING",
    }
    report["active_command"] = entry
    save(output / "report.json", report)
    with log.open("w", encoding="utf-8") as stream:
        if STOP:
            report.pop("active_command", None)
            save(output / "report.json", report)
            raise KeyboardInterrupt("interrupted before process launch")
        process = subprocess.Popen(
            argv,
            cwd=ROOT / "sotf-systemwide",
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        status = 130
        try:
            entry["owned_pgid"] = process.pid
            save(output / "report.json", report)
            heartbeat = time.monotonic()
            while not STOP:
                try:
                    status = process.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - heartbeat >= 30:
                        print(f"[{name}] still running", flush=True)
                        heartbeat = time.monotonic()
        finally:
            entry["cleanup"] = clean_group(process)
    text = log.read_text(encoding="utf-8", errors="replace")
    test_summaries = re.findall(r"^test result: (?:ok|FAILED)\..*$", text, re.MULTILINE)
    passed_tests = re.findall(r"^test (\S+) \.\.\. ok$", text, re.MULTILINE)
    ignored_tests = re.findall(r"^test (\S+) \.\.\. ignored(?:,.*)?$", text, re.MULTILINE)
    result = dict(entry)
    result.update({"exit_code": status, "test_summaries": test_summaries,
                   "passed_tests": passed_tests, "ignored_tests": ignored_tests,
                   "status": "PASS" if status == 0 and entry["cleanup"]["ok"] else "FAIL"})
    report["results"].append(result)
    report.pop("active_command", None)
    save(output / "report.json", report)
    print(f"[{name}] exit={status}; test binaries={len(test_summaries)}", flush=True)
    if status:
        print("\n".join(text.splitlines()[-80:]), flush=True)
    if STOP:
        raise KeyboardInterrupt(f"{name} interrupted after owned process cleanup")
    return result


def main() -> int:
    def interrupt(signum: int, _frame: object) -> None:
        global STOP
        STOP = True
        print(f"interruption requested by signal {signum}", flush=True)

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    if len(sys.argv) != 2:
        print("usage: systemwide_linux_full_check.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    evidence = (ROOT / sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"status": "RUNNING", "results": []}
    save(evidence / "report.json", report)
    before: dict[str, object] | None = None
    root_before: dict[str, object] | None = None
    root_revision_before: str | None = None
    manifest_before: bytes | None = None
    results: list[dict[str, object]] = []
    error: str | None = None
    issues: list[str] = []
    generated_report: dict | None = None
    generated_evidence = ROOT / "target/release-gitea/generated-roomeq-evidence"
    try:
        enable_subreaper()
        if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
            raise RuntimeError("CI=true and DISPOSABLE=1 are required")
        (evidence / "sources.json").write_bytes((ROOT / "scripts/release/sources.json").read_bytes())
        manifest_before = (ROOT / "scripts/release/sources.json").read_bytes()
        _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
        root_before = root_layout_status(ROOT, pins)
        root_revision_before = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        report["root_status_before"] = root_before
        report["root_revision_before"] = root_revision_before
        save(evidence / "report.json", report)
        (evidence / "root-revision.txt").write_text(root_revision_before + "\n")
        (evidence / "toolchain.txt").write_text(
            subprocess.check_output(["rustc", "--version"], text=True)
            + subprocess.check_output(["cargo", "--version"], text=True)
            + subprocess.check_output(["just", "--version"], text=True)
        )
        before = snapshot()
        save(evidence / "sources-before.json", before)
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
        if root_before["missing"] or root_before["unexpected"]:
            initial_issues.append("root checkout has missing or unexpected paths")
        for name, revision in pins.items():
            if before.get(name, {}).get("revision") != revision:
                initial_issues.append(f"{name}: source pin mismatch")
        if initial_issues:
            raise RuntimeError(f"source checkout is already dirty: {initial_issues}")
        generated_report = json.loads((generated_evidence / "report.json").read_text())
        generated_issues = generated_coverage(
            generated_report, before, root_revision_before, manifest_before,
            root_before, generated_evidence,
        )
        if generated_issues:
            raise RuntimeError(f"generated RoomEQ prerequisite failed: {generated_issues}")
        report["generated_roomeq_report"] = str(generated_evidence / "report.json")
        save(evidence / "report.json", report)
        if STOP:
            raise KeyboardInterrupt("interrupted before command launch")
        results.append(run_check("check", ["just", "check"], evidence, runtime, report))
        if STOP:
            raise KeyboardInterrupt("interrupted before QA launch")
        results.append(run_check("qa", ["just", "qa"], evidence, runtime, report))
    except (KeyboardInterrupt, Exception) as exc:
        error = str(exc)
        print(f"runner error: {exc}", file=sys.stderr, flush=True)
    finally:
        try:
            after = snapshot()
            save(evidence / "sources-after.json", after)
            issues = source_issues(before, after, require_clean=True) if before else ["initial source snapshot unavailable"]
            if manifest_before is not None:
                if (ROOT / "scripts/release/sources.json").read_bytes() != manifest_before:
                    issues.append("source manifest changed")
                _, _, after_pins = read_manifest(ROOT / "scripts/release/sources.json")
                report["root_status_after"] = root_layout_status(ROOT, after_pins)
                if report["root_status_after"] != root_before:
                    issues.append("root checkout status changed")
                report["root_revision_after"] = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
                if report["root_revision_after"] != root_revision_before:
                    issues.append("root revision changed")
                if generated_report is not None:
                    issues.extend(generated_coverage(
                        generated_report, after, report["root_revision_after"],
                        manifest_before, report["root_status_after"], generated_evidence,
                    ))
        except Exception as exc:
            issues = [f"source guard failed: {exc}"]
        (evidence / "source-issues.json").write_text(json.dumps(issues, indent=2) + "\n")

    qa_summaries = results[1]["test_summaries"] if len(results) == 2 else []
    qa_tests = results[1]["passed_tests"] if len(results) == 2 else []
    qa_ignored = results[1]["ignored_tests"] if len(results) == 2 else []
    required_safety_tests = (
        "testkit_concurrent_add_plugin_preserves_both_mutations",
        "testkit_idle_driver_config_change_updates_spec_without_engine_ready",
        "systemwide_lab_scenario_matrix_over_ipc",
        "systemwide_lab_restarts_with_a_fresh_coherent_snapshot",
        "decoder_retries_hal_reader_after_late_shared_memory_creation",
    )
    missing_safety_tests = [
        name for name in required_safety_tests
        if not any(test.endswith(name) for test in qa_tests)
    ]
    positive_counts, ignored_count = positive_qa_inventory(qa_summaries)
    verdict = (
        "PASS"
        if not error and not STOP and not issues and len(results) == 2
        and all(result["exit_code"] == 0 for result in results)
        and positive_counts and not missing_safety_tests
        and ignored_count == 1
        and qa_ignored == ["plugin_artifact::tests::all_generated_room_eq_files_build_graphs"]
        and all(result["cleanup"]["ok"] for result in results)
        and all(summary.startswith("test result: ok.") for summary in qa_summaries)
        else "FAIL"
    )
    report.update({"verdict": verdict, "status": verdict, "results": results,
                   "source_issues": issues, "missing_safety_tests": missing_safety_tests,
                   "ignored_tests": ignored_count, "ignored_test_names": qa_ignored,
                   "error": error})
    save(evidence / "report.json", report)
    print(f"Linux systemwide recipes: {verdict}", flush=True)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
