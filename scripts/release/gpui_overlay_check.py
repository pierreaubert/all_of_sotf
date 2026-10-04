#!/usr/bin/env python3
"""Qualify the GPUI overlay with rendered UI and named regressions."""

from __future__ import annotations

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


def root_status(names: set[str], platform: str) -> tuple[str, list[str]]:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    lines = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, text=True,
    ).splitlines()
    permitted = {f"?? {name}/" for name in names}
    permitted.add(f"?? release-ui-evidence-{platform}/")
    permitted.add("?? checkout-sources.log")
    permitted.add("?? gpui-overlay-parser-tests.log")
    unknown = [line for line in lines if line not in permitted]
    return revision, unknown


def run(name: str, argv: list[str], cwd: Path, output: Path,
        env: dict[str, str] | None = None) -> dict:
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
                argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
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


def named_test_passed(log: str, name: str) -> bool:
    return (
        re.search(rf"^test {re.escape(name)} \.\.\. ok$", log, re.MULTILINE) is not None
        and re.search(r"^test result: ok\. 1 passed; 0 failed; 0 ignored;", log, re.MULTILINE)
        is not None
    )


def scene_header(output: Path, build_log: Path, target_dir: Path) -> str:
    executed = []
    for line in build_log.read_text(errors="replace").splitlines():
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (event.get("reason") == "build-script-executed"
                and "gpui-toolkit-gpui-macos" in event.get("package_id", "")):
            executed.append(Path(event["out_dir"]).resolve())
    if len(executed) != 1 or not executed[0].is_relative_to(target_dir.resolve()):
        raise RuntimeError(f"expected one current GPUI macOS build-script output, found {executed}")
    header = executed[0] / "scene.h"
    contents = header.read_text(encoding="utf-8")
    if not all(token in contents for token in (
        "typedef uint32_t PaddedBool32;", "PaddedBool32 wavy;",
        "PaddedBool32 grayscale;",
    )):
        raise RuntimeError(f"current GPUI macOS generated scene.h lacks PaddedBool32 ABI: {header}")
    shutil.copy2(header, output / "scene.h")
    return str(header)


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"macos", "linux"}:
        raise SystemExit("usage: gpui_overlay_check.py macos|linux evidence-directory")
    if os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1" or os.environ.get("CI") != "true":
        raise SystemExit("GPUI overlay QA is restricted to the disposable Gitea workflow")
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
        root_before, unknown = root_status(names, platform)
        if unknown:
            raise RuntimeError(f"unowned root changes before QA: {unknown}")
        before = source_state(ROOT, sorted(names), platform)
        report["sources_before"] = before
        for name in names:
            if before[name].get("revision") != pins[name]["revision"]:
                raise RuntimeError(f"{name}: revision differs from sources.json")
        problems = source_issues(before, before, True)
        if problems:
            raise RuntimeError(f"source guard failed before QA: {problems}")
        if platform == "linux":
            enable_subreaper()
        toolkit = ROOT / "gpui-toolkit"
        target_base = toolkit / "target"
        target_base.mkdir(exist_ok=True)
        target_dir = Path(tempfile.mkdtemp(prefix="gpui-overlay-", dir=target_base)).resolve()
        toolkit_env = dict(os.environ, CARGO_TARGET_DIR=str(target_dir))
        commands = [
            ("toolkit-all-features", ["cargo", "check", "--locked", "--workspace", "--all-targets", "--all-features", "--tests", "--message-format=json"], None),
            ("line-wrapper", ["cargo", "test", "--locked", "-p", "gpui-toolkit-gpui", "--lib", "text_system::line_wrapper::tests::test_is_word_char", "--", "--exact"], "text_system::line_wrapper::tests::test_is_word_char"),
            ("scene-abi", ["cargo", "test", "--locked", "-p", "gpui-toolkit-gpui", "--lib", "scene::tests::gpu_boolean_has_u32_layout_and_values", "--", "--exact"], "scene::tests::gpu_boolean_has_u32_layout_and_values"),
            ("headless-geometry", ["cargo", "test", "--locked", "-p", "gpui-d3rs", "--no-default-features", "--test", "headless_surface_tests", "surface_geometry_is_available_to_a_headless_consumer", "--", "--exact"], "surface_geometry_is_available_to_a_headless_consumer"),
        ]
        if platform == "macos":
            commands.append(("metal-atlas", ["cargo", "test", "--locked", "-p", "gpui-toolkit-gpui-macos", "--lib", "metal_atlas::tests::test_metal_texture_is_none_after_last_tile_removed", "--", "--exact"], "metal_atlas::tests::test_metal_texture_is_none_after_last_tile_removed"))
        for name, argv, test in commands:
            result = run(name, argv, toolkit, output, toolkit_env)
            report["commands"].append(result)
            contents = (output / f"{name}.log").read_text(errors="replace")
            if result["exit_code"] != 0 or not result["cleanup_ok"] or (test and not named_test_passed(contents, test)):
                raise RuntimeError(f"{name}: command, cleanup, or positive test inventory failed")
        if platform == "macos":
            report["generated_scene_header"] = scene_header(
                output, output / "toolkit-all-features.log", target_dir,
            )
        result = run("rendered-ui", ["bash", "scripts/release/ui_check.sh", platform], ROOT, output)
        report["commands"].append(result)
        ui_evidence = ROOT / f"release-ui-evidence-{platform}"
        suite = (ui_evidence / "sotf-plugin-workflow-ui.log").read_text(errors="replace")
        if result["exit_code"] != 0 or not result["cleanup_ok"] or not re.search(
            r"^suite complete: 7 passed, 0 skipped, artifacts at ", suite, re.MULTILINE
        ):
            raise RuntimeError("rendered UI did not pass all seven scenarios")
        if platform == "linux" and "AT-SPI smoke passed:" not in (
            ui_evidence / "sotf-atspi-session-bus.log"
        ).read_text(errors="replace"):
            raise RuntimeError("Linux AT-SPI action, focus, and tree proof missing")
    except BaseException as exc:
        report["errors"].append(str(exc))
    finally:
        if before:
            try:
                after = source_state(ROOT, sorted(names), platform)
                report["sources_after"] = after
                report["errors"].extend(source_issues(before, after, True))
                current_root, unknown = root_status(names, platform)
                if current_root != root_before or unknown:
                    report["errors"].append(f"root source changed or unowned files appeared: {unknown}")
            except Exception as exc:
                report["errors"].append(f"source after-guard failed: {exc}")
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for error in report["errors"]:
        print(f"GPUI overlay QA failure: {error}", file=sys.stderr)
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
