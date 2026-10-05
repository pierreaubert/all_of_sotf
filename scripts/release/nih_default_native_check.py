#!/usr/bin/env python3
"""Qualify default NIH tests and native Convolution restore on Gitea."""

from __future__ import annotations

import ctypes
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
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.qa import ROOT, host_platform, source_issues, source_state


CASES = {
    "default": {
        "native_clap_fractional_rate_reaches_dsp_and_transport_without_integer_rounding",
        "native_clap_rejects_invalid_rates_before_plugin_initialization",
        "ambisonics_default_order_one_waveform_matches_pre_edit_capture",
    },
    "convolution-clap": {
        "clap_state_restore_stages_true_stereo_resource_and_survives_rejections",
    },
    "convolution-vst3": {
        "vst3_component_state_restore_stages_true_stereo_resource_and_preserves_audio",
    },
}
MANUAL_CAPTURE_IGNORED = (
    "wrapper::process_tests::capture_aud135_pre_edit_ambisonics_native_default_waveform",
    "capture the pre-AUD135 default native wrapper waveform before adapter changes",
)
INTERRUPTED = False


def interrupt(_signum: int, _frame: object) -> None:
    global INTERRUPTED
    INTERRUPTED = True


def write_report(path: Path, report: dict) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def group_members(pgid: int) -> list[dict[str, str]]:
    args = ["ps", "-axo" if sys.platform == "darwin" else "-eo", "pid=,ppid=,pgid=,stat="]
    output = subprocess.run(args, capture_output=True, text=True, check=True, timeout=5).stdout
    found = []
    for row in output.splitlines():
        fields = row.split()
        if len(fields) != 4 or not all(field.isdigit() for field in fields[:3]):
            raise ValueError(f"unparseable process row: {row!r}")
        if int(fields[2]) == pgid:
            found.append(dict(zip(("pid", "ppid", "pgid", "state"), fields, strict=True)))
    return found


def cleanup(child: subprocess.Popen[bytes]) -> dict:
    errors: list[str] = []
    remaining: list[dict[str, str]] = []
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            remaining = group_members(child.pid)
            if not remaining:
                break
        except Exception as error:
            errors.append(f"inspect: {error}")
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"signal: {error}")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                while True:
                    try:
                        pid, _ = os.waitpid(-1, os.WNOHANG)
                    except ChildProcessError:
                        break
                    if pid == 0:
                        break
                remaining = group_members(child.pid)
                if not remaining:
                    break
            except Exception as error:
                errors.append(f"inspect/reap: {error}")
                break
            time.sleep(0.1)
    try:
        child.wait(timeout=5)
        remaining = group_members(child.pid)
    except Exception as error:
        errors.append(f"final: {error}")
    return {"ok": not errors and not remaining, "remaining": remaining, "errors": errors}


