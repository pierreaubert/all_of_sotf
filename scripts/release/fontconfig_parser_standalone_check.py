#!/usr/bin/env python3
"""Candidate-only, compile-only qualification of the immutable Fontconfig Parser compatibility fork."""
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

FORK = "d247c91f5a57edd6ba6eb26e884d4904dbfbc87e"
OFFICIAL = "b8a29fbb7fcf217b3cb74c0e77040e1d61a61922"
TREE = "b0d462edd2531a8a8e8c14b5a090303f56ee66f5"
DIFF = "21660a8490160e6e18411a9b962fcb8dd2130711176e54e5e45f21197ea3d3a1"
owned = mac_owned if sys.platform == "darwin" else linux_owned
OUTPUT = ROOT / "target/release-gitea/fontconfig-parser-standalone"

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
        "license_blob": git(repo, "rev-parse", "HEAD:LICENSE"),
    }


def run(repo: Path, name: str, command: list[str], report: dict, env: dict[str, str]) -> dict:
    # The reviewed helper owns the process group and saves RUNNING/final evidence.
    # An absolute path is fixed under the ignored target directory, never user input.
    argv = ["bash", "-c", 'cd "$1" && shift && exec "$@"', "fontconfig", str(repo), *command]
    return owned.run_owned(name, argv, report, env)

def fixture_inventory(repo: Path) -> dict:
    fixture = repo / "test-conf"
    configs = sorted(fixture.rglob("*.conf"))
    paired = sorted(fixture.rglob("*.conf.json"))
    errors = []
    if len(configs) != 25 or len(paired) != 25:
        errors.append("upstream fixture inventory differs from 25 config/JSON pairs")
    for conf in configs:
        expected = conf.with_name(conf.name + ".json")
        if not expected.is_file() or not conf.read_bytes() or not expected.read_bytes():
            errors.append(f"fixture missing or empty: {conf.relative_to(repo)}")
    return {"configs": len(configs), "json": len(paired), "errors": errors}


def test_inventory(log: Path) -> dict:
    import re
    body = log.read_text(errors="replace")
    names = set(re.findall(r"^test ([A-Za-z0-9_:]+) \.\.\. ok$", body, re.M))
    summaries = [tuple(map(int, match)) for match in re.findall(
        r"^test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;", body, re.M)]
    errors = []
    required = ("test_conf", "merge_full", "types::constant::convert_test")
    for name in required:
        if not any(found == name or found.endswith("::" + name) for found in names):
            errors.append(f"original upstream test {name} did not pass")
    if not summaries or sum(row[0] for row in summaries) < 3 or any(row[1:] != (0, 0) for row in summaries):
        errors.append("upstream test summary lacks positive zero-failure zero-ignore evidence")
    if re.search(r"^test result: FAILED", body, re.M):
        errors.append("upstream test log contains failed summary")
    return {"passed_names": sorted(names), "summaries": summaries, "errors": errors}

def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("Fontconfig Parser standalone check runs only in disposable Gitea CI")
    owned.OUTPUT = OUTPUT
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    output = OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    (output / "logs").mkdir(exist_ok=True)
    report: dict = {"qualification": "upstream default/all-features/no-default compile and original all-feature fixtures", "commands": [], "errors": []}
    revisions: dict[str, str] = {}
    before: dict | None = None
    try:
        _, _, revisions = read_manifest(ROOT / "scripts/release/sources.json")
        before = root_snapshot(revisions)
        report["before"] = before
        report["status"] = "RUNNING"
        owned.save(report)
        report["errors"].extend(root_errors(before, before, revisions))
        if report["errors"]:
            raise ValueError("initial nine-source and ten-lock guard failed")
        repo = output / "fontconfig-source"
        state = fork_state(repo)
        report["fork_before"] = state
        if (state["head"], state["parent"], state["tree"], state["source_diff_sha256"]) != (FORK, OFFICIAL, TREE, DIFF):
            raise ValueError("fork revision, ancestry, tree, or source diff differs")
        if state["worktree_entries"] or state["license_blob"] != "758cb027c1be0765738381888f7642c2981881f3":
            raise ValueError("fork cleanliness or licenses differ")
        report["fixture_inventory"] = fixture_inventory(repo)
        owned.save(report)
        report["errors"].extend(report["fixture_inventory"]["errors"])
        if report["errors"]:
            raise ValueError("original upstream fixture inventory failed")
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
            ("upstream-tests", ["cargo", "test", "--locked", "--all-features", "--lib", "--tests", "--", "--show-output"]),
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
        if len(report["commands"]) == len(commands) and report["commands"][-1]["status"] == "PASS":
            report["upstream_test_inventory"] = test_inventory(output / "logs/upstream-tests.log")
            report["errors"].extend(report["upstream_test_inventory"]["errors"])
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
