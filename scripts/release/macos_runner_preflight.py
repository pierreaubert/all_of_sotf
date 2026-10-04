#!/usr/bin/env python3
"""Record a bounded, read-only lifecycle probe on the pinned macOS runner."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SECONDS = 120
INTERVAL = 10


def command(*argv: str) -> str:
    try:
        result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {type(error).__name__}"
    return result.stdout.strip() if result.returncode == 0 else f"exit {result.returncode}"


def root_state() -> dict[str, str]:
    manifest = (ROOT / "scripts/release/sources.json").read_bytes()
    return {
        "revision": command("git", "rev-parse", "HEAD"),
        "tracked_status": command("git", "status", "--porcelain", "--untracked-files=no"),
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
    }


def snapshot() -> dict[str, object]:
    disk = shutil.disk_usage(ROOT)
    return {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "own_pid_status": command("ps", "-p", str(os.getpid()), "-o", "pid=,ppid=,stat=,rss=,etime="),
        "disk_total_bytes": disk.total,
        "disk_free_bytes": disk.free,
        "physical_memory_bytes": command("sysctl", "-n", "hw.memsize"),
    }


def write(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: macos_runner_preflight.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    evidence = (ROOT / sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    if sys.platform != "darwin":
        write(evidence / "report.json", {
            "status": "FAIL",
            "scope": "runner lifecycle only; no build readiness verdict",
            "error": f"expected Darwin runner, got {sys.platform}",
        })
        return 1
    stopped: list[int] = []

    def on_signal(number: int, _frame: object) -> None:
        stopped.append(number)
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    os.environ["RUSTUP_AUTO_INSTALL"] = "0"
    initial = root_state()
    details = {
        "os": command("sw_vers"),
        "uname": command("uname", "-srm"),
        "rustc": command("rustc", "--version"),
        "cargo": command("cargo", "--version"),
        "python": command("python3", "--version"),
        "just": command("just", "--version"),
        "xcode": command("xcodebuild", "-version"),
        "github_sha": os.environ.get("GITHUB_SHA", ""),
    }
    write(evidence / "source-before.json", initial)
    write(evidence / "toolchain.json", details)
    beats: list[dict[str, object]] = []
    error = ""
    try:
        for _ in range(SECONDS // INTERVAL + 1):
            beats.append(snapshot())
            write(evidence / "heartbeats.json", beats)
            print(f"macOS runner heartbeat {len(beats)}", flush=True)
            if len(beats) <= SECONDS // INTERVAL:
                time.sleep(INTERVAL)
    except KeyboardInterrupt:
        error = f"signal {stopped[-1]}" if stopped else "interrupted"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    after = root_state()
    write(evidence / "source-after.json", after)
    if after != initial:
        error = (error + "; " if error else "") + "root source changed"
    if initial["revision"] != details["github_sha"]:
        error = (error + "; " if error else "") + "checkout revision differs from Gitea event"
    write(evidence / "report.json", {
        "status": "PASS" if not error else "FAIL",
        "scope": "runner lifecycle only; no build readiness verdict",
        "error": error,
        "heartbeat_count": len(beats),
    })
    return 0 if not error else 1


if __name__ == "__main__":
    raise SystemExit(main())
