#!/usr/bin/env python3
"""Qualify the pinned rfd portal and pollster wake path in disposable Gitea CI."""
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
import time
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release import qa
from scripts.release.process_supervision import clean_group, enable_subreaper

STOP = False
OUTPUT = ROOT / "target/release-gitea/native-dialog-linux"
MODES = ("open", "folder", "save", "cancel")
POLLSTER_CHECKSUM = "bc6355899e1c9462875b6757c79f3caa011a1fdae12bbb1a2e72dd1f234f8336"


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def save(report: dict) -> None:
    path = OUTPUT / "report.json"
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(path)


def source_snapshot(pins: dict[str, str]) -> dict:
    state = qa.source_state(ROOT, list(workspace_map()), "linux")
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest(),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": state,
    }


def source_errors(before: dict, after: dict, pins: dict[str, str]) -> list[str]:
    errors = qa.source_issues(before["workspaces"], after["workspaces"], True)
    if before["root_revision"] != after["root_revision"]:
        errors.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        errors.append("sources.json changed")
    if before["root_layout"] != after["root_layout"]:
        errors.append("root checkout layout changed")
    for label, snapshot in (("before", before), ("after", after)):
        layout = snapshot["root_layout"]
        if layout["unexpected"] or layout["missing"]:
            errors.append(f"{label} root layout invalid: {layout}")
        if layout["allowed_siblings"] or set(layout["tracked_gitlinks"]) != set(pins):
            errors.append(f"{label} root layout differs from exact pinned gitlinks: {layout}")
        for name, revision in pins.items():
            if snapshot["workspaces"].get(name, {}).get("revision") != revision:
                errors.append(f"{label} {name} differs from pinned revision")
    return errors


def run_owned(name: str, argv: list[str], report: dict, env: dict[str, str] | None = None) -> dict:
    if STOP:
        raise KeyboardInterrupt("stopped before command launch")
    log = OUTPUT / "logs" / f"{name}.log"
    entry = {"name": name, "argv": argv, "log": str(log), "status": "RUNNING"}
    report["active_command"] = entry
    save(report)
    with log.open("w") as stream:
        if STOP:
            raise KeyboardInterrupt("stopped before process launch")
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        status = 130
        try:
            entry["owned_pgid"] = child.pid
            save(report)
            heartbeat = time.monotonic()
            while not STOP:
                try:
                    status = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - heartbeat >= 30:
                        print(f"[{name}] still running", flush=True)
                        heartbeat = time.monotonic()
        finally:
            entry["owned_group_cleanup"] = clean_group(child)
    entry["exit_code"] = status
    entry["status"] = "PASS" if status == 0 and not STOP and entry["owned_group_cleanup"]["ok"] else "FAIL"
    report["commands"].append(entry)
    report.pop("active_command", None)
    save(report)
    return entry


def prepare_wake_project() -> Path:
    project = OUTPUT / "pollster-wake"
    source = project / "src"
    source.mkdir(parents=True, exist_ok=False)
    (project / "Cargo.toml").write_text(
        '[package]\nname = "rfd-pollster-wake-qa"\nversion = "0.0.0"\nedition = "2021"\n'
        '[dependencies]\npollster = "=1.0.1"\n'
    )
    shutil.copyfile(ROOT / "scripts/release/rfd_pollster_wake.rs", source / "lib.rs")
    return project


def check_wake_lock(project: Path) -> None:
    packages = tomllib.loads((project / "Cargo.lock").read_text())["package"]
    matches = [package for package in packages if package["name"] == "pollster"]
    if len(matches) != 1 or matches[0].get("version") != "1.0.1" or matches[0].get("checksum") != POLLSTER_CHECKSUM:
        raise ValueError(f"standalone pollster lock has unexpected identity: {matches}")


def check_wake_result(log: Path) -> None:
    body = log.read_text(errors="replace")
    if not re.search(r"^test tests::cross_thread_wake_resumes_pending_future \.\.\. ok$", body, re.MULTILINE):
        raise ValueError("cross-thread pending/wake test did not pass by name")
    if not re.search(r"^test result: ok\. 1 passed; 0 failed; 0 ignored;", body, re.MULTILINE):
        raise ValueError("cross-thread pending/wake inventory was not exactly one pass")


def check_dialog_results() -> None:
    for mode in MODES:
        log = OUTPUT / "logs" / f"{mode}.log"
        window = OUTPUT / "logs" / f"{mode}-window.log"
        screenshot = OUTPUT / "screenshots" / f"{mode}.png"
        if (f"PASS SOTF RFD {mode}" not in log.read_text(errors="replace").splitlines()
                or "painted-dialog=1" not in window.read_text(errors="replace")
                or "visible-window-id=" not in window.read_text(errors="replace")
                or not screenshot.is_file() or screenshot.stat().st_size == 0):
            raise ValueError(f"{mode} lacked selected-path/content/cancel, painted dialog or current screenshot evidence")


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1" or not Path("/.dockerenv").exists():
        print("Gitea disposable Linux container required", file=sys.stderr)
        return 2
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    enable_subreaper()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=False)
    (OUTPUT / "screenshots").mkdir(exist_ok=False)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {"status": "RUNNING", "commands": [], "errors": []}
    before: dict | None = None
    try:
        before = source_snapshot(pins)
        report["before"] = before
        save(report)
        report["errors"].extend(source_errors(before, before, pins))
        if report["errors"]:
            return 1
        project = prepare_wake_project()
        manifest = str(project / "Cargo.toml")
        if run_owned("wake-lock", ["cargo", "generate-lockfile", "--manifest-path", manifest], report)["status"] != "PASS":
            report["errors"].append("standalone pollster lock resolution failed")
            return 1
        check_wake_lock(project)
        if run_owned("wake-test", ["cargo", "test", "--locked", "--manifest-path", manifest,
                                   "--", "--show-output"], report)["status"] != "PASS":
            report["errors"].append("pollster pending/wake test failed")
            return 1
        check_wake_result(OUTPUT / "logs/wake-test.log")
        env = os.environ.copy()
        env["RFD_EVIDENCE_DIR"] = str(OUTPUT)
        env["XDG_CURRENT_DESKTOP"] = "GNOME"
        env["XDG_SESSION_TYPE"] = "x11"
        env["PATH"] = "/usr/libexec:" + env.get("PATH", "")
        portal = (
            f'openbox >"{OUTPUT}/logs/openbox.log" 2>&1 & '
            f'xdg-desktop-portal-gtk >"{OUTPUT}/logs/portal-gtk.log" 2>&1 & '
            f'xdg-desktop-portal >"{OUTPUT}/logs/portal.log" 2>&1 & '
            'exec bash scripts/release/native_dialog_check.sh'
        )
        argv = ["xvfb-run", "-a", "-s", "-screen 0 2560x1600x24", "dbus-run-session",
                "--", "bash", "-c", portal]
        if run_owned("portal-dialogs", argv, report, env)["status"] != "PASS":
            report["errors"].append("native portal dialog process failed")
            return 1
        check_dialog_results()
    except KeyboardInterrupt:
        report["errors"].append("interrupted")
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if STOP:
            report["errors"].append("interrupted")
        try:
            after = source_snapshot(pins)
            report["after"] = after
            if before is not None:
                report["errors"].extend(source_errors(before, after, pins))
        except Exception as error:
            report["errors"].append(f"after snapshot failed: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not report["errors"] and len(report["commands"]) == 3 else "FAIL"
        save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
