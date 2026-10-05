#!/usr/bin/env python3
"""Resolve the AUD132 diagnostic realfft fork lock on a disposable Gitea runner."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.release.process_supervision import clean_group, enable_subreaper


FORK_URL = "https://github.com/pierreaubert/realfft.git"
SOURCE_REV = "ac33e6e339caeb5169e23efa871696553c9e626c"
SOURCE_LIB_SHA = "e392a39745cc1c2820c999f1d1b00ba2ef1474105b3c7fd9cacfceab0cadb8fc"
STOP = False


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def save(path: Path, value: object) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, indent=2) + "\n")
    pending.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state(fork: Path) -> dict:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       cwd=fork, text=True).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=fork, text=True).splitlines()
    return {"revision": revision, "status": status,
            "lib_sha256": sha(fork / "src/lib.rs"),
            "manifest_sha256": sha(fork / "Cargo.toml"),
            "readme_sha256": sha(fork / "README.md"),
            "lock_sha256": sha(fork / "Cargo.lock") if (fork / "Cargo.lock").is_file() else None}


def aggregate_state() -> dict:
    return {"revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                cwd=ROOT, text=True).strip(),
            "status": subprocess.check_output(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=ROOT, text=True).splitlines(),
            "sources_sha256": sha(ROOT / "scripts/release/sources.json")}


def run(name: str, argv: list[str], cwd: Path, output: Path, report: dict) -> None:
    if STOP:
        raise KeyboardInterrupt(f"interrupted before {name}")
    log = output / f"{name}.log"
    entry = {"name": name, "argv": argv, "log": str(log), "status": "RUNNING"}
    report["active_command"] = entry
    save(output / "report.json", report)
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["CARGO_TARGET_DIR"] = str(output / "cargo-target")
    with log.open("wb") as stream:
        if STOP:
            raise KeyboardInterrupt(f"interrupted before {name}")
        child = subprocess.Popen(argv, cwd=cwd, env=environment,
                                 stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        code = 130
        started = time.monotonic()
        heartbeats = 0
        try:
            entry["owned_pgid"] = child.pid
            save(output / "report.json", report)
            while not STOP:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= (heartbeats + 1) * 30:
                        heartbeats += 1
                        print(f"realfft {name}: still running", flush=True)
        finally:
            entry["cleanup"] = clean_group(child)
    entry["exit_code"] = code
    entry["status"] = "PASS" if code == 0 and entry["cleanup"]["ok"] else "FAIL"
    report["commands"].append(entry)
    report.pop("active_command", None)
    save(output / "report.json", report)
    if entry["status"] != "PASS" or STOP:
        raise ValueError(f"realfft {name} failed or was interrupted")


def main() -> int:
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    if len(sys.argv) != 2 or os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        print("usage: disposable Gitea CI realfft_lock_resolve.py OUTPUT", file=sys.stderr)
        return 2
    if Path.cwd().resolve() != ROOT:
        print("run from the checked-out aggregate root", file=sys.stderr)
        return 2
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    fork = output / "realfft-fork"
    report: dict = {"status": "FAIL", "commands": [], "errors": [],
                    "source_rev": SOURCE_REV, "source_url": FORK_URL}
    save(output / "report.json", report)
    before = None
    try:
        enable_subreaper()
        if fork.exists():
            raise ValueError("fork checkout already exists")
        root_before = aggregate_state()
        report["aggregate_before"] = root_before
        if root_before["status"]:
            raise ValueError("aggregate checkout is dirty before fork resolution")
        run("clone", ["git", "-c", "credential.helper=", "clone", "--no-checkout",
                      FORK_URL, str(fork)], output, output, report)
        run("checkout", ["git", "checkout", "--detach", SOURCE_REV], fork, output, report)
        before = state(fork)
        report["fork_before"] = before
        save(output / "report.json", report)
        if before["revision"] != SOURCE_REV or before["status"] or before["lib_sha256"] != SOURCE_LIB_SHA:
            raise ValueError("fork source differs from reviewed immutable source")
        if before["lock_sha256"] is not None:
            raise ValueError("source-only fork unexpectedly contains Cargo.lock")
        run("resolve", ["cargo", "generate-lockfile"], fork, output, report)
        run("metadata", ["cargo", "metadata", "--locked", "--format-version", "1"],
            fork, output, report)
        after = state(fork)
        report["fork_after"] = after
        save(output / "report.json", report)
        # Upstream .gitignore excludes Cargo.lock, so status remains clean.
        # Its creation and byte identity are checked separately below.
        if after["revision"] != SOURCE_REV or after["status"]:
            raise ValueError("resolver modified fork source beyond Cargo.lock")
        if (after["lib_sha256"], after["manifest_sha256"], after["readme_sha256"]) != (
                before["lib_sha256"], before["manifest_sha256"], before["readme_sha256"]):
            raise ValueError("resolver changed fork source bytes")
        if after["lock_sha256"] is None:
            raise ValueError("resolver produced no Cargo.lock")
        (output / "Cargo.lock").write_bytes((fork / "Cargo.lock").read_bytes())
    except BaseException as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        try:
            report["aggregate_after"] = aggregate_state()
            if report.get("aggregate_before") != report["aggregate_after"]:
                report["errors"].append("aggregate revision, source manifest, or status changed")
            if before is not None:
                report["fork_final"] = state(fork)
                if report.get("fork_after") != report["fork_final"]:
                    report["errors"].append("fork state changed after resolution")
        except Exception as error:
            report["errors"].append(f"final state inspection failed: {error}")
        report["status"] = "PASS" if not report["errors"] and not STOP else "FAIL"
        save(output / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
