#!/usr/bin/env python3
"""Capture the rejected JBL PEQ candidate under the original QA command."""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import enable_subreaper
from scripts.release import nih_native_artifact_check as owned

OUT = ROOT / "target/release-gitea/autoeq-jbl-diagnostic"
STOP = False
EXPECTED_AUTOEQ = "f97caeedb9f233745a1f915fe9726107cbcc467b"
ARGS = [
    "./target/release/autoeq", "--speaker=JBL M2", "--version", "eac",
    "--measurement", "CEA2034", "--algo", "autoeq:de", "--loss", "speaker-score",
    "-n", "7", "--min-freq=20", "--max-q=6", "--peq-model", "hp-pk",
    "--maxeval", "100000", "--qa", "0.5",
]


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True
    owned.STOP = True


def save(report: dict) -> None:
    pending = OUT / "report.pending"
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(OUT / "report.json")


def snapshot(pins: dict[str, str]) -> dict:
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest(),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": qa.source_state(ROOT, list(workspace_map()), "linux"),
    }


def source_errors(before: dict, after: dict, pins: dict[str, str]) -> list[str]:
    errors = qa.source_issues(before["workspaces"], after["workspaces"], True)
    if before["root_revision"] != after["root_revision"]:
        errors.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        errors.append("source manifest changed")
    for state in (before, after):
        layout = state["root_layout"]
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            errors.append(f"root gitlink layout differs: {layout}")
        if set(layout["tracked_gitlinks"]) != set(pins):
            errors.append("nine pinned gitlinks incomplete")
        for name, pin in pins.items():
            source = state["workspaces"].get(name, {})
            if source.get("revision") != pin or not source.get("lock_sha256"):
                errors.append(f"{name}: pin or lock mismatch")
            if name == "autoeq" and not source.get("nested_lock_sha256"):
                errors.append("AutoEQ nested lock missing")
    if before["root_layout"] != after["root_layout"]:
        errors.append("root gitlink layout changed")
    return errors


def candidate_evidence(log: str) -> dict:
    if "spacing repair refused: within_bounds=true, spacing=0" not in log:
        raise ValueError("original strict JBL spacing refusal missing")
    budget = re.findall(
        r"DE maxeval=(\d+) with population_size=(\d+).*?Running (\d+) generations \(≈(\d+) evals\)",
        log, re.DOTALL,
    )
    if len(budget) != 1 or budget[0][0] != "100000" or int(budget[0][3]) > 100000:
        raise ValueError("declared DE budget differs from the 100000-evaluation recipe")
    rows = re.findall(r"rejected PEQ candidate (.+?): (model=[^\n]+)", log)
    if len(rows) != 1:
        raise ValueError("expected one complete rejected-candidate row")
    candidate_id, row = rows[0]
    scalars = {}
    for key in ("raw_ceiling", "projected_ceiling", "final_ceiling",
                "final_spacing", "final_min_gain", "final_loss"):
        match = re.search(rf"\b{key}=([^ ]+)", row)
        if match is None:
            raise ValueError(f"missing {key}")
        scalars[key] = float(match.group(1))
    if any(not math.isfinite(value) for value in scalars.values()):
        raise ValueError("nonfinite candidate diagnostic")
    if scalars["final_ceiling"] <= 0 or scalars["final_spacing"] != 0:
        raise ValueError("diagnostic does not describe the JBL ceiling-after-spacing refusal")
    vectors = {}
    for key in ("raw", "projected", "finalized", "lower", "upper"):
        match = re.search(rf"\b{key}=(\[[^\]]+\])", row)
        if match is None:
            raise ValueError(f"missing {key} vector")
        values = ast.literal_eval(match.group(1))
        if not isinstance(values, list) or not values or any(
            not isinstance(value, (int, float)) or not math.isfinite(value) for value in values
        ):
            raise ValueError(f"invalid {key} vector")
        vectors[key] = values
    if len({len(values) for values in vectors.values()}) != 1:
        raise ValueError("candidate and bound vector lengths differ")
    return {"candidate_id": candidate_id, "declared_budget": budget[0],
            "backend_evaluations_observed": False,
            "constraint_residuals": scalars, "vector_length": len(vectors["raw"]),
            "vectors": vectors}


def main() -> int:
    if (os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1"
            or not Path("/.dockerenv").exists() or Path("/dev/snd").exists()):
        raise RuntimeError("disposable audio-device-free Linux runner required")
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / "logs").mkdir()
    owned.OUTPUT = OUT
    owned.STOP = False
    enable_subreaper()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    before = snapshot(pins)
    report = {"status": "RUNNING", "complete": False, "source_before": before, "commands": []}
    save(report)
    try:
        if pins.get("autoeq") != EXPECTED_AUTOEQ or source_errors(before, before, pins):
            raise ValueError("pinned diagnostic AutoEQ source preflight failed")
        build = owned.run_owned(
            "build-autoeq",
            ["cargo", "build", "--locked", "--manifest-path", "autoeq/Cargo.toml",
             "--release", "--features", "cli", "--bin", "autoeq"],
            report, os.environ.copy(),
        )
        if build["status"] != "PASS":
            raise ValueError("AutoEQ release CLI build failed")
        # run_owned uses ROOT as cwd; the original Just recipe runs within autoeq/.
        owned.ROOT = ROOT / "autoeq"
        diagnostic = owned.run_owned("qa-jbl-m2-score", ARGS, report, os.environ.copy())
        log = Path(diagnostic["log"])
        report["qa_log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
        if diagnostic["exit_code"] == 0 or not diagnostic["owned_group_cleanup"]["ok"]:
            raise ValueError("original QA did not produce a cleanly contained red result")
        report["candidate"] = candidate_evidence(log.read_text(errors="replace"))
        report["expected_failure_evidence"] = True
    except (Exception, KeyboardInterrupt) as error:
        report["failure"] = str(error)
    finally:
        try:
            after = snapshot(pins)
            report["source_after"] = after
            report["source_issues"] = source_errors(before, after, pins)
        except Exception as error:
            report["source_issues"] = [f"final source snapshot failed: {error}"]
        report["status"] = "REVIEW_REQUIRED" if (
            len(report["commands"]) == 2 and report.get("expected_failure_evidence")
            and not STOP and not owned.STOP and not report.get("failure")
            and not report["source_issues"]
        ) else "FAIL"
        report["complete"] = False
        save(report)
    # Capturing the original failed QA never qualifies a release.
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
