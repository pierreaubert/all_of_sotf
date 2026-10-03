#!/usr/bin/env python3
"""Run aggregate CI gates with pinned-source and command-level evidence."""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "buildbot"))
from ci_matrix import gate_commands, workspace_map
from version_snapshot import snapshot


def host_platform() -> str:
    return {"darwin": "macos", "linux": "linux", "windows": "windows"}.get(
        platform.system().lower(), platform.system().lower()
    )


def commands_for(name: str, phase: str, platform_name: str | None = None) -> list[tuple[str, ...]]:
    """Return commands required of this workspace on the selected platform."""
    platform_name = platform_name or host_platform()
    metadata = ("cargo", "metadata", "--locked", "--format-version", "1")
    if phase == "metadata":
        return [metadata]
    if phase == "check":
        return [metadata, ("cargo", "check", "--workspace", "--all-targets", "--locked")]
    workspace = workspace_map()[name]
    commands = [metadata, *gate_commands(workspace, qa=phase == "qa")]
    if phase == "qa":
        extras = {
            "sotf": [("just", recipe) for recipe in (
                "test-pr", "ntest", "itest", "perf-smoke", "dev-driver-smoke",
                "dev-driver-full", "dev-driver-roomeq", "dev-driver-tui",
            )],
            "sotf-daw": [("just", recipe) for recipe in (
                "ntest", "qa-ffi", "qa-bridge", "qa-plugins-cross-format",
            )],
        }
        if name == "sotf-daw" and platform_name == "linux":
            extras[name].append((
                "cargo", "test", "--locked", "-p", "sotf-host",
                "--features", "worker-test-backend,external-plugin-clap",
                "--test", "external_plugin_isolation", "--", "--nocapture",
            ))
        if name == "gpui-toolkit":
            # The strict release recipe requires Metal. Linux runs the portable QA recipe.
            commands = [metadata, ("just", "qa-release-evidence" if platform_name == "macos" else "qa")]
        commands.extend(extras.get(name, []))
    return commands


