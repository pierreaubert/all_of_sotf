#!/usr/bin/env python3
"""Candidate-only, test qualification of the immutable rusty-fork compatibility fork."""
from __future__ import annotations

import hashlib
import json
import os
import re
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

FORK = "ee62bcd64fa6afe7fae0e52a448d716dc294e98d"
OFFICIAL = "22b6d890319f6041f7add41e014feb72c56488ed"
MANIFEST_CHILD = "8e3856e2392bbb551870c08503c0343fc3cdced6"
DIFF_SHA256 = "9ec34f627e1bc76e5e2bd75400e9744d18bbf967aaa92a2aa279a5093c8d0d47"
TREE = "cbaf730fe5b193633db5e0b69619773b045b2a90"
OFFICIAL_MANIFEST_BLOB = "a57b172e566cba1555f84ec557b8460782b08836"
FORK_MANIFEST_BLOB = "43b145b69d4ffa9cab59b4512aeb395b5ba382fb"
owned = mac_owned if sys.platform == "darwin" else linux_owned
OUTPUT = ROOT / "target/release-gitea/rusty-fork-candidate"

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
        "grandparent": git(repo, "rev-parse", "HEAD^^"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "worktree_entries": git(repo, "status", "--porcelain", "--untracked-files=all", "--ignored").splitlines(),
        "source_diff_sha256": sha(subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", OFFICIAL, FORK])),
        "changed_paths": git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", OFFICIAL, FORK).splitlines(),
        "official_manifest_blob": git(repo, "rev-parse", f"{OFFICIAL}:Cargo.toml"),
        "fork_manifest_blob": git(repo, "rev-parse", f"{FORK}:Cargo.toml"),
        "license_apache": git(repo, "rev-parse", "HEAD:LICENSE-APACHE"),
        "license_mit": git(repo, "rev-parse", "HEAD:LICENSE-MIT"),
    }


def verify_initial_fork(state: dict) -> None:
    expected = {
        "head": FORK,
        "parent": MANIFEST_CHILD,
        "grandparent": OFFICIAL,
        "tree": TREE,
        "changed_paths": ["Cargo.toml", "src/error.rs"],
        "official_manifest_blob": OFFICIAL_MANIFEST_BLOB,
        "fork_manifest_blob": FORK_MANIFEST_BLOB,
        "source_diff_sha256": DIFF_SHA256,
        "license_apache": "16fe87b06e802f094b3fbb0894b137bca2b16ef1",
        "license_mit": "63ceeec5c6d0770d928e2e9aa34ec5783dedb6de",
        "worktree_entries": [],
    }
    mismatched = [field for field, value in expected.items() if state.get(field) != value]
    if mismatched:
        raise ValueError(f"fork provenance, licenses, or cleanliness differ: {mismatched}")


def run(repo: Path, name: str, command: list[str], report: dict, env: dict[str, str]) -> dict:
    # The reviewed helper owns the process group and saves RUNNING/final evidence.
    # An absolute path is fixed under the ignored target directory, never user input.
    argv = ["bash", "-c", 'cd "$1" && shift && exec "$@"', "rusty-fork", str(repo), *command]
    return owned.run_owned(name, argv, report, env)

EXPECTED_BASE = {
    "cmdline::test::test_strip", "cmdline::test::define_args_via_env",
    "fork::test::fork_basically_works", "fork::test::child_output_captured_and_repeated",
    "fork::test::child_killed_if_parent_exits_first",
    "fork::test::child_killed_if_parent_panics_first",
    "fork::test::child_aborted_if_panics",
    "fork_test::test::trivial", "fork_test::test::panicking_child",
    "fork_test::test::aborting_child", "sugar::test::ids_are_actually_distinct",
    "error::tests::spawn_error_preserves_source_and_legacy_cause",
}
TIMEOUT_TESTS = {"fork_test::test::timeout_passes", "fork_test::test::timeout_fails"}
SHOULD_PANIC = {"fork_test::test::panicking_child", "fork_test::test::aborting_child",
                "fork_test::test::timeout_fails"}
TEST_LINE = re.compile(r"^test ([A-Za-z0-9_:]+)( - should panic)? \.\.\. (ok|FAILED|ignored)$", re.MULTILINE)
SUMMARY = re.compile(r"^test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;", re.MULTILINE)


def test_inventory(name: str) -> dict:
    log = (OUTPUT / "logs" / f"{name}.log").read_text(errors="replace")
    rows = TEST_LINE.findall(log)
    actual = {test for test, marker, result in rows if result == "ok"}
    wanted = ({"error::tests::spawn_error_preserves_source_and_legacy_cause"}
              if name == "error-source" else
              EXPECTED_BASE | (set() if name == "no-default" else TIMEOUT_TESTS))
    summaries = [(int(a), int(b), int(c)) for a, b, c in SUMMARY.findall(log)]
    if len(rows) != len(actual) or actual != wanted or any(
        bool(marker) != (test in SHOULD_PANIC) for test, marker, _ in rows
    ):
        raise ValueError(f"{name}: upstream named-test inventory differs: {rows}")
    if not summaries or summaries[0] != (len(wanted), 0, 0):
        raise ValueError(f"{name}: selected test summary differs: {summaries}")
    if any(fail or ignored for _, fail, ignored in summaries):
        raise ValueError(f"{name}: failed or ignored tests found: {summaries}")
    if re.search(r"^test result: FAILED", log, re.MULTILINE):
        raise ValueError(f"{name}: failed test result found")
    return {"names": sorted(actual), "summary": summaries[0]}


def main() -> int:
    if sys.flags.optimize != 0:
        raise SystemExit("Python assertions must remain active")
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("rusty-fork standalone check runs only in disposable Gitea CI")
    owned.OUTPUT = OUTPUT
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    output = OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    (output / "logs").mkdir(exist_ok=True)
    report: dict = {"qualification": "standalone upstream tests; no consumer qualification claimed", "commands": [], "errors": []}
    revisions: dict[str, str] = {}
    before: dict | None = None
    try:
        _, _, revisions = read_manifest(ROOT / "scripts/release/sources.json")
        before = root_snapshot(revisions)
        report["before"] = before
        report["errors"].extend(root_errors(before, before, revisions))
        if report["errors"]:
            raise ValueError("initial nine-source and ten-lock guard failed")
        repo = output / "rusty-fork-source"
        state = fork_state(repo)
        report["fork_before"] = state
        verify_initial_fork(state)
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
            ("default", ["cargo", "test", "--locked", "--all-targets"]),
            ("all-features", ["cargo", "test", "--locked", "--all-features", "--all-targets"]),
            ("no-default", ["cargo", "test", "--locked", "--no-default-features", "--all-targets"]),
            ("error-source", ["cargo", "test", "--locked", "--lib", "error::tests::spawn_error_preserves_source_and_legacy_cause"]),
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
        if len(report["commands"]) == len(commands) and all(x["status"] == "PASS" for x in report["commands"]):
            report["test_inventories"] = {name: test_inventory(name) for name in ("default", "all-features", "no-default", "error-source")}
        report["fork_after"] = fork_state(repo)
        after_fork = report["fork_after"].copy()
        ignored = after_fork.pop("worktree_entries")
        before_fork = state.copy()
        before_fork.pop("worktree_entries")
        if after_fork != before_fork or ignored != ["!! Cargo.lock"]:
            raise ValueError(f"fork source or worktree changed outside generated Cargo.lock: {ignored}")
        if len(report["commands"]) != len(commands) or any(x["status"] != "PASS" for x in report["commands"]):
            report["errors"].append("upstream test inventory incomplete or failed")
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
