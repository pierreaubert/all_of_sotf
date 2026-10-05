#!/usr/bin/env python3
"""Qualify the GPUI host lint repair with owned commands and pinned sources."""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
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

OUTPUT = ROOT / "target/release-gitea/gpui-lint-824"
TESTS = {
    "geometry-field": "mesh_plot::mesh_plot_chart::tests::retained_3d_field_update_keeps_prepared_geometry",
    "geometry-viewport": "mesh_plot::mesh_plot_chart::tests::retained_3d_viewport_and_selection_updates_keep_geometry_payload",
    "miniapp-menu": "tests::test_build_menus_with_language_basic",
}


def test_result(log: str, name: str) -> bool:
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", line).strip() for line in log.splitlines()]
    passed = [line for line in lines if line == f"test {name} ... ok"]
    summaries = [line for line in lines if line.startswith("test result:")]
    return (len(passed) == 1 and len(summaries) == 1 and
            summaries[0].startswith("test result: ok. 1 passed; 0 failed; 0 ignored;") and
            not any("FAILED" in line or "test result: FAILED" in line for line in lines))


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        print("Gitea disposable runner required", file=sys.stderr)
        return 2
    if sys.platform not in ("linux", "darwin"):
        print("Linux or macOS required", file=sys.stderr)
        return 2
    if sys.platform == "darwin" and platform.machine() != "arm64":
        print("Apple Silicon required", file=sys.stderr)
        return 2
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=True)
    owned.OUTPUT = OUTPUT
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    owned.enable_subreaper()
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {"status": "RUNNING", "commands": [], "errors": [], "inventory": {}}
    before = None
    try:
        before = owned.snapshot(pins)
        report["before"] = before
        owned.save(report)
        report["errors"].extend(owned.source_errors(before, before, pins))
        if report["errors"]:
            return 1
        env = os.environ.copy()
        original_home = Path.home()
        env.setdefault("CARGO_HOME", str(original_home / ".cargo"))
        env.setdefault("RUSTUP_HOME", str(original_home / ".rustup"))
        for key in ("CARGO_HOME", "RUSTUP_HOME"):
            if not Path(env[key]).is_absolute():
                raise ValueError(f"{key} must be an absolute toolchain path")
        private = OUTPUT / "private-home"
        private.mkdir(exist_ok=True)
        (private / ".cargo").mkdir(exist_ok=True)
        if list((private / ".cargo").iterdir()):
            raise ValueError("private HOME Cargo configuration is not empty")
        env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
                   XDG_CACHE_HOME=str(private / "cache"), XDG_DATA_HOME=str(private / "data"),
                   PULSE_SERVER=f"unix:{OUTPUT}/no-pulse", PIPEWIRE_REMOTE="no-pipewire",
                   JACK_NO_START_SERVER="1")
        commands = [
            ("lint-host", ["bash", "-c", "cd gpui-toolkit && just lint-host"], None),
            ("geometry-field", ["cargo", "test", "--locked", "--manifest-path", "gpui-toolkit/Cargo.toml", "-p", "gpui-px", "--features", "gpu-3d", "--lib", TESTS["geometry-field"], "--", "--exact", "--show-output"], TESTS["geometry-field"]),
            ("geometry-viewport", ["cargo", "test", "--locked", "--manifest-path", "gpui-toolkit/Cargo.toml", "-p", "gpui-px", "--features", "gpu-3d", "--lib", TESTS["geometry-viewport"], "--", "--exact", "--show-output"], TESTS["geometry-viewport"]),
            ("miniapp-menu", ["cargo", "test", "--locked", "--manifest-path", "gpui-toolkit/Cargo.toml", "-p", "gpui-miniapp", "--lib", TESTS["miniapp-menu"], "--", "--exact", "--show-output"], TESTS["miniapp-menu"]),
        ]
        for name, argv, test_name in commands:
            if owned.STOP:
                raise KeyboardInterrupt("interrupted before command")
            entry = owned.run_owned(name, argv, report, env)
            if entry["status"] != "PASS":
                report["errors"].append(f"{name} command or cleanup failed")
                break
            if test_name is not None:
                transcript = Path(entry["log"]).read_text(errors="replace")
                if not test_result(transcript, test_name):
                    report["errors"].append(f"{name} exact positive inventory missing")
                    break
                report["inventory"][name] = {"test": test_name, "passed": 1, "failed": 0, "ignored": 0}
    except KeyboardInterrupt:
        report["errors"].append("interrupted")
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if owned.STOP:
            report["errors"].append("interrupted")
        try:
            after = owned.snapshot(pins)
            report["after"] = after
            if before is not None:
                report["errors"].extend(owned.source_errors(before, after, pins))
        except Exception as error:
            report["errors"].append(f"after snapshot failed: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not owned.STOP and not report["errors"] and len(report["commands"]) == 4 and len(report["inventory"]) == 3 else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
