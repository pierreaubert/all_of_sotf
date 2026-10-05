#!/usr/bin/env python3
"""Candidate-only, compile-only qualification of the immutable Cosmic compatibility fork."""
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
from scripts.release.checkout_sources import read_manifest
from scripts.release import nih_native_artifact_check as linux_owned
from scripts.release import nih_macos_artifact_check as mac_owned

FORK = "5d2ccb99a7a470919b62eae46e37bb0d6aa61a48"
OFFICIAL = "59089955e1c8698c6b83b2e6ab6ebceff825ff96"
TREE = "27da67b5939ffaef2c11a86055f7cc45063de3af"
DIFF = "fdce51c87312de854ef2e521c4e2d67ab407d1e409a22b7b43b98329ac80a045"
owned = mac_owned if sys.platform == "darwin" else linux_owned
OUTPUT = ROOT / "target/release-gitea/cosmic-standalone"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def root_snapshot(revisions: dict[str, str]) -> dict:
    return owned.snapshot(revisions)


def root_errors(before: dict, after: dict, revisions: dict[str, str]) -> list[str]:
    return owned.source_errors(before, after, revisions)

def fork_state(repo: Path) -> dict:
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "parent": git(repo, "rev-parse", "HEAD^"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "worktree_entries": git(repo, "status", "--porcelain", "--untracked-files=all", "--ignored").splitlines(),
        "source_diff_sha256": sha(subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", OFFICIAL, FORK])),
        "license_apache": git(repo, "rev-parse", "HEAD:LICENSE-APACHE"),
        "license_mit": git(repo, "rev-parse", "HEAD:LICENSE-MIT"),
    }


def run(repo: Path, name: str, command: list[str], report: dict, env: dict[str, str]) -> dict:
    # The reviewed helper owns the process group and saves RUNNING/final evidence.
    # An absolute path is fixed under the ignored target directory, never user input.
    argv = ["bash", "-c", 'cd "$1" && shift && exec "$@"', "cosmic", str(repo), *command]
    return owned.run_owned(name, argv, report, env)

def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("Cosmic standalone check runs only in disposable Gitea CI")
    owned.OUTPUT = OUTPUT
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    output = OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    (output / "logs").mkdir(exist_ok=True)
    report: dict = {"qualification": "compile-only; no font LFS or render tests claimed", "commands": [], "errors": []}
    revisions: dict[str, str] = {}
    before: dict | None = None
    try:
        _, _, revisions = read_manifest(ROOT / "scripts/release/sources.json")
        before = root_snapshot(revisions)
        report["before"] = before
        report["errors"].extend(root_errors(before, before, revisions))
        if report["errors"]:
            raise ValueError("initial nine-source and ten-lock guard failed")
        repo = output / "cosmic-source"
        state = fork_state(repo)
        report["fork_before"] = state
        if (state["head"], state["parent"], state["tree"], state["source_diff_sha256"]) != (FORK, OFFICIAL, TREE, DIFF):
            raise ValueError("fork revision, ancestry, tree, or source diff differs")
        if state["worktree_entries"] or state["license_apache"] != "6f756351aae24b479e6a9418c1f08a8b7a991076" or state["license_mit"] != "db6aab15cf8c6a1f348650f0c6fa4df60d026a89":
            raise ValueError("fork cleanliness or licenses differ")
        if (repo / "Cargo.lock").exists():
            raise ValueError("fork checkout unexpectedly contains Cargo.lock")
        owned.enable_subreaper()
        private_home = output / "private-home"
        private_home.mkdir(exist_ok=True)
        env = os.environ.copy()
        for variable in ("CARGO_HOME", "RUSTUP_HOME"):
            value = env.get(variable)
            if not value:
                value = str(Path.home() / (".cargo" if variable == "CARGO_HOME" else ".rustup"))
            env[variable] = str(Path(value).expanduser().resolve())
        env["HOME"] = str(private_home)
        env["XDG_CONFIG_HOME"] = str(private_home / "config")
        env["XDG_CACHE_HOME"] = str(private_home / "cache")
        env["CARGO_TARGET_DIR"] = str(output / "build")
        (private_home / ".cargo").mkdir(exist_ok=True)
        commands = [
            ("resolve", ["cargo", "generate-lockfile"]),
            ("default", ["cargo", "check", "--locked", "--lib"]),
            ("all-features", ["cargo", "check", "--locked", "--all-features", "--all-targets"]),
            ("no-default", ["cargo", "check", "--locked", "--no-default-features", "--lib"]),
            ("no-std", ["cargo", "check", "--locked", "--no-default-features", "--features", "no_std", "--lib"]),
        ]
        lock_hash = None
        for name, argv in commands:
            if owned.STOP:
                break
            result = run(repo, name, argv, report, env)
            if result["status"] != "PASS":
                break
            lock = repo / "Cargo.lock"
            if not lock.is_file():
                raise ValueError("generated standalone Cargo.lock missing")
            current = sha(lock.read_bytes())
            if lock_hash is None:
                lock_hash = current
            elif current != lock_hash:
                raise ValueError("standalone Cargo.lock changed after locked command")
        report["fork_lock_sha256"] = lock_hash
        report["fork_after"] = fork_state(repo)
        after_fork = report["fork_after"].copy()
        ignored = after_fork.pop("worktree_entries")
        before_fork = state.copy()
        before_fork.pop("worktree_entries")
        if after_fork != before_fork or ignored != ["!! Cargo.lock"]:
            raise ValueError(f"fork source or worktree changed outside generated Cargo.lock: {ignored}")
        if len(report["commands"]) != len(commands) or any(x["status"] != "PASS" for x in report["commands"]):
            report["errors"].append("compile inventory incomplete or failed")
    except KeyboardInterrupt:
        report["errors"].append("interrupted before completion")
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        try:
            report["after"] = root_snapshot(revisions)
            if before is None:
                report["errors"].append("initial root snapshot unavailable")
            else:
                report["errors"].extend(root_errors(before, report["after"], revisions))
        except Exception as error:
            report["errors"].append(f"final root guard: {error}")
        report["status"] = "PASS" if not owned.STOP and not report["errors"] else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
