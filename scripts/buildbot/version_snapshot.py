#!/usr/bin/env python3
"""Emit a one-line JSON snapshot describing exactly what a build tested."""

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def command_version(command: list[str], cwd: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = result.stdout.strip()
    return output if result.returncode == 0 and output else None


def git_value(workspace: Path, *args: str) -> Optional[str]:
    return command_version(["git", *args], workspace)


def git_dirty(workspace: Path) -> Optional[bool]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def snapshot(workspace: Path, platform_label: str) -> dict:
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "workspace": workspace.name,
        "revision": git_value(workspace, "rev-parse", "HEAD"),
        "describe": git_value(workspace, "describe", "--always", "--dirty", "--tags"),
        "branch": git_value(workspace, "branch", "--show-current"),
        "dirty": git_dirty(workspace),
        "platform_label": platform_label,
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "rustc": command_version(["rustc", "--version"], workspace),
        "cargo": command_version(["cargo", "--version"], workspace),
        "cargo_nextest": command_version(["cargo", "nextest", "--version"], workspace),
        "just": command_version(["just", "--version"], workspace),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--platform-label", required=True)
    args = parser.parse_args()
    if not args.workspace.is_dir():
        parser.error(f"workspace does not exist: {args.workspace}")
    print(json.dumps(snapshot(args.workspace.resolve(), args.platform_label), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
