#!/usr/bin/env python3
"""Capture diagnostic-only AUD132 stages under an owned Gitea process."""
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release.checkout_sources import read_manifest
if sys.platform == "darwin":
    from scripts.release import nih_macos_artifact_check as owned
else:
    from scripts.release import nih_native_artifact_check as owned

OUTPUT = ROOT / "target/release-gitea/aud132-stage"
CAPTURE = OUTPUT / "vectors"
INPUT = ROOT / "scripts/release/fixtures/aud132-n2-linux-input.f32le"
INPUT_SHA = "704cbc984e7b54376aa3896be26902bc249c0d500c0babb56d3455b9174f05f1"
INPUT_BLOB = "1df3978f58ed02caffd65aa29e4e261bb055baeb"
TEST = "stream_boundary_tests::aud132_canonical_first_stage_trace"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_input() -> None:
    if INPUT.stat().st_size != 32_768 or sha(INPUT) != INPUT_SHA:
        raise ValueError("reviewed canonical AUD132 input differs")
    blob = subprocess.check_output(["git", "hash-object", str(INPUT)], cwd=ROOT, text=True).strip()
    if blob != INPUT_BLOB:
        raise ValueError("reviewed canonical AUD132 Git blob differs")


def expected_inventory() -> dict[str, int]:
    expected = {}
    for n, full in [(2, 9_218), (256, 9_472), (512, 9_728)]:
        lengths = {"window": n, "first_input": 2 * n,
                   "reconstructed_windowed_left": n,
                   "reconstructed_windowed_right": n,
                   "fft_left_complex": 2 * (n // 2 + 1),
                   "fft_right_complex": 2 * (n // 2 + 1),
                   "inverse_windowed_channel_0": n,
                   "inverse_windowed_channel_1": n,
                   "first_block_output": 2 * n, "full_output": full}
        for stage, count in lengths.items():
            expected[f"n{n}_canonical_stage_{stage}.f32le"] = count
    return expected


def validate_vectors() -> list[dict]:
    expected = expected_inventory()
    actual = {path.name for path in CAPTURE.iterdir()}
    if actual != set(expected):
        raise ValueError(f"stage inventory differs: missing={set(expected)-actual}; extra={actual-set(expected)}")
    rows = []
    for name, count in sorted(expected.items()):
        path = CAPTURE / name
        data = path.read_bytes()
        if len(data) != count * 4:
            raise ValueError(f"{name}: expected {count} f32 samples")
        if not all(math.isfinite(value) for (value,) in struct.iter_unpack("<f", data)):
            raise ValueError(f"{name}: nonfinite sample")
        rows.append({"name": name, "samples": count, "bytes": len(data), "sha256": sha(path)})
    return rows


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("Gitea disposable environment required")
    if sys.flags.optimize != 0 or os.environ.get("PYTHONOPTIMIZE", "0") not in ("", "0"):
        raise SystemExit("Python assertions must be enabled")
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise SystemExit("stage output must start empty")
    (OUTPUT / "logs").mkdir(parents=True)
    CAPTURE.mkdir()
    owned.OUTPUT = OUTPUT
    owned.STOP = False
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    report: dict = {"status": "RUNNING", "complete": False, "commands": [], "errors": [],
                    "scope": "diagnostic first stages only; six historical goldens unchanged"}
    owned.save(report)
    before = None
    pins = None
    try:
        _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
        before = owned.snapshot(pins)
        report["before"] = before
        owned.save(report)
        if errors := owned.source_errors(before, before, pins):
            raise ValueError(f"source baseline failed: {errors}")
        validate_input()
        env = dict(os.environ, SOTF_AUD132_CANONICAL_INPUT=str(INPUT),
                   SOTF_AUD132_CAPTURE_DIR=str(CAPTURE))
        command = ["cargo", "test", "--manifest-path", "sotf-daw/Cargo.toml", "--locked",
                   "-p", "sotf-plugin-upmixer", "--features", "onnx", "--lib", TEST,
                   "--", "--ignored", "--exact"]
        entry = owned.run_owned("stage", command, report, env)
        if entry["status"] != "PASS":
            raise ValueError("exact stage test failed or owned cleanup was incomplete")
        log = (OUTPUT / "logs/stage.log").read_text(errors="replace")
        expected_line = f"test {TEST} ... ok"
        if len(re.findall(rf"(?m)^{re.escape(expected_line)}$", log)) != 1:
            raise ValueError("exact named positive test missing")
        if "test result: ok. 1 passed; 0 failed; 0 ignored;" not in log:
            raise ValueError("one-pass zero-fail zero-ignore summary missing")
        report["vectors"] = validate_vectors()
        report["positive_inventory"] = {"selected_tests": 1, "stage_files": 30}
        validate_input()
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            validate_input()
            if pins is not None and before is not None:
                after = owned.snapshot(pins)
                report["after"] = after
                report["errors"].extend(owned.source_errors(before, after, pins))
            else:
                report["errors"].append("source baseline unavailable")
        except BaseException as error:
            report["errors"].append(f"after guard: {type(error).__name__}: {error}")
        report["complete"] = True
        report["status"] = "PASS" if not report["errors"] and not owned.STOP else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
