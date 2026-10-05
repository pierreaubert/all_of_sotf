#!/usr/bin/env python3
"""Capture AUD132 with default and scalar HR planners on identical input."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.librespot_candidate_check import clean_group, enable_subreaper
from scripts.release.qa import host_platform, source_issues, source_state


FIXTURE = ROOT / "scripts/release/fixtures/aud132-n2-linux-input.f32le"
FIXTURE_SHA = "704cbc984e7b54376aa3896be26902bc249c0d500c0babb56d3455b9174f05f1"
TEST_NAME = "aud132_preserves_small_fft_and_512_pre_edit_full_output_controls"
FORK_TEST = "scalar_planner_preserves_even_real_transform_contract"
FORK_TESTS = {FORK_TEST, "complex_to_real_64", "complex_to_real_32",
              "complex_to_real_errors_even", "complex_to_real_errors_odd",
              "real_to_complex_64", "real_to_complex_32"}
FORK_URL = "https://github.com/pierreaubert/realfft.git"
STOP = False


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def write(path: Path, value: object) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, indent=2) + "\n")
    pending.replace(path)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fork_state(fork: Path, expected_sha: str) -> dict:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=fork, text=True).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=fork, text=True).splitlines()
    source_sha = digest(fork / "src/lib.rs")
    state = {"revision": revision, "status": status, "source_sha256": source_sha,
             "lock_sha256": digest(fork / "Cargo.lock")}
    if revision != expected_sha or status:
        raise ValueError("realfft fork checkout differs from exact clean diagnostic pin")
    return state


def checkout_fork(fork: Path, expected_sha: str, output: Path, report: dict) -> None:
    if fork.exists():
        raise ValueError("realfft diagnostic checkout already exists")
    command = ["git", "-c", "credential.helper=", "clone", "--no-checkout",
               FORK_URL, str(fork)]
    log = output / "realfft-checkout.log"
    entry = {"name": "realfft-checkout", "command": command,
             "log": str(log), "status": "RUNNING"}
    report["active_command"] = entry
    write(output / "report.json", report)
    if STOP:
        raise KeyboardInterrupt("diagnostic interrupted before realfft checkout")
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    with log.open("wb") as stream:
        if STOP:
            raise KeyboardInterrupt("diagnostic interrupted before realfft checkout")
        child = subprocess.Popen(command, cwd=output, env=environment,
                                 stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        code = 130
        started = time.monotonic()
        heartbeats = 0
        try:
            entry["owned_pgid"] = child.pid
            write(output / "report.json", report)
            while not STOP:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= (heartbeats + 1) * 30:
                        heartbeats += 1
                        print("AUD132 realfft checkout: still running", flush=True)
        finally:
            entry["cleanup"] = clean_group(child)
    entry["exit_code"] = code
    entry["status"] = "PASS" if code == 0 and entry["cleanup"]["ok"] else "FAIL"
    report["cases"].append(entry)
    report.pop("active_command", None)
    write(output / "report.json", report)
    if entry["status"] != "PASS" or STOP:
        raise ValueError("realfft checkout failed or was interrupted")
    subprocess.check_call(["git", "checkout", "--detach", expected_sha], cwd=fork,
                          env=environment, stdout=subprocess.DEVNULL)
    fork_state(fork, expected_sha)


def root_binding() -> dict:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    return {"revision": revision,
            "sources_manifest_sha256": digest(ROOT / "scripts/release/sources.json")}


def validate_fixture(path: Path) -> None:
    if path.stat().st_size != 32768 or digest(path) != FIXTURE_SHA:
        raise ValueError("pinned Linux AUD132 input fixture differs")
    if not all(math.isfinite(sample[0])
               for sample in struct.iter_unpack("<f", path.read_bytes())):
        raise ValueError("canonical AUD132 input contains nonfinite samples")


def validate_output(path: Path) -> None:
    raw = path.read_bytes()
    if not raw or len(raw) % 4:
        raise ValueError(f"AUD132 output missing samples: {path.name}")
    if not all(math.isfinite(sample[0])
               for sample in struct.iter_unpack("<f", raw)):
        raise ValueError(f"AUD132 output contains nonfinite samples: {path.name}")


def positive_inventory(text: str, allow_golden_failure: bool = False) -> bool:
    passed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ok$", text, re.MULTILINE)
    failed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+FAILED$", text, re.MULTILINE)
    ignored = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ignored", text, re.MULTILINE)
    names = passed + failed
    if len(names) != 1 or names[0].rsplit("::", 1)[-1] != TEST_NAME or ignored:
        return False
    if allow_golden_failure and failed:
        return bool(re.search(r"test result: FAILED\. 0 passed; 1 failed; 0 ignored;", text))
    return (not failed and bool(re.search(
        r"test result: ok\. 1 passed; 0 failed; 0 ignored;", text)))


def run_case(name: str, output: Path, fixture: Path | None,
             scalar_hr: bool, collect_all: bool, report: dict) -> dict:
    capture = output / name
    capture.mkdir()
    log = output / f"{name}.log"
    command = ["cargo", "test", "--locked", "-p", "sotf-plugin-upmixer",
               "--features", "onnx", "--lib", TEST_NAME, "--", "--show-output",
               "--test-threads=1"]
    environment = os.environ.copy()
    environment["SOTF_AUD132_CAPTURE_DIR"] = str(capture)
    if collect_all:
        environment["SOTF_AUD132_COLLECT_ALL_GOLDENS"] = "1"
    else:
        environment.pop("SOTF_AUD132_COLLECT_ALL_GOLDENS", None)
    if scalar_hr:
        environment["SOTF_AUD132_SCALAR_HR_FFT"] = "1"
    else:
        environment.pop("SOTF_AUD132_SCALAR_HR_FFT", None)
    if fixture is not None:
        environment["SOTF_AUD132_CANONICAL_INPUT_F32LE"] = str(fixture)
    else:
        environment.pop("SOTF_AUD132_CANONICAL_INPUT_F32LE", None)
    entry = {"name": name, "command": command, "status": "RUNNING",
             "log": str(log), "capture": str(capture)}
    report["active_command"] = entry
    write(output / "report.json", report)

    def stop_before_launch() -> None:
        if STOP:
            entry["status"] = "INTERRUPTED_BEFORE_LAUNCH"
            report["cases"].append(entry)
            report.pop("active_command", None)
            write(output / "report.json", report)
            raise KeyboardInterrupt("diagnostic interrupted before Cargo launch")

    stop_before_launch()
    with log.open("wb") as stream:
        stop_before_launch()
        child = subprocess.Popen(command, cwd=ROOT / "sotf-daw", env=environment,
                                 stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        code = 130
        started = time.monotonic()
        heartbeats = 0
        try:
            entry["owned_pgid"] = child.pid
            write(output / "report.json", report)
            while not STOP:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= (heartbeats + 1) * 30:
                        heartbeats += 1
                        print(f"AUD132 {name}: still running", flush=True)
        finally:
            entry["cleanup"] = clean_group(child)
    text = log.read_text(errors="replace")
    passed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ok$", text, re.MULTILINE)
    failed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+FAILED$", text, re.MULTILINE)
    ignored = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ignored", text, re.MULTILINE)
    selected = (capture / "n2_aud132_pre_edit_hr_off_input.f32le")
    full = (capture / "n2_aud132_pre_edit_hr_off_full.f32le")
    all_full = sorted(path.name for path in capture.glob("n*_aud132_pre_edit_hr_*_full.f32le"))
    expected_full = sorted(f"n{n}_aud132_pre_edit_hr_{route}_full.f32le"
                           for n in (2, 256, 512) for route in ("on", "off"))
    for filename in all_full:
        validate_output(capture / filename)
    valid_result = (entry["cleanup"]["ok"]
                    and (not collect_all or all_full == expected_full)
                    and positive_inventory(text, allow_golden_failure=collect_all)
                    and (code == 0 or collect_all and code == 101))
    entry.update({"status": "CAPTURED_GOLDEN_PASS" if valid_result and code == 0
                  else "CAPTURED_GOLDEN_FAIL" if valid_result else "FAIL",
                  "exit_code": code, "passed": passed, "failed": failed,
                  "ignored": ignored, "selected_input_sha256": digest(selected) if selected.is_file() else None,
                  "full_output_sha256": digest(full) if full.is_file() else None,
                  "full_output_bytes": full.stat().st_size if full.is_file() else None,
                  "captured_files": sorted(path.name for path in capture.glob("*.f32le"))})
    report["cases"].append(entry)
    report.pop("active_command", None)
    write(output / "report.json", report)
    return entry


def compare_outputs(output: Path, report: dict) -> None:
    comparisons = {}
    for n in (2, 256, 512):
        for route in ("on", "off"):
            filename = f"n{n}_aud132_pre_edit_hr_{route}_full.f32le"
            for left_case, right_case in (("canonical", "scalar"),):
                left_path = output / left_case / filename
                right_path = output / right_case / filename
                if not left_path.is_file() or not right_path.is_file():
                    raise ValueError(f"missing comparison capture: {filename}")
                validate_output(left_path)
                validate_output(right_path)
                left, right = left_path.read_bytes(), right_path.read_bytes()
                if len(left) != len(right) or len(left) % 4:
                    raise ValueError(f"comparison length mismatch: {filename}")
                values = zip(struct.iter_unpack("<f", left),
                             struct.iter_unpack("<f", right), strict=True)
                bit_differences = sum(
                    left[i:i + 4] != right[i:i + 4]
                    for i in range(0, len(left), 4))
                maximum_delta = max((abs(a[0] - b[0]) for a, b in values), default=0.0)
                comparisons[f"{left_case}_vs_{right_case}_{filename}"] = {
                    "samples": len(left) // 4, "bit_differences": bit_differences,
                    "maximum_absolute_difference": maximum_delta,
                    "left_sha256": digest(left_path), "right_sha256": digest(right_path),
                }
                if route == "off" and bit_differences:
                    raise ValueError(f"HR-off changed under scalar-only diagnostic: {filename}")
    report["comparisons"] = comparisons


def run_fork_contract(fork: Path, output: Path, report: dict) -> None:
    command = ["cargo", "test", "--locked", "--lib",
               "--", "--show-output", "--test-threads=1"]
    log = output / "realfft-scalar-contract.log"
    entry = {"name": "realfft-scalar-contract", "command": command,
             "status": "RUNNING", "log": str(log)}
    report["active_command"] = entry
    write(output / "report.json", report)
    if STOP:
        raise KeyboardInterrupt("diagnostic interrupted before realfft test")
    with log.open("wb") as stream:
        if STOP:
            raise KeyboardInterrupt("diagnostic interrupted before realfft test")
        environment = os.environ.copy()
        environment["CARGO_TARGET_DIR"] = str(output / "realfft-target")
        child = subprocess.Popen(command, cwd=fork, stdout=stream,
                                 stderr=subprocess.STDOUT, env=environment,
                                 start_new_session=True)
        started = time.monotonic()
        heartbeats = 0
        code = 130
        try:
            entry["owned_pgid"] = child.pid
            write(output / "report.json", report)
            while not STOP:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= (heartbeats + 1) * 30:
                        heartbeats += 1
                        print("AUD132 realfft scalar contract: still running", flush=True)
        finally:
            entry["cleanup"] = clean_group(child)
    text = log.read_text(errors="replace")
    selected = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ok$", text, re.MULTILINE)
    failed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+FAILED$", text, re.MULTILINE)
    ignored = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ignored", text, re.MULTILINE)
    summary = re.search(r"test result: ok\. (\d+) passed; 0 failed; 0 ignored;", text)
    entry["status"] = "PASS" if (code == 0 and entry["cleanup"]["ok"]
                              and {name.rsplit("::", 1)[-1] for name in selected} == FORK_TESTS
                              and summary is not None
                              and int(summary.group(1)) == len(selected) == 7
                              and not failed and not ignored) else "FAIL"
    entry["exit_code"] = code
    entry["passed"] = selected
    report["cases"].append(entry)
    report.pop("active_command", None)
    write(output / "report.json", report)
    if entry["status"] != "PASS":
        raise ValueError("realfft scalar contract test failed or did not execute")


def main() -> int:
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    if len(sys.argv) != 2 or os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        print("usage: disposable Gitea CI aud132_scalar_hr_check.py OUTPUT", file=sys.stderr)
        return 2
    if Path.cwd().resolve() != ROOT:
        print("AUD132 diagnostic must run from the checked-out root", file=sys.stderr)
        return 2
    output = Path(sys.argv[1]).resolve()
    fork = output / "realfft-fork"
    manifest = tomllib.loads((ROOT / "sotf-daw/Cargo.toml").read_text())
    realfft_patch = manifest["patch"]["crates-io"]["realfft"]
    if realfft_patch["git"] != FORK_URL:
        print("DAW realfft source does not match diagnostic fork", file=sys.stderr)
        return 2
    fork_sha = realfft_patch["rev"]
    if not re.fullmatch(r"[0-9a-f]{40}", fork_sha):
        print("missing exact realfft diagnostic fork SHA", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    report: dict = {"status": "FAIL", "platform": host_platform(), "cases": [], "errors": []}
    write(output / "report.json", report)
    before = None
    before_layout = None
    root_before = None
    pins = None
    fork_before = None
    try:
        before = source_state(ROOT, list(workspace_map()), report["platform"])
        root_before = root_binding()
        report["root_binding_before"] = root_before
        _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
        before_layout = root_layout_status(ROOT, pins)
        report["sources_before"] = before
        report["root_before"] = before_layout
        write(output / "report.json", report)
        enable_subreaper()
        validate_fixture(FIXTURE)
        if source_issues(before, before, require_clean=True):
            raise ValueError("source tree was not clean before diagnostic")
        if any(before[name].get("revision") != revision for name, revision in pins.items()):
            raise ValueError("sibling revision differs from pinned sources.json")
        if before_layout["unexpected"] or before_layout["missing"]:
            raise ValueError("root checkout layout was not pinned before diagnostic")
        checkout_fork(fork, fork_sha, output, report)
        fork_before = fork_state(fork, fork_sha)
        report["fork_before"] = fork_before
        write(output / "report.json", report)
        run_fork_contract(fork, output, report)
        native = run_case("native", output, None, False, False, report)
        if STOP:
            raise KeyboardInterrupt("diagnostic interrupted")
        canonical = run_case("canonical", output, FIXTURE, False, True, report)
        if STOP:
            raise KeyboardInterrupt("diagnostic interrupted")
        scalar = run_case("scalar", output, FIXTURE, True, True, report)
        compare_outputs(output, report)
        if (canonical["selected_input_sha256"] != FIXTURE_SHA
                or scalar["selected_input_sha256"] != FIXTURE_SHA):
            raise ValueError("canonical or scalar input capture differs from pinned fixture")
        if not canonical["full_output_sha256"]:
            raise ValueError("canonical output capture missing")
        for case in (native, canonical, scalar):
            if case["status"] == "FAIL":
                raise ValueError(f"{case['name']} test failed to provide valid golden evidence")
        if native["status"] != "CAPTURED_GOLDEN_PASS" or canonical["status"] != "CAPTURED_GOLDEN_PASS":
            raise ValueError("default planner changed an original historical golden")
        if scalar["status"] == "CAPTURED_GOLDEN_FAIL":
            raise ValueError("scalar HR planner changed an original historical golden")
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            after = source_state(ROOT, list(workspace_map()), report["platform"])
            report["sources_after"] = after
            if before is not None:
                report["errors"].extend(source_issues(before, after, require_clean=True))
            if pins is not None:
                after_layout = root_layout_status(ROOT, pins)
                report["root_after"] = after_layout
                if before_layout != after_layout:
                    report["errors"].append("root checkout layout changed")
            if root_before is not None:
                root_after = root_binding()
                report["root_binding_after"] = root_after
                if root_before != root_after:
                    report["errors"].append("aggregate HEAD or source manifest changed")
            if fork_before is not None:
                fork_after = fork_state(fork, fork_sha)
                report["fork_after"] = fork_after
                if fork_before != fork_after:
                    report["errors"].append("realfft fork checkout changed")
        except Exception as error:
            report["errors"].append(f"after-source guard failed: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not report["errors"] and not STOP else "FAIL"
        write(output / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
