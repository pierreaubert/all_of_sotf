#!/usr/bin/env python3
"""Pinned, device-free fractional-clock and NIH horizon regression evidence."""

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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release.checkout_sources import read_manifest
from scripts.release.qa import source_issues, source_state, workspace_map

STOP = False


def interrupt(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def group_members(pgid: int) -> list[dict]:
    result = []
    output = subprocess.run(["ps", "-eo", "pid=,pgid=,stat="], check=True,
                            capture_output=True, text=True, timeout=3).stdout
    for line in output.splitlines():
        pid, group, state = line.split(maxsplit=2)
        if int(group) == pgid:
            result.append({"pid": int(pid), "state": state})
    return result


def reap_group(child: subprocess.Popen, result: dict) -> None:
    child.poll()
    if child.returncode is None or sys.platform != "linux":
        return
    try:
        entries = group_members(child.pid)
    except Exception as error:
        result.setdefault("cleanup_errors", []).append(f"reap inventory: {error}")
        return
    for item in entries:
        pid = item["pid"]
        if pid == child.pid:
            continue
        try:
            reaped, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            continue
        if reaped:
            result.setdefault("reaped_descendants", []).append({"pid": reaped, "status": status})


def cleanup(child: subprocess.Popen, result: dict) -> bool:
    for signum in (signal.SIGTERM, signal.SIGKILL):
        reap_group(child, result)
        try:
            remaining = group_members(child.pid)
        except Exception as error:
            result.setdefault("cleanup_errors", []).append(f"group inventory: {error}")
            remaining = [{"pid": child.pid, "state": "uninspectable"}]
        if not remaining:
            break
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
        for _ in range(50):
            child.poll()
            reap_group(child, result)
            try:
                if not group_members(child.pid):
                    break
            except Exception as error:
                result.setdefault("cleanup_errors", []).append(f"group poll: {error}")
                break
            time.sleep(0.1)
    child.poll()
    reap_group(child, result)
    try:
        result["survivors"] = group_members(child.pid)
    except Exception as error:
        result.setdefault("cleanup_errors", []).append(f"final inventory: {error}")
        result["survivors"] = [{"pid": child.pid, "state": "uninspectable"}]
    return not result["survivors"] and not result.get("cleanup_errors")


def run(name: str, argv: list[str], output: Path) -> dict:
    result: dict = {"name": name, "argv": argv, "exit_code": None,
                    "cleanup_ok": False, "owned_pgid": None}
    child: subprocess.Popen | None = None
    with (output / f"{name}.log").open("wb") as log:
        try:
            child = subprocess.Popen(argv, cwd=ROOT / "sotf-daw", stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            result["owned_pgid"] = child.pid
            (output / "active-command.json").write_text(json.dumps(result, indent=2) + "\n")
            while child.poll() is None and not STOP:
                print(f"{name}: owned PID {child.pid} still running", flush=True)
                try:
                    child.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
            result["exit_code"] = child.poll() if not STOP else 130
            result["interrupted"] = STOP
        except Exception as error:
            result["runner_error"] = str(error)
        finally:
            if child is not None:
                result["cleanup_ok"] = cleanup(child, result)
            (output / "active-command.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def root_status(pins: dict[str, str]) -> dict:
    lines = set(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, text=True).splitlines())
    allowed = {f"?? {name}/" for name in pins}
    return {"allowed": sorted(lines & allowed), "missing": sorted(allowed - lines),
            "unexpected": sorted(lines - allowed)}


def cases() -> list[tuple[str, list[str], str]]:
    host = ["cargo", "test", "--locked", "-p", "sotf-host", "--lib"]
    ab = ["cargo", "test", "--locked", "-p", "sotf-plugin-ab-compare", "--test", "ab087_variable_rate"]
    convolution = ["cargo", "test", "--locked", "-p", "sotf-plugin-convolution", "--lib"]
    eq = ["cargo", "test", "--locked", "-p", "sotf-plugin-eq", "--lib"]
    xtc = ["cargo", "test", "--locked", "-p", "sotf-plugin-xtc", "--lib"]
    nih = ["cargo", "test", "--locked", "-p", "nih_plug", "--lib"]
    return [
        ("host-exact-clock", host, "fractional_clock_retains_binary_input_exactly"),
        ("host-overflow", host, "fractional_graph_refuses_timeline_overflow_before_processing"),
        ("host-fractional", host, "fractional_host_rate_reaches_both_clocks_without_integer_rounding"),
        ("host-removed", host, "removed_node_clock_does_not_constrain_the_rebuilt_graph"),
        ("host-contracted", host, "contracted_output_does_not_hide_upstream_input_position_overflow"),
        ("ab-two-sink", ab, "fractional_outer_clock_runs_two_sink_free_paths_without_truncation"),
        ("ab-nested", ab, "fractional_outer_clock_runs_nested_gain_path_without_rounding"),
        ("convolution-ir", convolution, "fractional_host_rate_ir_keeps_duration_channels_and_impulse_origin"),
        ("convolution-memory", convolution, "fractional_ir_resampling_rejects_unbounded_temporary_output_before_allocation"),
        ("eq-fractional", eq, "fractional_sample_rate_reaches_eq_filter_and_autogain_clock"),
        ("xtc-transition", xtc, "bypass_transition_uses_the_exact_host_clock"),
        ("xtc-boundary", xtc, "xtc_rejects_unaddressable_bypass_duration_before_mutating_clock"),
        ("nih-checked-horizon", nih, "checked_horizon_refuses_overflow_without_changing_live_smoother"),
        ("nih-oversampling", nih, "oversampling_horizon_uses_one_prepared_factor_snapshot"),
        ("nih-large-skip", nih, "large_skip_finishes_valid_smoothing_without_signed_wrap"),
        ("nih-float-refusal", nih, "refused_float_automation_preserves_value_modulation_and_smoother"),
        ("nih-integer-refusal", nih, "refused_integer_automation_preserves_value_modulation_and_smoother"),
        ("nih-valid-restore", nih, "live_audio_restore_keeps_existing_valid_preset_behavior"),
        ("nih-invalid-restore", nih, "invalid_live_horizon_refuses_before_any_active_preset_write"),
    ]


def main() -> int:
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    if len(sys.argv) != 2:
        print("usage: f64_fractional_nih_check.py OUTPUT", file=sys.stderr)
        return 2
    output = (ROOT / sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report: dict = {"status": "FAIL", "scope": "focused DSP and NIH; no full release qualification",
                    "commands": [], "issues": []}
    before = None
    pins = None
    root_before = None
    status_before = None
    try:
        if sys.platform == "linux":
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(36, 1, 0, 0, 0) != 0:
                raise RuntimeError("Linux private child subreaper registration failed")
        manifest = ROOT / "scripts/release/sources.json"
        (output / "sources.json").write_bytes(manifest.read_bytes())
        _, _, pins = read_manifest(manifest)
        root_before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              text=True).strip()
        report["root_revision"] = root_before
        status_before = root_status(pins)
        before = source_state(ROOT, list(workspace_map()), "macos" if sys.platform == "darwin" else "linux")
        (output / "sources-before.json").write_text(json.dumps(before, indent=2) + "\n")
        report["issues"].extend(source_issues(before, before, True))
        for name, revision in pins.items():
            if before.get(name, {}).get("revision") != revision:
                report["issues"].append(f"{name}: pin mismatch")
        if status_before["unexpected"] or status_before["missing"]:
            report["issues"].append("unexpected or missing root checkout paths")
        if report["issues"]:
            raise RuntimeError("source preflight failed")
        for label, base, selected in cases():
            for phase, tail in (("inventory", ["--", "--list"]),
                                ("execute", ["--", "--show-output", "--test-threads=1"])):
                result = run(label + "-" + phase, base + [selected] + tail, output)
                body = (output / f"{label}-{phase}.log").read_text(errors="replace")
                if phase == "inventory":
                    result["positive_inventory"] = bool(re.search(
                        r"(?m)^.*" + re.escape(selected) + r": test$", body))
                else:
                    result["named_pass"] = bool(re.search(
                        r"(?m)^test .*" + re.escape(selected) + r" \.\.\. ok$", body))
                    result["one_executed_no_skips"] = bool(re.search(
                        r"test result: ok\. 1 passed; 0 failed; 0 ignored;", body))
                report["commands"].append(result)
                (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
                if result["exit_code"] != 0 or not result["cleanup_ok"] or STOP or not all(
                    value for key, value in result.items()
                    if key in ("positive_inventory", "named_pass", "one_executed_no_skips")
                ):
                    raise RuntimeError(f"{label}-{phase} did not execute the named positive gate")
    except (Exception, KeyboardInterrupt) as error:
        report["issues"].append(str(error))
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            after = source_state(ROOT, list(workspace_map()), "macos" if sys.platform == "darwin" else "linux")
            (output / "sources-after.json").write_text(json.dumps(after, indent=2) + "\n")
            if before is not None:
                report["issues"].extend(source_issues(before, after, True))
            if pins is not None and root_status(pins) != status_before:
                report["issues"].append("root checkout status changed")
            if root_before is not None and subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip() != root_before:
                report["issues"].append("root revision changed")
            if (ROOT / "scripts/release/sources.json").read_bytes() != (output / "sources.json").read_bytes():
                report["issues"].append("manifest changed")
        except Exception as error:
            report["issues"].append(f"final source guard: {error}")
        report["status"] = "PASS" if not report["issues"] and len(report["commands"]) == 2 * len(cases()) else "FAIL"
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