def source_state(root: Path, names: list[str], platform_name: str) -> dict:
    """Capture every sibling before and after the complete aggregate run."""
    states = {}
    for name in names:
        workspace = root / name
        if not (workspace / "Cargo.toml").is_file():
            states[name] = {"error": "missing workspace Cargo.toml"}
            continue
        source = snapshot(workspace, platform_name)
        lock = workspace / "Cargo.lock"
        source["lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else None
        states[name] = source
    return states


def source_issues(before: dict, after: dict, require_clean: bool) -> list[str]:
    issues = []
    for name, start in before.items():
        end = after.get(name, {})
        if "error" in start or "error" in end:
            issues.append(f"{name}: {start.get('error') or end.get('error')}")
        elif not start.get("revision") or start.get("dirty") is None:
            issues.append(f"{name}: source revision or cleanliness unavailable")
        elif require_clean and start["dirty"]:
            issues.append(f"{name}: source tree was dirty before validation")
        elif start["revision"] != end.get("revision") or start["dirty"] != end.get("dirty"):
            issues.append(f"{name}: source revision or cleanliness changed")
        elif require_clean and end.get("dirty") is not False:
            issues.append(f"{name}: source tree is dirty after validation")
        elif start["lock_sha256"] != end.get("lock_sha256"):
            issues.append(f"{name}: Cargo.lock changed")
    return issues


def write_report(path: Path, report: dict) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def print_failure_tail(log: Path, lines: int = 80) -> None:
    """Show the end of a failed gate in CI while preserving the full artifact."""
    print(f"--- Last {lines} lines of {log} ---", flush=True)
    with log.open("r", encoding="utf-8", errors="replace") as stream:
        for line in deque(stream, maxlen=lines):
            print(line, end="", flush=True)


def sandbox_coverage_skipped(name: str, phase: str, platform_name: str,
                             command: tuple[str, ...], log: Path) -> bool:
    """Reject the sandbox integration test's successful kernel-unavailable return."""
    if (name, phase, platform_name) != ("sotf-daw", "qa", "linux"):
        return False
    if not (command[:5] == ("cargo", "test", "--locked", "-p", "sotf-host")
            and "external_plugin_isolation" in command):
        return False
    with log.open("r", encoding="utf-8", errors="replace") as stream:
        return any("SKIP: kernel sandbox unavailable" in line for line in stream)


class GateInterrupted(KeyboardInterrupt):
    def __init__(self, result: dict):
        super().__init__("gate interrupted")
        self.result = result


def stop_process_group(process: subprocess.Popen) -> None:
    """Stop the gate and any Cargo/just descendants when CI cancels it."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_workspace(name: str, phase: str, root: Path, output: Path, require_clean: bool,
                  platform_name: str | None = None, report: dict | None = None,
                  report_path: Path | None = None) -> dict:
    platform_name = platform_name or host_platform()
    workspace = root / name
    result = {"workspace": name, "status": "FAIL", "commands": [], "gates": []}
    if not (workspace / "Cargo.toml").is_file():
        result["error"] = "missing workspace Cargo.toml"
        return result
    if phase == "qa" and name == "gpui-toolkit" and platform_name != "macos":
        result["gates"].append({"name": "strict Metal release evidence", "status": "SKIPPED", "required_on": "macos"})
    before = source_state(root, [name], platform_name)
    result["source"] = before[name]
    issues = source_issues(before, before, require_clean)
    if issues:
        result["error"] = "; ".join(issues)
        return result
    for index, command in enumerate(commands_for(name, phase, platform_name)):
        log = output / f"{name}-{index:02d}.log"
        started = time.monotonic()
        print(f"[{name}] {' '.join(command)}", flush=True)
        entry = {"argv": list(command), "exit_code": None, "log": str(log)}
        if report is not None and report_path is not None:
            report["active_command"] = entry
            write_report(report_path, report)
        with log.open("w", encoding="utf-8") as stream:
            try:
                process = subprocess.Popen(command, cwd=workspace, stdout=stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = process.wait()
                except KeyboardInterrupt:
                    stop_process_group(process)
                    entry.update({"status": "INTERRUPTED", "exit_code": process.returncode,
                                  "duration_seconds": round(time.monotonic() - started, 3)})
                    result["commands"].append(entry)
                    result["error"] = "gate interrupted"
                    raise GateInterrupted(result)
            except OSError as error:
                stream.write(str(error) + "\n")
                code = 127
        entry.update({"exit_code": code,
                      "duration_seconds": round(time.monotonic() - started, 3)})
        result["commands"].append(entry)
        if report is not None:
            report.pop("active_command", None)
        print(f"[{name}] exit {code}; log: {log}", flush=True)
        if code:
            print_failure_tail(log)
            result["error"] = "command failed; later commands were not run"
            return result
        if sandbox_coverage_skipped(name, phase, platform_name, command, log):
            print_failure_tail(log)
            result["error"] = "required Linux sandbox coverage skipped; later commands were not run"
            result["gates"].append({"name": "Linux external-plugin sandbox", "status": "FAIL",
                                    "reason": "kernel sandbox unavailable"})
            return result
    after = source_state(root, [name], platform_name)
    issues = source_issues(before, after, require_clean)
    if issues:
        result["error"] = "; ".join(issues)
    else:
        result["status"] = "PASS"
    return result


def interrupted(_signum, _frame):
    raise KeyboardInterrupt("SIGTERM")


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", nargs="?", choices=("metadata", "check", "tests", "qa"))
    parser.add_argument("--phase", dest="phase_option", choices=("metadata", "check", "tests", "qa"))
    parser.add_argument("--platform", choices=("macos", "linux", "windows"))
    parser.add_argument("--workspace", action="append", choices=tuple(workspace_map()))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args(argv)
    phase = args.phase_option or args.phase
    if not phase or (args.phase and args.phase_option and args.phase != args.phase_option):
        parser.error("specify exactly one phase")
    platform_name = args.platform or host_platform()
    if platform_name != host_platform():
        parser.error(f"requested platform {platform_name} differs from host {host_platform()}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = (args.output or ROOT / "target" / "release-qa" / f"{timestamp}-{phase}").resolve()
    output.mkdir(parents=True, exist_ok=False)
    names = args.workspace or list(workspace_map())
    report = {"started_at": timestamp, "phase": phase, "platform": platform_name,
              "status": "RUNNING", "require_clean": args.require_clean,
              "required_workspaces": names, "workspaces": [],
              "release_coverage": {"complete": False, "reason": "single-platform phase evidence; release requires separately verified platform and packaging lanes",
                                   "missing_platforms": [item for item in ("macos", "linux", "windows") if item != platform_name],
                                   "packaging": "not_run"}}
    path = output / "report.json"
    try:
        report["sources_before"] = source_state(ROOT, list(workspace_map()), platform_name)
        write_report(path, report)
        issues = source_issues(report["sources_before"], report["sources_before"], args.require_clean)
        if issues:
            report["errors"] = issues
        else:
            for name in names:
                report["active_workspace"] = name
                write_report(path, report)
                result = run_workspace(name, phase, ROOT, output, args.require_clean,
                                       platform_name, report, path)
                report["workspaces"].append(result)
                report.pop("active_workspace", None)
                write_report(path, report)
    except GateInterrupted as error:
        report["workspaces"].append(error.result)
        report["error"] = str(error)
        report["interrupted"] = True
    except BaseException as error:
        report["error"] = f"{type(error).__name__}: {error}"
        if isinstance(error, KeyboardInterrupt):
            report["interrupted"] = True
    finally:
        try:
            report["sources_after"] = source_state(ROOT, list(workspace_map()), platform_name)
            report["source_issues"] = source_issues(report.get("sources_before", {}), report["sources_after"], args.require_clean)
        except BaseException as error:
            report["source_issues"] = [f"final source snapshot failed: {type(error).__name__}: {error}"]
        passed = len(report["workspaces"]) == len(names) and all(
            item["status"] == "PASS" for item in report["workspaces"])
        report["status"] = "PASS" if passed and not report["source_issues"] and not report.get("error") else "FAIL"
        write_report(path, report)
    print(f"{report['status']}: {path}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
