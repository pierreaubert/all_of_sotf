#!/usr/bin/env python3
"""Qualify the isolated Rubato trim and exact fractional-rate DSP paths."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release.generated_roomeq_check import enable_subreaper, stop_group
from scripts.release.qa import source_issues, source_state, workspace_map

STOP_REQUESTED = False


def interrupted(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def run(name: str, argv: list[str], cwd: Path, output: Path) -> dict:
    if STOP_REQUESTED:
        raise KeyboardInterrupt
    log = output / f"{name}.log"
    with log.open("w", encoding="utf-8") as stream:
        child: subprocess.Popen | None = None
        status = 1
        was_interrupted = False
        cleanup_ok, survivors, cleanup_errors = False, [], []
        try:
            child = subprocess.Popen(
                argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            print(f"[{name}] owned PID {child.pid}: {' '.join(argv)}", flush=True)
            next_heartbeat = time.monotonic() + 30
            while True:
                if STOP_REQUESTED:
                    status, was_interrupted = 130, True
                    break
                try:
                    status = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= next_heartbeat:
                        print(f"[{name}] still running, owned PID {child.pid}", flush=True)
                        next_heartbeat = time.monotonic() + 30
        finally:
            if child is not None:
                cleanup_ok, survivors, cleanup_errors = stop_group(child)
        if STOP_REQUESTED:
            status = 130
            was_interrupted = True
    return {
        "name": name, "argv": argv, "exit_code": status,
        "cleanup_ok": cleanup_ok, "survivors": survivors,
        "cleanup_errors": cleanup_errors, "interrupted": was_interrupted,
        "log": str(log.relative_to(ROOT)),
    }


def exact_test_ok(text: str, test: str) -> bool:
    return (
        re.search(rf"^test {re.escape(test)} \.\.\. ok$", text, re.MULTILINE) is not None
        and re.search(r"^test result: ok\. 1 passed; 0 failed; 0 ignored;", text, re.MULTILINE)
        is not None
    )


def full_test_counts(text: str) -> tuple[int, int]:
    summaries = re.findall(
        r"^test result: ok\. (\d+) passed; 0 failed; (\d+) ignored;", text, re.MULTILINE
    )
    return sum(int(passed) for passed, _ in summaries), sum(int(ignored) for _, ignored in summaries)


def root_clean(names: set[str]) -> tuple[str, list[str]]:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    lines = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True,
    ).splitlines()
    allowed = {f"?? {name}/" for name in names} | {"?? checkout-sources.log"}
    return revision, sorted(set(lines) - allowed)


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"macos", "linux"}:
        raise SystemExit("usage: rubato_fractional_check.py macos|linux evidence-directory")
    if os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1" or os.environ.get("CI") != "true":
        raise SystemExit("Rubato fractional QA is restricted to the disposable Gitea workflow")
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    platform, output = sys.argv[1], (ROOT / sys.argv[2]).resolve()
    if not output.is_relative_to(ROOT / "target"):
        raise SystemExit("evidence directory must be under root target/")
    output.mkdir(parents=True, exist_ok=True)
    names = set(workspace_map())
    pins = json.loads((ROOT / "scripts/release/sources.json").read_text())["sources"]
    report: dict = {"platform": platform, "commands": [], "errors": []}
    before: dict = {}
    root_before = ""
    try:
        root_before, unexpected = root_clean(names)
        if unexpected:
            raise RuntimeError(f"unowned root changes before QA: {unexpected}")
        before = source_state(ROOT, sorted(names), platform)
        report["sources_before"] = before
        problems = source_issues(before, before, True)
        for name in names:
            if before[name].get("revision") != pins[name]["revision"]:
                problems.append(f"{name}: source differs from pinned revision")
        if problems:
            raise RuntimeError(f"source guard failed before QA: {problems}")
        if platform == "linux":
            enable_subreaper()

        math = ROOT / "math-audio"
        daw = ROOT / "sotf-daw"
        rubato_source = math / "crates/3rdparties/rubato"
        with tempfile.TemporaryDirectory(prefix="rubato-standalone-") as temporary:
            standalone = Path(temporary) / "rubato"
            shutil.copytree(rubato_source, standalone, ignore=shutil.ignore_patterns("target", "Cargo.lock"))
            generated = run("rubato-lock-resolution", ["cargo", "generate-lockfile"], standalone, output)
            report["commands"].append(generated)
            lock = standalone / "Cargo.lock"
            rubato_ready = generated["exit_code"] == 0 and generated["cleanup_ok"] and lock.is_file()
            lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest() if rubato_ready else None
            if rubato_ready:
                report["standalone_lock_sha256"] = lock_hash
                shutil.copy2(lock, output / "rubato-standalone.Cargo.lock")
            else:
                report["errors"].append("standalone Rubato lock resolution failed")
            if not generated["cleanup_ok"]:
                raise RuntimeError("standalone Rubato process group did not clean up")
            commands = [
                ("rubato-async", standalone, ["cargo", "test", "--locked", "--lib", "tests::process_all_matches_incremental_output_after_delay_trim", "--", "--exact"], "tests::process_all_matches_incremental_output_after_delay_trim"),
                ("rubato-fft", standalone, ["cargo", "test", "--locked", "--lib", "tests::process_all_fft_matches_incremental_output_after_delay_trim", "--", "--exact"], "tests::process_all_fft_matches_incremental_output_after_delay_trim"),
                ("rubato-empty", standalone, ["cargo", "test", "--locked", "--lib", "tests::process_all_empty_clip_returns_empty_output", "--", "--exact"], "tests::process_all_empty_clip_returns_empty_output"),
                ("rubato-mask", standalone, ["cargo", "test", "--locked", "--lib", "tests::process_all_preserves_active_channel_mask", "--", "--exact"], "tests::process_all_preserves_active_channel_mask"),
                ("rubato-invalid-mask", standalone, ["cargo", "test", "--locked", "--lib", "tests::wrong_length_mask_returns_error", "--", "--exact"], "tests::wrong_length_mask_returns_error"),
                ("rubato-all-targets", standalone, ["cargo", "test", "--locked", "--all-features", "--all-targets"], None),
                ("factory-fractional", daw, ["cargo", "test", "--locked", "-p", "sotf-plugins", "--lib", "factory::tests::ab_compare_factory_accepts_exact_fractional_nested_clock", "--", "--exact"], "factory::tests::ab_compare_factory_accepts_exact_fractional_nested_clock"),
                ("convolution-fractional", daw, ["cargo", "test", "--locked", "-p", "sotf-plugin-convolution", "--lib", "tests::fractional_host_rate_ir_keeps_duration_channels_and_impulse_origin", "--", "--exact"], "tests::fractional_host_rate_ir_keeps_duration_channels_and_impulse_origin"),
                ("engine-staging", daw, ["cargo", "test", "--locked", "-p", "sotf-engine", "--lib", "engine::decoder_thread::tests::test_resample_staging_emits_full_frame_size_blocks", "--", "--exact"], "engine::decoder_thread::tests::test_resample_staging_emits_full_frame_size_blocks"),
            ]
            for name, cwd, argv, test in commands:
                if cwd == standalone and not rubato_ready:
                    report["commands"].append({"name": name, "status": "NOT_RUN_NO_LOCK"})
                    continue
                if STOP_REQUESTED:
                    report["errors"].append("interrupted before remaining Rubato commands")
                    break
                result = run(name, argv, cwd, output)
                report["commands"].append(result)
                contents = (output / f"{name}.log").read_text(errors="replace")
                if test:
                    positive = exact_test_ok(contents, test)
                else:
                    passed, ignored = full_test_counts(contents)
                    result["test_counts"] = {"passed": passed, "ignored": ignored}
                    positive = passed > 0 and ignored == 0
                if result["exit_code"] or not result["cleanup_ok"] or not positive:
                    report["errors"].append(f"{name}: command, cleanup, or positive test inventory failed")
                if not result["cleanup_ok"] or result["interrupted"]:
                    break
                if cwd == standalone and hashlib.sha256(lock.read_bytes()).hexdigest() != lock_hash:
                    report["errors"].append("standalone Rubato lock changed after locked tests")
                    break
    except BaseException as exc:
        report["errors"].append(str(exc))
    finally:
        if before:
            try:
                after = source_state(ROOT, sorted(names), platform)
                report["sources_after"] = after
                report["errors"].extend(source_issues(before, after, True))
                root_after, unexpected = root_clean(names)
                if root_after != root_before or unexpected:
                    report["errors"].append(f"root source changed or unowned files appeared: {unexpected}")
            except Exception as exc:
                report["errors"].append(f"source after-guard failed: {exc}")
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for error in report["errors"]:
        print(f"Rubato fractional QA failure: {error}", file=sys.stderr)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
