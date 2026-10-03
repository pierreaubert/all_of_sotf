#!/usr/bin/env python3
"""Resolve nine pinned workspaces on Gitea and preserve lockfile evidence.

This is a preparation phase, not a release QA pass. Its Cargo.lock outputs
must be reviewed and committed before the --locked QA workflow is dispatched.
"""

from __future__ import annotations

import argparse
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
sys.path.insert(0, str(ROOT / "scripts"))
from workspaces import workspace_names

from checkout_sources import read_manifest

ORDER = (
    "math-audio", "gpui-toolkit", "sofa-reader", "symphonia-add-ons",
    "autoeq", "sotf-daw", "sotf-capture", "sotf", "sotf-systemwide",
)


def git(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args], check=True,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def changed_paths(workspace: Path) -> list[str]:
    modified = git(workspace, "diff", "--name-only").splitlines()
    staged = git(workspace, "diff", "--cached", "--name-only").splitlines()
    untracked = git(workspace, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(modified + staged + untracked))


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def write_report(path: Path, report: dict) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


class ResolutionInterrupted(KeyboardInterrupt):
    def __init__(self, result: dict):
        super().__init__("resolution interrupted")
        self.result = result


def stop_process_group(process: subprocess.Popen) -> None:
    """Stop Cargo and its descendants before preserving partial evidence."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def interrupted(_signum, _frame):
    raise KeyboardInterrupt("SIGTERM")


def resolve_one(name: str, revision: str, root: Path, output: Path) -> dict:
    workspace = root / name
    result: dict = {"workspace": name, "revision": revision, "status": "FAIL"}
    if not (workspace / "Cargo.toml").is_file():
        result["error"] = "workspace Cargo.toml missing"
        return result
    actual = git(workspace, "rev-parse", "HEAD")
    result["actual_revision"] = actual
    if actual != revision:
        result["error"] = "checkout does not match pinned revision"
        return result
    if changed_paths(workspace):
        result["error"] = "checkout was dirty before resolution"
        return result

    lock = workspace / "Cargo.lock"
    result["lock_before_sha256"] = digest(lock)
    lock_dir = output / "locks" / name
    lock_dir.mkdir(parents=True, exist_ok=True)
    if lock.is_file():
        shutil.copy2(lock, lock_dir / "Cargo.lock.before")

    metadata = output / "metadata" / f"{name}.json"
    log = output / "logs" / f"{name}.log"
    start = time.monotonic()
    print(f"[{name}] resolving {revision}", flush=True)
    was_interrupted = False
    with metadata.open("w", encoding="utf-8") as stdout, log.open("w", encoding="utf-8") as stderr:
        try:
            process = subprocess.Popen(
                ["cargo", "metadata", "--format-version", "1"],
                cwd=workspace, stdout=stdout, stderr=stderr,
                start_new_session=True,
            )
            try:
                result["exit_code"] = process.wait()
            except KeyboardInterrupt:
                stop_process_group(process)
                result["exit_code"] = process.returncode
                was_interrupted = True
        except OSError as error:
            stderr.write(str(error) + "\n")
            result["exit_code"] = 127
    result["duration_seconds"] = round(time.monotonic() - start, 3)
    result["metadata_file"] = str(metadata.relative_to(output))
    result["log_file"] = str(log.relative_to(output))
    result["lock_after_sha256"] = digest(lock)
    result["lock_changed"] = result["lock_before_sha256"] != result["lock_after_sha256"]
    if lock.is_file():
        shutil.copy2(lock, lock_dir / "Cargo.lock")
    result["changed_paths"] = changed_paths(workspace)

    if was_interrupted:
        result["status"] = "INTERRUPTED"
        result["error"] = "resolution interrupted; inspect log and partial lockfile"
        raise ResolutionInterrupted(result)

    if result["exit_code"]:
        result["error"] = "cargo metadata failed; inspect log and partial lockfile"
    elif git(workspace, "rev-parse", "HEAD") != revision:
        result["error"] = "source revision changed during resolution"
    elif set(result["changed_paths"]) - {"Cargo.lock"}:
        result["error"] = "resolution modified source files beyond Cargo.lock"
    else:
        try:
            json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            result["error"] = f"invalid cargo metadata output: {error}"
        else:
            result["status"] = "RESOLVED"
    return result


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "scripts" / "release" / "sources.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "release-resolution")
    args = parser.parse_args(argv)
    if set(ORDER) != set(workspace_names()):
        parser.error("resolution order and workspace inventory differ")
    _, _, revisions = read_manifest(args.manifest)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "metadata").mkdir()
    (output / "logs").mkdir()
    shutil.copy2(args.manifest, output / "sources.json")
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING", "release_qa": False,
        "required_workspaces": list(ORDER), "workspaces": [],
    }
    report_path = output / "report.json"
    write_report(report_path, report)
    try:
        for name in ORDER:
            report["active_workspace"] = name
            write_report(report_path, report)
            try:
                result = resolve_one(name, revisions[name], args.root.resolve(), output)
            except (OSError, subprocess.CalledProcessError) as error:
                result = {"workspace": name, "revision": revisions[name], "status": "FAIL", "error": str(error)}
            report["workspaces"].append(result)
            report.pop("active_workspace", None)
            write_report(report_path, report)
    except ResolutionInterrupted as error:
        report["workspaces"].append(error.result)
        report.pop("active_workspace", None)
        report["interrupted"] = True
        report["error"] = str(error)
    except KeyboardInterrupt as error:
        report["interrupted"] = True
        report["error"] = str(error) or "resolution interrupted"
    finally:
        report["status"] = "FAIL" if report.get("interrupted") or len(report["workspaces"]) != len(ORDER) or any(
            item["status"] != "RESOLVED" for item in report["workspaces"]
        ) else "RESOLVED"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_report(report_path, report)
    print(f"{report['status']}: {report_path}", flush=True)
    return 0 if report["status"] == "RESOLVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
