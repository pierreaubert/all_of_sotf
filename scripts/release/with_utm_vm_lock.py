#!/usr/bin/env python3
"""Serialize Gitea jobs that operate on the same UTM guest."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import time


class Interrupted(Exception):
    def __init__(self, signum: int):
        self.signum = signum


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm", required=True)
    parser.add_argument("--wait-seconds", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not args.vm.strip() or args.wait_seconds < 0:
        parser.error("a VM name, nonnegative wait, and command are required")

    key = hashlib.sha256(args.vm.encode()).hexdigest()[:16]
    path = Path("/private/tmp") / f"sotf-utm-{key}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "r+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        deadline = time.monotonic() + args.wait_seconds
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SystemExit(f"timed out waiting for UTM guest lock: {args.vm}")
                time.sleep(1)
        print(f"UTM guest lock acquired for {args.vm}", flush=True)
        def interrupt(signum: int, _frame: object) -> None:
            raise Interrupted(signum)

        process: subprocess.Popen[bytes] | None = None
        previous = {
            signum: signal.signal(signum, interrupt)
            for signum in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            process = subprocess.Popen(command, start_new_session=True)
            return process.wait()
        except Interrupted as error:
            print(f"forwarding signal {error.signum} to UTM job", flush=True)
            for signum in (signal.SIGINT, signal.SIGTERM):
                signal.signal(signum, signal.SIG_IGN)
            if process is None:
                return 128 + error.signum
            try:
                os.killpg(process.pid, error.signum)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=240)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                print("UTM job did not finish cleanup within 240 seconds", flush=True)
            return 128 + error.signum
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
