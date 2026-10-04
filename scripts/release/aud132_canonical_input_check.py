#!/usr/bin/env python3
"""Compare AUD132 output on Linux and macOS using identical captured input."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.librespot_candidate_check import clean_group, enable_subreaper
from scripts.release.qa import host_platform, source_issues, source_state


FIXTURE = ROOT / "scripts/release/fixtures/aud132-n2-linux-input.f32le"
FIXTURE_SHA = "704cbc984e7b54376aa3896be26902bc249c0d500c0babb56d3455b9174f05f1"
TEST_NAME = "aud132_preserves_small_fft_and_512_pre_edit_full_output_controls"
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


def validate_fixture(path: Path) -> None:
    if path.stat().st_size != 32768 or digest(path) != FIXTURE_SHA:
        raise ValueError("pinned Linux AUD132 input fixture differs")


def positive_inventory(text: str) -> bool:
    passed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ok$", text, re.MULTILINE)
    failed = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+FAILED$", text, re.MULTILINE)
    ignored = re.findall(r"^test\s+(\S+)\s+\.\.\.\s+ignored", text, re.MULTILINE)
    return (len(passed) == 1 and passed[0].rsplit("::", 1)[-1] == TEST_NAME
            and not failed and not ignored
            and bool(re.search(r"test result: ok\. 1 passed; 0 failed; 0 ignored;", text)))


def run_case(name: str, output: Path, fixture: Path | None, report: dict) -> dict:
    capture = output / name
    capture.mkdir()
    log = output / f"{name}.log"
    command = ["cargo", "test", "--locked", "-p", "sotf-plugin-upmixer",
               "--features", "onnx", "--lib", TEST_NAME, "--", "--show-output",
               "--test-threads=1"]
    environment = os.environ.copy()
    environment["SOTF_AUD132_CAPTURE_DIR"] = str(capture)
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
    entry.update({"status": "PASS" if code == 0 and entry["cleanup"]["ok"]
                  and positive_inventory(text) else "FAIL",
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
    linux = output / "native" / "n2_aud132_pre_edit_hr_off_full.f32le"
    canonical = output / "canonical" / "n2_aud132_pre_edit_hr_off_full.f32le"
    if not linux.is_file() or not canonical.is_file():
        report["comparison_error"] = "N=2 HR-off capture missing"
        return
    left, right = linux.read_bytes(), canonical.read_bytes()
    if len(left) != len(right) or len(left) % 4:
        report["comparison_error"] = "N=2 HR-off capture length mismatch"
        return
    values = zip(struct.iter_unpack("<f", left), struct.iter_unpack("<f", right), strict=True)
    bit_differences = sum(1 for a, b in zip(
        (left[i:i + 4] for i in range(0, len(left), 4)),
        (right[i:i + 4] for i in range(0, len(right), 4)), strict=True) if a != b)
    maximum_delta = max((abs(a[0] - b[0]) for a, b in values), default=0.0)
    report["native_vs_canonical_output"] = {
        "samples": len(left) // 4, "bit_differences": bit_differences,
        "maximum_absolute_difference": maximum_delta,
    }


def main() -> int:
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    if len(sys.argv) != 2 or os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        print("usage: disposable Gitea CI aud132_canonical_input_check.py OUTPUT", file=sys.stderr)
        return 2
    if Path.cwd().resolve() != ROOT:
        print("AUD132 diagnostic must run from the checked-out root", file=sys.stderr)
        return 2
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report: dict = {"status": "FAIL", "platform": host_platform(), "cases": [], "errors": []}
    write(output / "report.json", report)
    before = None
    before_layout = None
    pins = None
    try:
        before = source_state(ROOT, list(workspace_map()), report["platform"])
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
        native = run_case("native", output, None, report)
        if STOP:
            raise KeyboardInterrupt("diagnostic interrupted")
        canonical = run_case("canonical", output, FIXTURE, report)
        compare_outputs(output, report)
        if canonical["selected_input_sha256"] != FIXTURE_SHA:
            raise ValueError("canonical input capture differs from pinned fixture")
        if not canonical["full_output_sha256"]:
            raise ValueError("canonical output capture missing")
        if native["status"] != "PASS" or canonical["status"] != "PASS":
            raise ValueError("native or canonical historical golden assertion failed")
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
        except Exception as error:
            report["errors"].append(f"after-source guard failed: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not report["errors"] and not STOP else "FAIL"
        write(output / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
