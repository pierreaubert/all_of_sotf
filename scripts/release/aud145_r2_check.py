#!/usr/bin/env python3
"""Qualify the independent AUD145 r2 reference against public Rust paths."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release.checkout_sources import read_manifest

if sys.platform == "darwin":
    from scripts.release import nih_macos_artifact_check as owned
else:
    from scripts.release import nih_native_artifact_check as owned

OUTPUT = ROOT / "target/release-gitea/aud145-r2"
CAPTURE = OUTPUT / "public-capture"
DAW = ROOT / "sotf-daw"
REFERENCE = DAW / "audit/artifacts/aud145-analytical-reference-r2"
COMPARATOR = DAW / "audit/reference-tools/aud145_compare_r2.py"
EXPECTED_DAW = "8146381653950e9ee8f46aeb43ef5cad3f8ecde0"
MANIFEST_SHA = "9a17b772e23a535c69c0c9d3e3c3cab3d4f9359f8aba7c12d3aea2243f2a151d"
GENERATOR_SHA = "b595231e814123e8c5134a24edde15ecc303a5b55066af4960133c2f32c8dd76"
COMPARATOR_SHA = "fdbd31f20d779e6e4b89c32d1f1f32c2f95955bc7890be8234de2187f7f0936d"
ENGINE_TESTS = (
    "engine::processing_thread::tests::misc::compiled_legacy_eq_host_falls_back_after_ordered_placement_event",
    "engine::processing_thread::tests::misc::rejected_all_muted_per_channel_placement_keeps_live_eq_host_unchanged",
)
PUBLIC_CAPTURE_TEST = "capture_base_rate_placement_matrix"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def named_test(log: str, name: str) -> None:
    names = re.findall(r"(?m)^test (\S+) \.\.\. ok$", log)
    if names != [name]:
        raise ValueError(f"expected one positive {name}, got {names}")
    if "test result: ok. 1 passed; 0 failed; 0 ignored;" not in log:
        raise ValueError(f"{name}: one-pass zero-ignore result absent")


def validate_capture() -> list[dict]:
    manifest = json.loads((REFERENCE / "cases.json").read_text())
    if len(manifest["cases"]) != 42:
        raise ValueError("reference case count changed")
    expected = {case["reference"].removesuffix(".f64le") + ".f32le": case
                for case in manifest["cases"]}
    actual = {path.name for path in CAPTURE.iterdir()}
    if actual != set(expected):
        raise ValueError(f"public capture inventory differs: {sorted(actual ^ set(expected))}")
    rows = []
    for name, case in sorted(expected.items()):
        path = CAPTURE / name
        length = case["frames"] * case["channels"] * 4
        if path.stat().st_size != length:
            raise ValueError(f"{name}: wrong byte length")
        rows.append({"name": name, "bytes": length, "sha256": sha(path)})
    return rows


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("disposable Gitea environment required")
    if sys.flags.optimize or os.environ.get("PYTHONOPTIMIZE", "0") not in ("", "0"):
        raise SystemExit("Python assertions must be enabled")
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise SystemExit("AUD145 output must start empty")
    (OUTPUT / "logs").mkdir(parents=True)
    CAPTURE.mkdir()
    owned.OUTPUT = OUTPUT
    owned.STOP = False
    owned.enable_subreaper()
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    report = {"status": "RUNNING", "complete": False, "commands": [], "errors": [],
              "scope": "analytical r2 only; historical r1 and full release remain unqualified"}
    owned.save(report)
    pins = before = None
    try:
        _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
        if pins["sotf-daw"] != EXPECTED_DAW:
            raise ValueError("AUD145 source pin differs")
        before = owned.snapshot(pins)
        report["before"] = before
        owned.save(report)
        if errors := owned.source_errors(before, before, pins):
            raise ValueError(f"source baseline failed: {errors}")
        if (sha(REFERENCE / "cases.json"), sha(DAW / "audit/reference-tools/aud145_analytical_r2.py"),
                sha(COMPARATOR)) != (MANIFEST_SHA, GENERATOR_SHA, COMPARATOR_SHA):
            raise ValueError("audited reference or tools differ")
        env = dict(os.environ)
        commands = [("reference", [sys.executable, str(COMPARATOR), "--reference", str(REFERENCE),
                                   "--verify-reference-only"])]
        for i, test in enumerate(ENGINE_TESTS, 1):
            commands.append((f"engine-{i}", ["cargo", "test", "--locked", "--manifest-path",
                                           "sotf-daw/Cargo.toml", "-p", "sotf-engine", "--lib",
                                           test, "--", "--exact", "--test-threads=1"]))
        capture_env = dict(env, AUD145_PLACEMENT_CAPTURE_DIR=str(CAPTURE))
        commands.append(("public-capture", ["cargo", "test", "--locked", "--manifest-path",
                                            "sotf-daw/Cargo.toml", "-p", "sotf-plugin-eq",
                                            "--test", "aud145_ordered_route", PUBLIC_CAPTURE_TEST,
                                            "--", "--ignored", "--exact", "--test-threads=1"]))
        commands.append(("compare", [sys.executable, str(COMPARATOR), "--reference", str(REFERENCE),
                                     "--capture", str(CAPTURE)]))
        for name, argv in commands:
            entry = owned.run_owned(name, argv, report, capture_env if name == "public-capture" else env)
            if entry["status"] != "PASS":
                raise ValueError(f"{name}: command failed or owned cleanup incomplete")
            log = (OUTPUT / "logs" / f"{name}.log").read_text(errors="replace")
            if name.startswith("engine-"):
                named_test(log, ENGINE_TESTS[int(name[-1]) - 1])
            elif name == "public-capture":
                named_test(log, PUBLIC_CAPTURE_TEST)
            elif name == "reference" and "AUD145 r2 reference: 42 cases, 48 verified binaries" not in log:
                raise ValueError("reference verification positive missing")
            elif name == "compare":
                positives = re.findall(r"(?m)^PASS (\d+-(?:2|5)ch-\S+\.f64le) peak=", log)
                if len(positives) != 42 or len(set(positives)) != 42 or \
                        "AUD145 r2: 42 passed, 0 failed" not in log:
                    raise ValueError("public comparison positive inventory differs")
        report["captures"] = validate_capture()
        report["positive_inventory"] = {"engine": 2, "public_capture": 1,
                                        "reference_cases": 42, "comparisons": 42}
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            if pins is None or before is None:
                report["errors"].append("source baseline unavailable")
            else:
                after = owned.snapshot(pins)
                report["after"] = after
                report["errors"].extend(owned.source_errors(before, after, pins))
                if (sha(REFERENCE / "cases.json"), sha(COMPARATOR)) != (MANIFEST_SHA, COMPARATOR_SHA):
                    report["errors"].append("AUD145 reference or comparator changed")
        except BaseException as error:
            report["errors"].append(f"after guard: {type(error).__name__}: {error}")
        report["complete"] = True
        report["status"] = "PASS" if not report["errors"] and not owned.STOP else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
