#!/usr/bin/env python3
"""Gitea-only, offline qualification of the seven pinned tract packages."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import tomllib

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.qa import host_platform, source_issues, source_state

FORK = "https://github.com/pierreaubert/tract.git"
OFFICIAL_BASE = "d40ce12ae71741008a2a3b4fffcd3d6a6175301d"
COMPATIBILITY_PARENT = "3ab6874b52c4b0ff83a7114f9c30c5fe62f257cd"
RAND_COMPATIBILITY_PARENT = "aee8cf204bef9be6bba0025ef7c20a298613cef7"
PACKAGES = {f"tract-{name}" for name in ("core", "data", "hir", "linalg", "nnef", "onnx", "onnx-opl")}
TESTS = {
    "seeded_multinomial_replays_and_only_selects_possible_classes",
    "seeded_uniform_replays_and_stays_within_bounds",
    "seeded_normal_replays_with_requested_mean_and_variance",
    "seeded_random_operator_advances_and_replays_after_state_reset",
}
STOP = False


def interrupted(_signal: int, _frame: object) -> None:
    global STOP
    STOP = True


def save(path: Path, value: object) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, indent=2) + "\n")
    pending.replace(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fork_source_status(fork: Path) -> list[str]:
    lines = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=fork, text=True,
    ).splitlines()
    return [line for line in lines if line != " M Cargo.lock"]


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


def enable_subreaper() -> None:
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")


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
            errors.append(f"inspect/reap: {error}")
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
                errors.append(f"inspect/reap: {error}")
                break
            time.sleep(0.1)
    try:
        child.wait(timeout=5)
        reap()
        remaining = members(child.pid)
    except Exception as error:
        errors.append(f"final reap: {error}")
    return {"ok": not errors and not remaining, "errors": errors, "remaining": remaining}


def run(name: str, argv: list[str], cwd: Path, out: Path, report: dict) -> dict:
    entry = {"name": name, "argv": argv, "cwd": str(cwd), "log": str(out / f"{name}.log"),
             "status": "RUNNING"}
    report["active_command"] = entry
    save(out / "report.json", report)
    with (out / f"{name}.log").open("wb") as log:
        child: subprocess.Popen[bytes] | None = None
        code = 130
        try:
            child = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            entry["owned_pgid"] = child.pid
            save(out / "report.json", report)
            while not STOP:
                try:
                    code = child.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    print(f"[{name}] still running", flush=True)
        finally:
            if child is not None:
                entry["cleanup"] = cleanup(child)
    text = Path(entry["log"]).read_text(errors="replace")
    entry.update({"exit_code": code,
                  "passed_tests": sum(map(int, re.findall(r"test result: ok\.\s+(\d+) passed;", text))),
                  "ignored_tests": sum(map(int, re.findall(r"test result: ok\.[^\n]*?;\s+(\d+) ignored;", text))),
                  "named_tests": [n.rsplit("::", 1)[-1] for n in re.findall(
                      r"^test\s+([^\n]+?)\s+\.\.\.\s+ok\s*$", text, re.MULTILINE)],
                  "status": "PASS" if code == 0 and entry["cleanup"]["ok"] else "FAIL"})
    report["commands"].append(entry)
    report.pop("active_command", None)
    save(out / "report.json", report)
    if entry["status"] != "PASS":
        print(f"[{name}] failed\n" + "\n".join(text.splitlines()[-80:]), flush=True)
    return entry


def metadata_packages(path: Path, rev: str) -> dict[str, list[str]]:
    metadata = None
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("{") and '"packages"' in line and '"resolve"' in line:
            metadata = json.loads(line)
    if metadata is None:
        raise ValueError("Cargo metadata JSON absent")
    packages = {p["id"]: p for p in metadata["packages"]}
    expected = f"git+{FORK}?rev={rev}#{rev}"
    found: dict[str, list[str]] = {}
    for node in metadata["resolve"]["nodes"]:
        package = packages[node["id"]]
        if package["name"] not in PACKAGES:
            continue
        if package.get("source") != expected or package["name"] in found:
            raise ValueError(f"unexpected source or duplicate identity: {package['name']} {package.get('source')}")
        found[package["name"]] = sorted(node["features"])
    if set(found) != PACKAGES:
        raise ValueError(f"seven-package resolved set incomplete: {sorted(PACKAGES - set(found))}")
    return found


def main() -> int:
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    enable_subreaper()
    if not os.getenv("CI") or len(sys.argv) != 3 or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]):
        print("Gitea CI usage: tract_candidate_check.py FORK_REV EVIDENCE_DIR", file=sys.stderr)
        return 2
    rev = sys.argv[1]
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    try:
        manifest = ROOT / "scripts/release/sources.json"
        original_manifest = manifest.read_bytes()
        (out / "sources.json").write_bytes(original_manifest)
        _, _, pins = read_manifest(manifest)
        names = list(workspace_map())
        before = source_state(ROOT, names, host_platform())
        save(out / "sources-before.json", before)
        root_rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        root_status_before = root_layout_status(ROOT, pins)
        errors = source_issues(before, before, True)
        if root_status_before["missing"] or root_status_before["unexpected"]:
            errors.append(f"root checkout differs from pinned siblings: {root_status_before}")
        for name, pin in pins.items():
            if before.get(name, {}).get("revision") != pin:
                errors.append(f"{name}: revision differs from sources.json")
        for workspace in ("sotf", "sotf-daw"):
            patches = tomllib.loads((ROOT / workspace / "Cargo.toml").read_text())["patch"]["crates-io"]
            for package in PACKAGES:
                declaration = patches.get(package, {})
                if declaration.get("git") != FORK or declaration.get("rev") != rev:
                    errors.append(f"{workspace}: {package} lacks the same pinned tract source")
        report: dict = {"status": "RUNNING", "root_revision": root_rev, "fork_revision": rev,
                        "official_base": OFFICIAL_BASE, "commands": [], "errors": errors}
        save(out / "report.json", report)
    except BaseException as error:
        save(out / "report.json", {"status": "FAIL", "errors": [f"setup raised {type(error).__name__}: {error}"]})
        return 1
    try:
        if not errors:
            with tempfile.TemporaryDirectory(prefix="tract-candidate-") as temp:
                fork = Path(temp) / "tract"
                for name, argv, cwd in (("fork-clone", ["git", "clone", "--no-checkout", FORK, str(fork)], ROOT),
                                         ("fork-checkout", ["git", "checkout", "--detach", rev], fork)):
                    result = run(name, argv, cwd, out, report)
                    if result["status"] != "PASS":
                        errors.append(f"{name} failed")
                        break
                if not errors:
                    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fork, text=True).strip()
                    parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=fork, text=True).strip()
                    grandparent = subprocess.check_output(["git", "rev-parse", "HEAD^^"], cwd=fork, text=True).strip()
                    official = subprocess.check_output(["git", "rev-parse", "HEAD^^^"], cwd=fork, text=True).strip()
                    if (actual != rev or parent != COMPATIBILITY_PARENT
                            or grandparent != RAND_COMPATIBILITY_PARENT or official != OFFICIAL_BASE):
                        errors.append("fork revision or reviewed three-commit ancestry differs")
                    if fork_source_status(fork):
                        errors.append("fork source checkout is dirty before qualification")
                if not errors:
                    generated = run("fork-lock-resolution", ["cargo", "generate-lockfile"], fork, out, report)
                    lock = fork / "Cargo.lock"
                    if generated["status"] != "PASS" or not lock.is_file():
                        errors.append("fork lock resolution failed")
                    else:
                        report["fork_lock_sha256"] = sha(lock)
                        (out / "fork-Cargo.lock").write_bytes(lock.read_bytes())
                        save(out / "report.json", report)
                if not errors:
                    for name, argv, cwd, minimum, named in (
                        ("fork-rand-compat", ["cargo", "test", "--locked", "-p", "tract-onnx-opl", "rand_compat_tests"], fork, 4, TESTS),
                        ("fork-seven-check", ["cargo", "check", "--locked", "-p", "tract-onnx", "--all-targets", "--all-features"], fork, 0, set()),
                        ("sotf-inference", ["cargo", "test", "--locked", "-p", "sotf-plugin-upmixer", "--features", "onnx", "--lib", "test_inference_with_dummy_model"], ROOT / "sotf-daw", 1, {"test_inference_with_dummy_model"}),
                        ("sotf-inference-reset", ["cargo", "test", "--locked", "-p", "sotf-plugin-upmixer", "--features", "onnx", "--lib", "reset_during_streaming_recovers_with_fresh_result"], ROOT / "sotf-daw", 1, {"reset_during_streaming_recovers_with_fresh_result"}),
                        ("sotf-upmixer-onnx-lib", ["cargo", "test", "--locked", "-p", "sotf-plugin-upmixer", "--features", "onnx", "--lib"], ROOT / "sotf-daw", 2, {"test_inference_with_dummy_model", "reset_during_streaming_recovers_with_fresh_result"}),
                        ("sotf-metadata", ["cargo", "metadata", "--locked", "--format-version", "1", "--all-features"], ROOT / "sotf", 0, set()),
                        ("daw-metadata", ["cargo", "metadata", "--locked", "--format-version", "1", "--all-features"], ROOT / "sotf-daw", 0, set()),
                        ("sotf-all-targets", ["cargo", "check", "--locked", "--workspace", "--all-targets", "--all-features"], ROOT / "sotf", 0, set()),
                        ("daw-all-targets", ["cargo", "check", "--locked", "--workspace", "--all-targets", "--all-features"], ROOT / "sotf-daw", 0, set()),
                    ):
                        if STOP:
                            errors.append("interrupted")
                            break
                        entry = run(name, argv, cwd, out, report)
                        if (entry["status"] != "PASS" or entry["passed_tests"] < minimum
                                or entry["ignored_tests"] or not named.issubset(entry["named_tests"])):
                            errors.append(f"{name}: command or exact test inventory failed")
                        if name.endswith("metadata") and entry["status"] == "PASS":
                            try:
                                report[name + "-resolved"] = metadata_packages(Path(entry["log"]), rev)
                            except Exception as error:
                                errors.append(f"{name}: {error}")
                        if not entry["cleanup"]["ok"]:
                            break
                if fork.is_dir() and (fork / ".git").is_dir():
                    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fork, text=True).strip() != rev:
                        errors.append("fork revision changed")
                    if not (fork / "Cargo.lock").is_file() or sha(fork / "Cargo.lock") != report.get("fork_lock_sha256"):
                        errors.append("fork resolved Cargo.lock changed or absent")
                    if fork_source_status(fork):
                        errors.append("fork source checkout became dirty during qualification")
    except BaseException as error:
        errors.append(f"qualification raised {type(error).__name__}: {error}")
    finally:
        try:
            after = source_state(ROOT, names, host_platform())
            save(out / "sources-after.json", after)
            errors.extend(source_issues(before, after, True))
            if manifest.read_bytes() != original_manifest:
                errors.append("sources.json changed")
            if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != root_rev:
                errors.append("root revision changed")
            root_status_after = root_layout_status(ROOT, pins)
            if (root_status_after != root_status_before
                    or root_status_after["missing"] or root_status_after["unexpected"]):
                errors.append("root checkout status changed")
        except BaseException as error:
            errors.append(f"after source guard raised {type(error).__name__}: {error}")
        report["errors"] = errors
        report["status"] = "PASS" if not errors and not STOP else "FAIL"
        save(out / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
