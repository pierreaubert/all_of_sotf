#!/usr/bin/env python3
"""Check the candidate Zed GPUI dependency closure without changing release refs."""

from __future__ import annotations

import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.checkout_sources import read_manifest
from scripts.release.qa import ROOT, source_issues, source_state
from scripts.release.spectrum_lowrate_check import enable_subreaper, stop_group


def run(name: str, command: list[str], out: Path) -> dict:
    log = out / f"{name}.log"
    with log.open("w", encoding="utf-8") as stream:
        child = subprocess.Popen(command, cwd=ROOT / "gpui-toolkit", stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        interrupted = False
        try:
            deadline = time.monotonic() + 3600
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    code = 124
                    break
                try:
                    code = child.wait(timeout=min(30, remaining))
                    break
                except subprocess.TimeoutExpired:
                    print(f"[{name}] still running; owned leader PID {child.pid}", flush=True)
        except KeyboardInterrupt:
            code = 130
            interrupted = True
        finally:
            cleanup_ok, survivors, inspection_errors = stop_group(child)
    text = log.read_text(errors="replace")
    tests = re.findall(r"^test (\S+) \.\.\. ok$", text, re.MULTILINE)
    return {"name": name, "argv": command, "exit_code": code,
            "interrupted": interrupted,
            "cleanup_ok": cleanup_ok, "owned_group_survivors": survivors,
            "cleanup_inspection_errors": inspection_errors,
            "positive_tests": len(tests), "log": str(log.relative_to(ROOT))}


def main() -> int:
    def interrupted(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    if len(sys.argv) != 2 or sys.argv[1] not in {"linux", "macos"}:
        print("usage: zed-gpui-trial-check.py linux|macos", file=sys.stderr)
        return 2
    platform = sys.argv[1]
    if (sys.platform == "darwin") != (platform == "macos"):
        print("runner platform does not match requested platform", file=sys.stderr)
        return 2
    evidence = ROOT / f"zed-gpui-trial-{platform}"
    evidence.mkdir(exist_ok=False)
    before = source_state(ROOT, list(workspace_map()), platform)
    (evidence / "sources-before.json").write_text(json.dumps(before, indent=2))
    results: list[dict] = []
    errors: list[str] = []
    try:
        if platform == "linux":
            enable_subreaper()
        _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
        errors.extend(source_issues(before, before, require_clean=True))
        for name, revision in pins.items():
            if before[name]["revision"] != revision:
                errors.append(f"{name}: checkout differs from pinned revision")
        packages = tomllib.loads((ROOT / "gpui-toolkit/Cargo.lock").read_text())["package"]
        fork = "git+https://github.com/pierreaubert/zed.git?rev=3a0ea890ddf8e6247e38c795a960eb18f5182113#3a0ea890ddf8e6247e38c795a960eb18f5182113"
        for package in ("collections", "gpui_util", "media"):
            selected = [item for item in packages if item["name"] == package]
            if len(selected) != 1 or selected[0].get("source") != fork:
                errors.append(f"{package}: candidate fork identity absent or ambiguous")
        if errors:
            raise RuntimeError("source guard failed before GPUI qualification")
        commands = [
            ("metadata", ["cargo", "metadata", "--locked", "--format-version", "1"], False),
            ("all-targets", ["cargo", "check", "--workspace", "--all-targets", "--locked"], False),
            ("gpui-test-support", ["cargo", "test", "--locked", "-p", "gpui-toolkit-gpui",
                                   "--features", "test-support", "--lib"], True),
            ("fork-collections", ["cargo", "test", "--locked", "-p", "collections"], True),
            ("fork-gpui-util", ["cargo", "test", "--locked", "-p", "gpui_util"], True),
            ("fork-media", ["cargo", "test", "--locked", "-p", "media"], True),
            ("toolkit-util", ["cargo", "test", "--locked", "-p", "gpui-toolkit-util"], True),
            ("vendored-inventory", ["cargo", "test", "--locked", "-p", "gpui-release-gates",
                                    "vendored_patches"], True),
        ]
        for name, argv, requires_tests in commands:
            result = run(name, argv, evidence)
            results.append(result)
            if result["exit_code"] or not result["cleanup_ok"] or (requires_tests and not result["positive_tests"]):
                errors.append(f"{name}: command failed or ran zero tests")
                break
    except (KeyboardInterrupt, Exception) as exc:
        errors.append(str(exc))
    after = source_state(ROOT, list(workspace_map()), platform)
    (evidence / "sources-after.json").write_text(json.dumps(after, indent=2))
    errors.extend(source_issues(before, after, require_clean=True))
    report = {"status": "PASS" if not errors else "FAIL", "platform": platform,
              "errors": errors, "commands": results}
    (evidence / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
