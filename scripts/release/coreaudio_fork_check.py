#!/usr/bin/env python3
"""Qualify the pinned CoreAudio fork without opening an audio device."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


FORK_URL = "https://github.com/pierreaubert/coreaudio-rs.git"
FORK_REV = "29b0407363c479be0b7de681ba6ba050725a5174"
COMPAT_PARENT = "2d57f0f827d67162ccdce8f34b453fbd70d7750b"
OFFICIAL_PARENT = "f07c02c7419328650112d4b276cffd785b0be4ee"
FORK_TREE = "dce88f9f37c662e25df03952ded66b4b2622726e"
LICENSE_BLOBS = {"LICENSE-APACHE": "16fe87b06e802f094b3fbb0894b137bca2b16ef1",
                 "LICENSE-MIT": "9203baa055d41d89e1ab8f4d6aa9180a49e078a7"}
TESTS = {
    "input_buffer_reclaims_initial_overallocated_storage",
    "input_buffer_reclaims_actual_capacity_after_shrink_and_growth",
    "independent_input_buffer_lifetimes_do_not_reuse_capacity",
    "input_buffer_grows_from_watchos_first_callback",
}
INTERRUPTED = False


def interrupt(signum: int, _frame: object) -> None:
    global INTERRUPTED
    INTERRUPTED = True


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def members(pgid: int) -> list[dict[str, str]]:
    listing = subprocess.run(["ps", "-axo", "pid=,ppid=,pgid=,stat="], text=True,
                             capture_output=True, check=True, timeout=5)
    found = []
    for line in listing.stdout.splitlines():
        fields = line.split()
        if len(fields) != 4 or not all(field.isdigit() for field in fields[:3]):
            raise ValueError(f"unparseable process inventory row: {line!r}")
        if int(fields[2]) == pgid:
            found.append(dict(zip(("pid", "ppid", "pgid", "state"), fields, strict=True)))
    return found


def cleanup(child: subprocess.Popen[bytes]) -> dict:
    errors: list[str] = []
    remaining: list[dict[str, str]] = []

    def reap() -> None:
        if child.poll() is None:
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
            reap()
            remaining = members(child.pid)
            if not remaining:
                break
        except Exception as error:
            errors.append(f"inspect: {error}")
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass
        except OSError as error:
            errors.append(f"signal: {error}")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                reap()
                remaining = members(child.pid)
                if not remaining:
                    break
            except Exception as error:
                errors.append(f"inspect: {error}")
                break
            time.sleep(0.1)
    try:
        child.wait(timeout=5)
        reap()
        remaining = members(child.pid)
    except Exception as error:
        errors.append(f"final reap: {error}")
    return {"ok": not errors and not remaining, "errors": errors, "remaining": remaining}


def command(name: str, argv: list[str], cwd: Path, evidence: Path) -> dict:
    log_path = evidence / f"{name}.log"
    entry: dict = {"name": name, "argv": argv, "log": str(log_path), "status": "RUNNING"}
    if INTERRUPTED:
        entry.update({"exit_code": 130, "status": "FAIL", "not_started": True,
                      "cleanup": {"ok": True, "errors": [], "remaining": []}, "text": ""})
        return entry
    with log_path.open("wb") as log:
        child: subprocess.Popen[bytes] | None = None
        code = 130
        try:
            child = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            entry["owned_pgid"] = child.pid
            next_heartbeat = time.monotonic() + 30
            while not INTERRUPTED:
                try:
                    code = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= next_heartbeat:
                        print(f"[{name}] still running", flush=True)
                        next_heartbeat = time.monotonic() + 30
        finally:
            if child is not None:
                entry["cleanup"] = cleanup(child)
    text = log_path.read_text(errors="replace")
    entry.update({"exit_code": code, "text": text,
                  "status": "PASS" if code == 0 and entry["cleanup"]["ok"] else "FAIL"})
    return entry


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def main() -> int:
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    evidence = Path(sys.argv[1]).resolve()
    report: dict = {"fork_url": FORK_URL, "fork_revision": FORK_REV,
                    "commands": [], "errors": []}
    if (sys.platform != "darwin" or os.environ.get("CI") != "true"
            or os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1"):
        print("CoreAudio qualification requires disposable macOS CI", file=sys.stderr)
        return 2
    evidence.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="coreaudio-fork-") as temporary:
            fork = Path(temporary) / "coreaudio-rs"
            result = command("clone", ["git", "clone", "--no-checkout", FORK_URL, str(fork)],
                             Path(temporary), evidence)
            report["commands"].append({key: val for key, val in result.items() if key != "text"})
            if result["status"] != "PASS":
                raise RuntimeError("clone failed")
            result = command("checkout", ["git", "checkout", "--detach", FORK_REV], fork,
                             evidence)
            report["commands"].append({key: val for key, val in result.items() if key != "text"})
            if result["status"] != "PASS" or git(fork, "rev-parse", "HEAD") != FORK_REV:
                raise RuntimeError("fork revision mismatch")
            if git(fork, "rev-parse", "HEAD^") != COMPAT_PARENT or git(fork, "rev-parse", "HEAD^^") != OFFICIAL_PARENT:
                raise RuntimeError("fork does not directly descend from official upstream")
            if git(fork, "rev-parse", "HEAD^{tree}") != FORK_TREE:
                raise RuntimeError("fork source tree mismatch")
            changed = git(fork, "diff", "--name-only", "HEAD^", "HEAD").splitlines()
            if changed != ["src/audio_unit/render_callback.rs"] or git(fork, "diff", "--name-only", "HEAD^^", "HEAD^").splitlines() != ["src/audio_unit/mod.rs", "src/audio_unit/render_callback.rs"]:
                raise RuntimeError("fork changed unexpected source files")
            for name, blob in LICENSE_BLOBS.items():
                if git(fork, "rev-parse", f"HEAD:{name}") != blob:
                    raise RuntimeError(f"fork license changed: {name}")
            report["provenance"] = {"official_parent": OFFICIAL_PARENT, "tree": FORK_TREE,
                                    "changed_files": changed, "license_blobs": LICENSE_BLOBS}
            if git(fork, "status", "--porcelain"):
                raise RuntimeError("fork checkout is dirty before resolution")
            result = command("resolve", ["cargo", "generate-lockfile"], fork, evidence)
            report["commands"].append({key: val for key, val in result.items() if key != "text"})
            lock = fork / "Cargo.lock"
            if result["status"] != "PASS" or not lock.is_file():
                raise RuntimeError("lock resolution failed")
            report["lock_sha256"] = sha256(lock)
            shutil.copy2(lock, evidence / "coreaudio-fork.Cargo.lock")
            for test_name in sorted(TESTS):
                result = command(test_name,
                                 ["cargo", "test", "--locked", "-p", "coreaudio-rs", "--lib",
                                  test_name, "--", "--test-threads=1", "--show-output"],
                                 fork, evidence)
                report["commands"].append({key: val for key, val in result.items() if key != "text"})
                # The filter is a substring; require its sole full test name.
                if result["status"] != "PASS" or not re.search(
                    rf"(?m)^test\s+\S*::{re.escape(test_name)}\s+\.\.\.\s+ok$",
                    result["text"]):
                    raise RuntimeError(f"{test_name}: missing positive result")
                if not re.search(r"test result: ok\.\s+1 passed; 0 failed; 0 ignored;",
                                 result["text"]):
                    raise RuntimeError(f"{test_name}: unexpected test inventory")
            result = command("all-targets", ["cargo", "check", "--locked", "-p",
                                             "coreaudio-rs", "--all-targets"], fork,
                             evidence)
            report["commands"].append({key: val for key, val in result.items() if key != "text"})
            if result["status"] != "PASS":
                raise RuntimeError("all-target compilation failed")
            report["source_status_after"] = git(fork, "status", "--porcelain", "--untracked-files=all")
            # Upstream ignores /Cargo.lock; the separately hashed copy still
            # proves it stayed fixed through every command.
            if report["source_status_after"]:
                raise RuntimeError("fork source changed during qualification")
            if git(fork, "rev-parse", "HEAD") != FORK_REV or sha256(lock) != report["lock_sha256"]:
                raise RuntimeError("fork revision or resolved lock changed")
    except Exception as error:
        report["errors"].append(str(error))
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
