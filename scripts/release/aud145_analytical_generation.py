#!/usr/bin/env python3
"""Generate the new AUD145 mathematical reference in disposable Gitea only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release import nih_native_artifact_check as owned
from scripts.release.checkout_sources import read_manifest

OUTPUT = ROOT / "target/release-gitea/aud145-analytical-r2"
REFERENCE = OUTPUT / "aud145-analytical-reference-r2"
EXPECTED_GENERATOR_SHA = "b595231e814123e8c5134a24edde15ecc303a5b55066af4960133c2f32c8dd76"
EXPECTED_COMPARE_SHA = "fdbd31f20d779e6e4b89c32d1f1f32c2f95955bc7890be8234de2187f7f0936d"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_generated() -> list[dict]:
    manifest = json.loads((REFERENCE / "cases.json").read_text())
    if manifest["generator_sha256"] != EXPECTED_GENERATOR_SHA:
        raise ValueError("reference generator SHA differs")
    files = sorted(REFERENCE.iterdir())
    if len(files) != 49 or any(not path.is_file() for path in files):
        raise ValueError("expected exactly 48 binaries and one manifest")
    return [{"path": str(path.relative_to(OUTPUT)), "bytes": path.stat().st_size,
             "sha256": sha(path)} for path in files]


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("Gitea disposable environment required")
    if sys.flags.optimize != 0 or os.environ.get("PYTHONOPTIMIZE", "0") not in ("", "0"):
        raise SystemExit("Python assertions must be enabled")
    output_exists = OUTPUT.exists()
    if output_exists and any(OUTPUT.iterdir()):
        raise SystemExit("AUD145 output directory must start empty")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=True)
    owned.OUTPUT = OUTPUT
    owned.STOP = False
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    report: dict = {"status": "RUNNING", "complete": False, "commands": [], "errors": [],
                    "scope": "new analytical reference only; no Rust capture or r1 recovery"}
    owned.save(report)
    before = None
    pins = None
    try:
        _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
        before = owned.snapshot(pins)
        report["before"] = before
        owned.save(report)
        initial_errors = owned.source_errors(before, before, pins)
        if initial_errors:
            raise ValueError(f"source baseline failed: {initial_errors}")
        generator = ROOT / "scripts/release/aud145_analytical_r2.py"
        comparator = ROOT / "scripts/release/aud145_compare_r2.py"
        if sha(generator) != EXPECTED_GENERATOR_SHA or sha(comparator) != EXPECTED_COMPARE_SHA:
            raise ValueError("approved reference tool SHA differs")
        env = dict(os.environ, PYTHONOPTIMIZE="0")
        for name, argv in (
            ("generate", [sys.executable, str(generator), "--output", str(REFERENCE)]),
            ("verify", [sys.executable, str(comparator), "--reference", str(REFERENCE),
                        "--verify-reference-only"]),
        ):
            if owned.STOP:
                raise KeyboardInterrupt("stopped before launch")
            entry = owned.run_owned(name, argv, report, env)
            if entry["status"] != "PASS":
                raise ValueError(f"{name} failed or owned cleanup was incomplete")
        verify_log = (OUTPUT / "logs/verify.log").read_text()
        if verify_log.count("AUD145 r2 reference: 42 cases, 48 verified binaries") != 1:
            raise ValueError("42-case/48-binary positive inventory missing")
        report["artifacts"] = audit_generated()
        report["positive_inventory"] = {"cases": 42, "binary_files": 48}
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            if pins is not None and before is not None:
                after = owned.snapshot(pins)
                report["after"] = after
                report["errors"].extend(owned.source_errors(before, after, pins))
            else:
                report["errors"].append("source baseline was unavailable")
        except BaseException as error:
            report["errors"].append(f"after guard: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not report["errors"] and not owned.STOP else "FAIL"
        report["complete"] = True
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
