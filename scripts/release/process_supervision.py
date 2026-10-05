#!/usr/bin/env python3
"""Inspect and stop only process groups owned by release QA commands."""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time

def members(pgid: int) -> list[dict[str, str]]:
    listing = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat="], text=True,
        capture_output=True, check=True, timeout=5,
    )
    found = []
    for line in listing.stdout.splitlines():
        fields = line.split()
        if len(fields) != 4 or not all(field.isdecimal() for field in fields[:3]):
            raise ValueError(f"unparseable process inventory: {line!r}")
        if int(fields[2]) == pgid:
            found.append(dict(zip(("pid", "ppid", "pgid", "state"), fields, strict=True)))
    return found


def enable_subreaper() -> None:
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")


def clean_group(child: subprocess.Popen[bytes]) -> dict:
    errors: list[str] = []
    remaining: list[dict[str, str]] = []

    def reap_owned_descendants() -> None:
        # Popen retains the direct child's exit status. Reap only adopted
        # descendants after it has been polled; this runner owns no other jobs.
        if not sys.platform.startswith("linux") or child.poll() is None:
            return
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid == 0:
                return

    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            child.poll()
            reap_owned_descendants()
            remaining = members(child.pid)
            if not remaining:
                break
        except Exception as error:
            errors.append(f"owned group inspection/reap: {error}")
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"owned group signal: {error}")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                child.poll()
                reap_owned_descendants()
                remaining = members(child.pid)
                if not remaining:
                    break
            except Exception as error:
                errors.append(f"owned group inspection/reap: {error}")
                break
            time.sleep(0.1)
    try:
        child.wait(timeout=5)
        reap_owned_descendants()
        remaining = members(child.pid)
    except Exception as error:
        errors.append(f"owned group final reap: {error}")
    return {"ok": not errors and not remaining, "remaining": remaining, "errors": errors}
