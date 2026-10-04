#!/usr/bin/env python3
"""Run the two failing AutoEQ quality gates with complete release evidence."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from checkout_sources import read_manifest
from qa import ROOT, source_issues, source_state

FLOOR_TEST = "delayed_convergence_uses_existing_generation_budget_and_reports_actual_evaluations"
REGISTERED_DE_TEST = "registered_de_route_returns_report_for_the_final_selected_vector"
MH_BUDGET_TESTS = (
    "registered_rga_stage_budget_refusal_keeps_run_control_priority",
    "parallel_mh_objective_reservations_never_score_denied_attempts",
)
COMMANDS = (
    ("math-de-floor", ("cargo", "test", "--locked", "-p", "math-optimisation",
                       "--lib", FLOOR_TEST)),
    ("registered-de", ("cargo", "test", "--locked", "-p", "autoeq-optim",
                       "--lib", REGISTERED_DE_TEST)),
    *(("mh-budget-" + name, ("cargo", "test", "--locked", "-p", "autoeq-optim",
                               "--lib", name)) for name in MH_BUDGET_TESTS),
    ("spacing-projection", ("cargo", "test", "--locked", "-p", "autoeq-optim",
                            "--lib", "spacing_projection::tests")),
    ("de-completion", ("cargo", "test", "--locked", "-p", "autoeq-cli",
                       "--lib", "de_completion_tests")),
    ("autoeq-optim-lib", ("cargo", "test", "--locked", "-p", "autoeq-optim", "--lib")),
    ("qa-unit-tests", ("cargo", "test", "--locked", "-p", "autoeq-cli", "--lib", "qa_tests")),
    ("autoeq-all-targets", ("cargo", "check", "--locked", "--all-targets")),
    ("build-autoeq", ("cargo", "build", "--locked", "--release", "--features", "cli", "--bin", "autoeq")),
    ("qa-ascilab-6b", ("just", "qa-ascilab-6b")),
    ("qa-beyerdynamic-dt1990pro-score2", ("just", "qa-beyerdynamic-dt1990pro-score2")),
)
EXPECTED_QA_TESTS = {
    "test_perform_qa_analysis_all_pass",
    "test_perform_qa_analysis_no_improvement",
    "test_perform_qa_analysis_no_convergence_returns_error",
    "test_perform_qa_analysis_with_nan",
    "test_display_qa_analysis",
}


def enable_subreaper() -> None:
    # Cargo/just can exit before their descendants. Adopt and reap only our children.
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")


def group_members(pgid: int) -> list[dict]:
    process = subprocess.run(["ps", "-eo", "pid=,ppid=,pgid=,stat="],
                             text=True, capture_output=True, check=True, timeout=3)
    members = []
    for line in process.stdout.splitlines():
        fields = line.split()
        if len(fields) == 4 and int(fields[2]) == pgid:
            members.append({"pid": int(fields[0]), "ppid": int(fields[1]),
                            "pgid": pgid, "state": fields[3]})
    return members


def stop_group(child: subprocess.Popen) -> tuple[bool, list[dict], list[str]]:
    errors: list[str] = []

    def inspect() -> list[dict] | None:
        try:
            return group_members(child.pid)
        except Exception as error:
            errors.append(f"owned group inspection failed: {error}")
            return None

    for signum in (signal.SIGTERM, signal.SIGKILL):
        child.poll()  # Reap the direct child before adopting its descendants.
        members = inspect()
        if members == [] and not errors:
            return True, [], []
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"owned group signal failed: {error}")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            child.poll()
            try:
                while True:
                    pid, _ = os.waitpid(-1, os.WNOHANG)
                    if pid == 0:
                        break
            except ChildProcessError:
                pass
            except OSError as error:
                errors.append(f"owned child reap failed: {error}")
            members = inspect()
            if members == [] and not errors:
                return True, [], []
            time.sleep(0.1)
    child.poll()
    members = inspect()
    return members == [] and not errors, members or [], errors


def run(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    _, _, revisions = read_manifest(ROOT / "scripts/release/sources.json")
    names = list(revisions)
    before = source_state(ROOT, names, "linux")
    report = {"status": "RUNNING", "sources_before": before, "commands": []}
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    child: subprocess.Popen[str] | None = None
    active_entry: dict | None = None
    stopping = False
    old_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def interrupt(_sig, _frame):
        if stopping:
            return
        raise KeyboardInterrupt

    for sig in old_handlers:
        signal.signal(sig, interrupt)
    try:
        initial_issues = source_issues(before, before, True)
        initial_issues.extend(
            f"{name}: checkout differs from pinned revision {revision}"
            for name, revision in revisions.items()
            if before[name].get("revision") != revision
        )
        if initial_issues:
            raise ValueError("; ".join(initial_issues))
        enable_subreaper()
        for name, command in COMMANDS:
            entry = {"name": name, "command": command}
            report["commands"].append(entry)
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            active_entry = entry
            env = os.environ.copy()
            if name in ("qa-ascilab-6b", "qa-beyerdynamic-dt1990pro-score2"):
                evidence_path = output / f"{name}.selected-x.json"
                env["AUTOEQ_QA_EVIDENCE_PATH"] = str(evidence_path)
                entry["selected_x_evidence"] = str(evidence_path)
            log_path = output / f"{name}.log"
            with log_path.open("w") as log:
                cwd = ROOT / ("math-audio" if name == "math-de-floor" else "autoeq")
                child = subprocess.Popen(command, cwd=cwd, stdout=log,
                                         stderr=subprocess.STDOUT, start_new_session=True, env=env)
                started = time.monotonic()
                try:
                    while True:
                        try:
                            entry["exit_code"] = child.wait(timeout=30)
                            break
                        except subprocess.TimeoutExpired:
                            elapsed = time.monotonic() - started
                            if elapsed >= 3600:
                                entry["exit_code"] = 124
                                entry["error"] = "command timed out after 3600 seconds"
                                break
                            print(f"{name}: running for {elapsed:.0f}s", flush=True)
                finally:
                    cleanup_ok, survivors, cleanup_errors = stop_group(child)
                    entry["cleanup_ok"] = cleanup_ok
                    entry["owned_group_survivors"] = survivors
                    entry["cleanup_errors"] = cleanup_errors
            output_text = log_path.read_text(errors="replace")
            print(output_text[-8000:], end="", flush=True)
            entry["printed_fail"] = any(line.strip() == "FAIL" for line in output_text.splitlines())
            if "selected_x_evidence" in entry and not Path(entry["selected_x_evidence"]).is_file():
                entry["error"] = "selected-x evidence was not written"
            if not entry["cleanup_ok"]:
                entry["error"] = "owned process group did not terminate cleanly"
            if name == "math-de-floor":
                passed = re.findall(r"^test \S*" + re.escape(FLOOR_TEST) + r" \.\.\. ok$",
                                    output_text, re.MULTILINE)
                entry["floor_test_passed"] = len(passed)
                if len(passed) != 1:
                    entry["error"] = "expected exactly one passing DE floor regression"
            if name.startswith("mh-budget-"):
                selected = name.removeprefix("mh-budget-")
                exact = re.findall(r"^test \S*" + re.escape(selected) + r" \.\.\. ok$",
                                   output_text, re.MULTILINE)
                entry["named_budget_passed"] = len(exact)
                if len(exact) != 1:
                    entry["error"] = "expected exactly one passing objective-budget regression"
            if name in ("registered-de", "spacing-projection", "de-completion", "autoeq-optim-lib"):
                passed = re.findall(r"^test \S+ \.\.\. ok$", output_text, re.MULTILINE)
                entry["passed_tests"] = len(passed)
                if not passed:
                    entry["error"] = "expected at least one passing named regression"
                if name == "registered-de":
                    exact = re.findall(r"^test \S*" + re.escape(REGISTERED_DE_TEST)
                                       + r" \.\.\. ok$", output_text, re.MULTILINE)
                    if len(exact) != 1:
                        entry["error"] = "expected exactly one passing registered DE regression"
            if name == "qa-unit-tests":
                output_text = (output / f"{name}.log").read_text()
                passed = set(re.findall(r"^test \S+::(test_\w+) \.\.\. ok$", output_text, re.MULTILINE))
                entry["qa_tests_passed"] = sorted(passed)
                if not EXPECTED_QA_TESTS <= passed:
                    entry["error"] = f"missing QA regressions: {sorted(EXPECTED_QA_TESTS - passed)}"
            child = None
            active_entry = None
            report_path.write_text(json.dumps(report, indent=2) + "\n")
            if not entry["cleanup_ok"]:
                break
            if name not in ("qa-ascilab-6b", "qa-beyerdynamic-dt1990pro-score2") and (entry["exit_code"] or entry.get("error")):
                break
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        stopping = True
        if child is not None:
            cleanup_ok, survivors, cleanup_errors = stop_group(child)
            if active_entry is not None:
                active_entry["cleanup_ok"] = cleanup_ok
                active_entry["owned_group_survivors"] = survivors
                active_entry["cleanup_errors"] = cleanup_errors
                if not cleanup_ok:
                    active_entry["error"] = "owned process group did not terminate cleanly"
        for sig, old_handler in old_handlers.items():
            signal.signal(sig, old_handler)
        try:
            after = source_state(ROOT, names, "linux")
            report["sources_after"] = after
            report["source_issues"] = source_issues(before, after, True)
        except BaseException as error:
            report["source_issues"] = [f"final source inspection failed: {type(error).__name__}: {error}"]
        completed = {item["name"] for item in report["commands"] if "exit_code" in item}
        failures = [item["name"] for item in report["commands"]
                    if item.get("exit_code") or item.get("printed_fail") or item.get("error")]
        if completed != {name for name, _ in COMMANDS}:
            failures.append("incomplete-command-set")
        if report["source_issues"]:
            failures.append("source-or-lock-drift")
        if "error" in report:
            failures.append("runner-error")
        report["failures"] = failures
        report["status"] = "FAIL" if failures else "PASS"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(run(Path(sys.argv[1]).resolve()))
