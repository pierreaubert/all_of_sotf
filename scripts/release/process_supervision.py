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
    # A loaded native linker can delay ps. A timeout supplies no inventory,
    # so retry inspection before deciding that cleanup cannot be verified.
    # Every attempt remains bounded; malformed output and hard errors propagate.
    for attempt in range(3):
        try:
            listing = subprocess.run(
                ["ps", "-axo", "pid=,ppid=,pgid=,stat="], text=True,
                capture_output=True, check=True, timeout=5,
            )
            break
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise
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
        # descendants still present in this owned process group. A broad
        # waitpid(-1) could steal the exit status of an unrelated child owned
        # by another helper in the same runner process.
        if not sys.platform.startswith("linux") or child.poll() is None:
            return
        for member in members(child.pid):
            pid = int(member["pid"])
            if pid == child.pid:
                continue
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                continue

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
