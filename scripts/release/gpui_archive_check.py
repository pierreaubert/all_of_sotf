#!/usr/bin/env python3
"""Qualify GPUI archive extraction on the exact aggregate release sources."""

import hashlib
import json
import os
import ctypes
from pathlib import Path
import re
import tomllib
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release.checkout_sources import clone_env

GPUI_BASE = "8da11c6acf383ed52fa2b2c069f70121b8242616"
BASELINE_ROOT = "7a3686393b6ef41cb0b605c3e63f5573a0014604"
TESTS = (
    "tar_downloads_with_both_codecs_and_digest_modes_on_futures_and_smol",
    "tar_corruption_truncation_and_digest_mismatch_leave_no_destination",
    "tar_traversal_symlink_and_pax_entries_stay_within_staging",
    "downloads_raw_binary_into_destination_dir",
    "raw_binary_digest_mismatch_cleans_up_staging",
)
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


def enable_subreaper() -> None:
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "PR_SET_CHILD_SUBREAPER failed")


def clean_group(child: subprocess.Popen[bytes]) -> dict:
    errors: list[str] = []
    remaining: list[dict[str, str]] = []

    def reap_owned_descendants() -> None:
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
    return {"ok": not errors and not remaining, "errors": errors, "remaining": remaining}


def command(name: str, argv: list[str], cwd: Path, evidence: Path,
            env: dict[str, str] | None = None) -> dict:
    log_path = evidence / f"{name}.log"
    entry: dict = {"name": name, "argv": argv, "log": str(log_path), "status": "RUNNING"}
    if INTERRUPTED:
        entry.update({"exit_code": 130, "status": "FAIL", "not_started": True,
                      "cleanup": {"ok": True, "errors": [], "remaining": []}, "text": ""})
        return entry
    with log_path.open("wb") as log:
        if INTERRUPTED:
            entry.update({"exit_code": 130, "status": "FAIL", "not_started": True,
                          "cleanup": {"ok": True, "errors": [], "remaining": []}, "text": ""})
            return entry
        child: subprocess.Popen[bytes] | None = None
        code = 130
        try:
            child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
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
                entry["cleanup"] = clean_group(child)
    text = log_path.read_text(errors="replace")
    entry.update({"exit_code": code, "text": text,
                  "status": "PASS" if code == 0 and entry["cleanup"]["ok"] else "FAIL"})
    return entry


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def ensure_historical_blob(repo: Path, revision: str, relative: str,
                           auth_env: dict[str, str], evidence: Path, report: dict) -> dict:
    wanted = f"{revision}:{relative}"
    exists = subprocess.run(["git", "cat-file", "-e", wanted], cwd=repo,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not exists:
        run_required(f"fetch-{repo.name}-{revision[:12]}",
                     ["git", "fetch", "--no-tags", "--depth=1", "origin", revision],
                     repo, evidence, report, env=auth_env)
    blob = git(repo, "rev-parse", wanted)
    if len(blob) != 40:
        raise RuntimeError(f"invalid historical blob identity {wanted}")
    return {"repository": repo.name, "revision": revision, "path": relative,
            "blob": blob, "fetched": not exists}


def locks(root: Path, revisions: dict[str, str] | None = None) -> dict[str, bytes]:
    result = {}
    for name in sorted(json.loads((root / "scripts/release/sources.json").read_text())["sources"]):
        paths = ["Cargo.lock"]
        if name == "autoeq":
            paths.append("crates/autoeq-gpui-examples/Cargo.lock")
        for relative in paths:
            key = f"{name}/{relative}"
            if revisions is None:
                result[key] = (root / key).read_bytes()
            else:
                result[key] = subprocess.check_output(
                    ["git", "show", f"{revisions[name]}:{relative}"], cwd=root / name
                )
    if len(result) != 10:
        raise RuntimeError(f"expected ten locks, found {len(result)}")
    return result


def duplicate_groups(lock_bytes: dict[str, bytes]) -> set[tuple[str, str]]:
    names: dict[str, set[str]] = {}
    sources: dict[tuple[str, str], set[str]] = {}
    for data in lock_bytes.values():
        for package in tomllib.loads(data.decode())["package"]:
            name, version = package["name"], package["version"]
            names.setdefault(name, set()).add(version)
            sources.setdefault((name, version), set()).add(package.get("source", "path/local"))
    groups = {("multiple_versions", name) for name, versions in names.items()
              if len(versions) > 1}
    groups.update(("mixed_sources", name) for (name, _), values in sources.items()
                  if len(values) > 1)
    return groups


def source_state(root: Path, expected: dict[str, str]) -> dict:
    state: dict = {"root_revision": git(root, "rev-parse", "HEAD"), "sources": {}}
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("aggregate root changed or contains untracked files")
    for name, revision in sorted(expected.items()):
        path = root / name
        entry = git(root, "ls-files", "--stage", "--", name).split()
        if len(entry) != 4 or entry[0] != "160000" or entry[1] != revision or entry[2] != "0":
            raise RuntimeError(f"{name}: root gitlink differs from manifest")
        actual = git(path, "rev-parse", "HEAD")
        status = git(path, "status", "--porcelain", "--untracked-files=all")
        if actual != revision or status:
            raise RuntimeError(f"{name}: checkout differs from clean pinned revision")
        state["sources"][name] = actual
    state["locks"] = {name: hashlib.sha256(data).hexdigest()
                      for name, data in locks(root).items()}
    return state


def run_required(name: str, argv: list[str], cwd: Path, evidence: Path, report: dict,
                 env: dict[str, str] | None = None) -> str:
    result = command(name, argv, cwd, evidence, env=env)
    report["commands"].append({key: value for key, value in result.items() if key != "text"})
    if result["status"] != "PASS":
        raise RuntimeError(f"{name}: command failed or left owned processes")
    return result["text"]


def main() -> int:
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    evidence = Path(sys.argv[1]).resolve()
    platform_name = sys.argv[2]
    baseline_root = BASELINE_ROOT
    report: dict = {"schema": 1, "platform": platform_name, "baseline_root": baseline_root,
                    "commands": [], "errors": []}
    if (platform_name not in {"linux", "macos"} or os.environ.get("CI") != "true"
            or os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1"
            or (platform_name == "macos") != (sys.platform == "darwin")):
        print("archive qualification requires a disposable matching Gitea runner", file=sys.stderr)
        return 2
    enable_subreaper()
    evidence.mkdir(parents=True, exist_ok=True)
    expected: dict[str, str] = {}
    try:
        manifest_bytes = (ROOT / "scripts/release/sources.json").read_bytes()
        expected = {name: entry["revision"] for name, entry in
                    json.loads(manifest_bytes)["sources"].items()}
        report["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        before = source_state(ROOT, expected)
        report["before"] = before
        manifest = json.loads(manifest_bytes)
        auth_env = clone_env(manifest["server"], manifest["owner"])
        for key in list(auth_env):
            if key.startswith("GIT_TRACE") or key in {"GIT_CURL_VERBOSE", "CURL_VERBOSE"}:
                auth_env.pop(key)
        historical = [ensure_historical_blob(ROOT, baseline_root,
                                              "scripts/release/sources.json", auth_env,
                                              evidence, report)]
        old_manifest = json.loads(subprocess.check_output(
            ["git", "show", f"{baseline_root}:scripts/release/sources.json"], cwd=ROOT
        ))
        old_revisions = {name: entry["revision"] for name, entry in old_manifest["sources"].items()}
        if set(old_revisions) != set(expected):
            raise RuntimeError("baseline source inventory differs")
        if old_revisions["gpui-toolkit"] != GPUI_BASE:
            raise RuntimeError("baseline does not pin the reviewed GPUI parent")
        for name, revision in sorted(old_revisions.items()):
            paths = ["Cargo.lock"]
            if name == "autoeq":
                paths.append("crates/autoeq-gpui-examples/Cargo.lock")
            for relative in paths:
                historical.append(ensure_historical_blob(ROOT / name, revision,
                                                          relative, auth_env, evidence, report))
        report["historical_blobs"] = historical
        os.environ.pop("GITEA_TOKEN", None)
        old_locks = locks(ROOT, old_revisions)
        new_locks = locks(ROOT)
        previous_groups = duplicate_groups(old_locks)
        current_groups = duplicate_groups(new_locks)
        new_groups = sorted(current_groups - previous_groups)
        report["dependency_groups"] = {"baseline": sorted(previous_groups),
                                       "current": sorted(current_groups), "added": new_groups}
        if new_groups:
            raise RuntimeError(f"new duplicate dependency groups: {new_groups}")
        gpui_packages = {(item["name"], item["version"]) for item in
                         tomllib.loads(new_locks["gpui-toolkit/Cargo.lock"].decode())["package"]}
        obsolete = sorted([
            (name, version) for name, version in gpui_packages
            if name == "async-std"
            or (name == "async-channel" and version.startswith("1."))
            or (name == "event-listener" and version.startswith("2."))
        ])
        report["obsolete_runtime_packages"] = obsolete
        if obsolete:
            raise RuntimeError(f"old async-tar runtime chain remains: {obsolete}")

        workspace = ROOT / "gpui-toolkit"
        for test_name in TESTS:
            text = run_required(test_name,
                                ["cargo", "test", "--locked", "-p", "gpui-toolkit-http-client",
                                 "--features", "github-download", "--lib", test_name, "--",
                                 "--test-threads=1", "--show-output"],
                                workspace, evidence, report)
            if not re.search(rf"(?m)^test\s+\S*::{re.escape(test_name)}\s+\.\.\.\s+ok$", text):
                raise RuntimeError(f"{test_name}: named test did not pass")
            if not re.search(r"test result: ok\.\s+1 passed; 0 failed; 0 ignored;", text):
                raise RuntimeError(f"{test_name}: unexpected test inventory")
        for package in ("gpui-toolkit-http-client", "gpui-toolkit-gpui"):
            run_required(f"{package}-all-targets",
                         ["cargo", "check", "--locked", "-p", package,
                          "--all-targets", "--all-features"], workspace, evidence, report)
        after = source_state(ROOT, expected)
        report["after"] = after
        if after != before or hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest() != report["manifest_sha256"]:
            raise RuntimeError("source, manifest, or one of ten locks changed")
    except Exception as error:
        report["errors"].append(str(error))
        if expected:
            try:
                report["after"] = source_state(ROOT, expected)
            except Exception as inspection_error:
                report["errors"].append(f"final source inspection: {inspection_error}")
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
