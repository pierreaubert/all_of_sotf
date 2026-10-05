#!/usr/bin/env python3
"""Check the immutable cbindgen TOML candidate and its original header fixtures."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release.checkout_sources import read_manifest
from scripts.release import nih_native_artifact_check as linux_owned
from scripts.release import nih_macos_artifact_check as mac_owned

owned = mac_owned if sys.platform == "darwin" else linux_owned
OUTPUT = ROOT / "target/release-gitea/cbindgen-standalone"
SOURCE = "https://github.com/pierreaubert/cbindgen.git"
OFFICIAL = "bd78bbe59b10eda6ef1255e4acda95c56c6d0279"
OFFICIAL_TREE = "c7130dd78565e4ac583076ab227aa74ecb137ab7"
FORK = "50c4815d1d704f86432f9cb94dc7f5ce17b7678e"
FORK_TREE = "a45a8526bb3e2bcba064e2d7ebd1ad5161bdebac"
DIFF_SHA256 = "8732dc90b3887851206b018b89e9a3895f6d002119df39e5cea8fd5082ec6d81"
LICENSE_BLOB = "a612ad9813b006ce81d1ee438dd784da99a54007"
LOCK_BLOB = "43efb9cb3ad6cc3ff52bf34e2462b3c4d9eeb4aa"
TEST_LINE = re.compile(r"^test (test_[A-Za-z0-9_]+) \.\.\. ok$", re.MULTILINE)
SUMMARY = re.compile(
    r"^test result: ok\. (\d+) passed; 0 failed; 0 ignored; 0 measured; 0 filtered out;",
    re.MULTILINE,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def source_state(repo: Path) -> dict:
    return {
        "head": git(repo, "rev-parse", "HEAD"),
        "parent": git(repo, "rev-parse", "HEAD^"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "official_tree": git(repo, "rev-parse", f"{OFFICIAL}^{{tree}}"),
        "license_blob": git(repo, "rev-parse", "HEAD:LICENSE"),
        "lock_blob": git(repo, "rev-parse", "HEAD:Cargo.lock"),
        "changed_paths": git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", OFFICIAL, FORK).splitlines(),
        "diff_sha256": sha(subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", OFFICIAL, FORK])),
        "status": subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all", "--ignored"],
            text=True,
        ).splitlines(),
    }


def fixture_names(repo: Path) -> list[str]:
    files = sorted(path for path in (repo / "tests/rust").iterdir()
                   if path.is_dir() or path.suffix == ".rs")
    names = []
    for path in files:
        segment = path.stem if path.is_file() else path.name
        identifier = "".join(char if char.isalnum() else "_" for char in segment).replace("__", "_")
        names.append("test_" + identifier)
    if len(names) != 147 or len(set(names)) != 147:
        raise ValueError(f"upstream header fixture inventory differs: {len(names)} entries")
    return names


def fixture_results(log: str, expected: list[str]) -> dict:
    observed = TEST_LINE.findall(log)
    summaries = SUMMARY.findall(log)
    if len(summaries) != 1 or int(summaries[0]) != len(expected):
        raise ValueError("upstream fixture summary is absent or does not count 147 passes")
    if len(observed) != len(expected) or set(observed) != set(expected):
        raise ValueError("upstream fixture names are missing, duplicated, or unexpected")
    if " ... FAILED" in log or " ... ignored" in log:
        raise ValueError("upstream fixture failed or was ignored")
    return {"passed": len(observed), "names": sorted(observed)}


def run(name: str, argv: list[str], report: dict, env: dict[str, str]) -> dict:
    return owned.run_owned(name, argv, report, env)


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise SystemExit("cbindgen standalone check requires disposable Gitea CI")
    if sys.platform not in ("linux", "darwin"):
        raise SystemExit("unsupported CI platform")
    if sys.platform == "linux" and (not Path("/.dockerenv").exists() or Path("/dev/snd").exists()):
        raise SystemExit("Linux check requires a disposable container without an audio device")
    owned.OUTPUT = OUTPUT
    signal.signal(signal.SIGINT, owned.interrupted)
    signal.signal(signal.SIGTERM, owned.interrupted)
    owned.enable_subreaper()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=False)
    report: dict = {"status": "RUNNING", "commands": [], "errors": [],
                    "scope": "standalone fork; no consumer or release-lock adoption"}
    revisions: dict[str, str] = {}
    before: dict | None = None
    repo = OUTPUT / "source"
    try:
        _, _, revisions = read_manifest(ROOT / "scripts/release/sources.json")
        before = owned.snapshot(revisions)
        report["before"] = before
        owned.save(report)
        report["errors"].extend(owned.source_errors(before, before, revisions))
        if report["errors"]:
            raise ValueError("initial nine-source and ten-lock guard failed")
        if repo.exists():
            raise ValueError("stale source checkout exists")
        original_home = Path.home().expanduser().resolve()
        env = os.environ.copy()
        for variable, default in (("CARGO_HOME", ".cargo"), ("RUSTUP_HOME", ".rustup")):
            env[variable] = str(Path(env.get(variable) or original_home / default).expanduser().resolve())
        private_home = OUTPUT / "private-home"
        private_home.mkdir(exist_ok=True)
        (private_home / ".cargo").mkdir(exist_ok=True)
        env["HOME"] = str(private_home)
        env["XDG_CONFIG_HOME"] = str(private_home / "config")
        env["XDG_CACHE_HOME"] = str(private_home / "cache")
        env["TMPDIR"] = str(OUTPUT / "tmp")
        Path(env["TMPDIR"]).mkdir(exist_ok=True)
        env["CARGO_TARGET_DIR"] = str(OUTPUT / "build")
        report["tool_homes"] = {key: env[key] for key in ("CARGO_HOME", "RUSTUP_HOME")}
        owned.save(report)
        preparation = [
            ("clone", ["git", "clone", "--no-checkout", SOURCE, str(repo)]),
            ("checkout", ["git", "-C", str(repo), "checkout", "--detach", FORK]),
        ]
        for name, argv in preparation:
            if run(name, argv, report, env)["status"] != "PASS":
                raise ValueError(f"{name} failed")
        state = source_state(repo)
        report["fork_before"] = state
        owned.save(report)
        if (state["head"], state["parent"], state["tree"], state["official_tree"],
            state["license_blob"], state["lock_blob"], state["changed_paths"],
            state["diff_sha256"], state["status"]) != (
                FORK, OFFICIAL, FORK_TREE, OFFICIAL_TREE, LICENSE_BLOB, LOCK_BLOB,
                ["Cargo.toml"], DIFF_SHA256, []):
            raise ValueError("fork revision, one-file diff, license, or source cleanliness differs")
        lock = repo / "Cargo.lock"
        if not lock.is_file():
            raise ValueError("tracked upstream Cargo.lock is missing")
        initial_lock_hash = sha(lock.read_bytes())
        report["fork_lock_before_sha256"] = initial_lock_hash
        fixtures = fixture_names(repo)
        report["fixture_inventory"] = {"count": len(fixtures), "names_sha256": sha("\n".join(fixtures).encode())}
        owned.save(report)
        commands = [
            ("resolve", ["cargo", "generate-lockfile"]),
            ("default", ["cargo", "check", "--locked", "--lib", "--bin", "cbindgen"]),
            ("all-features", ["cargo", "check", "--locked", "--all-features", "--all-targets"]),
            ("no-default", ["cargo", "check", "--locked", "--no-default-features", "--lib"]),
            ("header-fixtures", ["cargo", "test", "--locked", "--test", "tests", "--", "--test-threads=1"]),
        ]
        lock_hash: str | None = None
        for name, argv in commands:
            if owned.STOP:
                raise KeyboardInterrupt("stopped before next command")
            command = ["bash", "-c", 'cd "$1" && shift && exec "$@"', "cbindgen", str(repo), *argv]
            result = run(name, command, report, env)
            if result["status"] != "PASS":
                raise ValueError(f"{name} failed")
            lock = repo / "Cargo.lock"
            if not lock.is_file():
                raise ValueError("standalone Cargo.lock missing")
            current = sha(lock.read_bytes())
            if lock_hash is None:
                lock_hash = current
            elif current != lock_hash:
                raise ValueError("standalone Cargo.lock changed after a locked command")
        report["fork_lock_sha256"] = lock_hash
        report["header_fixtures"] = fixture_results(
            (OUTPUT / "logs/header-fixtures.log").read_text(errors="replace"), fixtures)
        after_fork = source_state(repo)
        report["fork_after"] = after_fork
        after_status = after_fork["status"]
        before_state = state.copy()
        before_state.pop("status")
        after_state = after_fork.copy()
        after_state.pop("status")
        expected_status = [] if lock_hash == initial_lock_hash else [" M Cargo.lock"]
        if after_state != before_state or after_status != expected_status:
            raise ValueError(f"fork source changed outside generated Cargo.lock: {after_status}")
        if len(report["commands"]) != 7 or any(item["status"] != "PASS" for item in report["commands"]):
            raise ValueError("standalone command inventory incomplete")
    except KeyboardInterrupt:
        report["errors"].append("interrupted before completion")
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        try:
            report["after"] = owned.snapshot(revisions)
            if before is None:
                report["errors"].append("initial root snapshot unavailable")
            else:
                report["errors"].extend(owned.source_errors(before, report["after"], revisions))
        except Exception as error:
            report["errors"].append(f"final root guard: {error}")
        report["status"] = "PASS" if not owned.STOP and not report["errors"] else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