def run_owned(name: str, args: list[str], cwd: Path, evidence: Path, report: dict) -> dict:
    log_path = evidence / f"{name}.log"
    entry = {"name": name, "argv": args, "log": log_path.name,
             "status": "RUNNING"}
    if INTERRUPTED:
        raise RuntimeError("interrupted before starting next command")
    with log_path.open("wb") as stream:
        child: subprocess.Popen[bytes] | None = None
        code = 130
        try:
            child = subprocess.Popen(args, cwd=cwd, stdout=stream,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            entry["owned_pgid"] = child.pid
            report["active_command"] = entry
            write_report(evidence / "report.json", report)
            heartbeat = time.monotonic() + 30
            while not INTERRUPTED:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= heartbeat:
                        print(f"[{name}] still running", flush=True)
                        heartbeat = time.monotonic() + 30
        finally:
            if child is not None:
                entry["cleanup"] = cleanup(child)
            report.pop("active_command", None)
    entry.update({"exit_code": code, "status": "PASS" if (code == 0 and not INTERRUPTED
                  and entry["cleanup"]["ok"]) else "FAIL"})
    report["commands"].append(entry)
    write_report(evidence / "report.json", report)
    return entry


def parse_tests(output: str, required: set[str],
                expected_ignored: tuple[str, str] | None = None,
                minimum_positive: int = 1,
                exact_positive: int | None = None) -> dict:
    passed = set(re.findall(r"(?m)^test (\S+) \.\.\. ok$", output))
    ignored = re.findall(r"(?m)^test (\S+) \.\.\. ignored, (.+)$", output)
    matched = {test for test in required if any(full.endswith("::" + test) for full in passed)}
    summaries = re.findall(
        r"test result: ok\.\s+(\d+) passed; (\d+) failed; (\d+) ignored;",
        output,
    )
    allowed_ignored = [expected_ignored] if expected_ignored is not None else []
    accepted = (matched == required and len(summaries) == 1
                and len(passed) >= minimum_positive and ignored == allowed_ignored
                and (exact_positive is None or len(passed) == exact_positive)
                and int(summaries[0][0]) == len(passed)
                and summaries[0][1:] == ("0", str(len(allowed_ignored))))
    return {"positive_count": len(passed), "required_passed": sorted(matched),
            "required": sorted(required), "ignored_inventory": ignored,
            "expected_ignored": allowed_ignored, "summaries": summaries,
            "accepted": accepted}


def run_case(name: str, evidence: Path, report: dict) -> dict:
    args = ["cargo", "test", "--locked", "-p", "plugins-nih", "--lib"]
    if name.startswith("convolution-"):
        args.extend(["--no-default-features", "--features", "convolution"])
        test_name = next(iter(CASES[name]))
        args.append("wrapper::process_tests::native_convolution_state_callbacks::" + test_name)
    args.extend(["--", "--show-output", "--test-threads=1"])
    if name.startswith("convolution-"):
        args.append("--exact")
    entry = run_owned(name, args, ROOT / "sotf-daw", evidence, report)
    output = (evidence / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    inventory = parse_tests(
        output, CASES[name], MANUAL_CAPTURE_IGNORED if name == "default" else None,
        minimum_positive=229 if name == "default" else 1,
        exact_positive=1 if name.startswith("convolution-") else None,
    )
    entry.update(inventory)
    if not inventory["accepted"]:
        entry["status"] = "FAIL"
    write_report(evidence / "report.json", report)
    return entry


def main() -> int:
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    if len(sys.argv) != 2:
        print("usage: nih_default_native_check.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    if (os.environ.get("CI") != "true"
            or os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1"):
        print("NIH gate requires the designated Gitea QA runner", file=sys.stderr)
        return 2
    if sys.platform == "linux":
        if not Path("/.dockerenv").exists() or os.geteuid() != 0:
            print("Linux NIH gate requires a disposable root container", file=sys.stderr)
            return 2
        if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
            print("Linux subreaper setup failed", file=sys.stderr)
            return 2
    evidence = (ROOT / sys.argv[1]).resolve()
    if not evidence.is_relative_to(ROOT / "target" / "release-gitea"):
        print("evidence must be under target/release-gitea", file=sys.stderr)
        return 2
    evidence.mkdir(parents=True, exist_ok=False)
    report: dict = {"status": "RUNNING", "root_revision": None,
                    "commands": [], "errors": [],
                    "native_43_artifact_gate": "required separately: artifact-release-check plugins"}
    before = None
    try:
        _, _, revisions = read_manifest(ROOT / "scripts/release/sources.json")
        layout = root_layout_status(ROOT, revisions)
        report["root_layout_before"] = layout
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            raise RuntimeError(f"invalid pinned root layout before qualification: {layout}")
        report["root_revision"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        report["sources_manifest_sha256"] = hashlib.sha256(
            (ROOT / "scripts/release/sources.json").read_bytes()).hexdigest()
        before = source_state(ROOT, list(workspace_map()), host_platform())
        report["sources_before"] = before
        write_report(evidence / "report.json", report)
        issues = source_issues(before, before, require_clean=True)
        issues.extend(f"{name}: source revision differs from manifest"
                      for name, revision in revisions.items()
                      if before[name].get("revision") != revision)
        if issues:
            raise RuntimeError("source preflight: " + "; ".join(issues))
        for name in CASES:
            if run_case(name, evidence, report)["status"] != "PASS":
                raise RuntimeError(f"{name} NIH test inventory failed")
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        try:
            after = source_state(ROOT, list(workspace_map()), host_platform())
            report["sources_after"] = after
            if before is None:
                report["errors"].append("source before-state unavailable")
            else:
                report["errors"].extend(source_issues(before, after, require_clean=True))
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
            if revision != report["root_revision"]:
                report["errors"].append("root revision changed")
            layout = root_layout_status(ROOT, revisions)
            report["root_layout_after"] = layout
            if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
                report["errors"].append(f"invalid pinned root layout after qualification: {layout}")
            digest = hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest()
            if digest != report["sources_manifest_sha256"]:
                report["errors"].append("sources manifest changed")
        except Exception as error:
            report["errors"].append(f"final guard: {error}")
        report["status"] = "PASS" if not report["errors"] else "FAIL"
        write_report(evidence / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
