#!/usr/bin/env python3
"""Draft Gitea-only offline qualification of the pinned Librespot candidate."""
from __future__ import annotations

import json
import hashlib
import ctypes
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

FORK = "https://github.com/pierreaubert/librespot.git"
REV = "9cc09665dd3ed55b938a7d77d4038d9038b159ae"
BASE = "cbfe064e575b22200c5f086be4e0e8f42f6fe1f9"
COMPATIBILITY_PARENT = "d19176a4c8cd9763fa99edf7ab862743cec10b54"
PLAYBACK_PARENT = "0df7e17c037d565551454a638186836fd2580087"
OLDER_PARENT = "59af8295dd8a4998ff6b9091af96cd420c11e05c"
OFFICIAL_BASE = "d36f9f1907e8cc9d68a93f8ebc6b627b1bf7267d"
META_FORK = "https://github.com/pierreaubert/metaheuristics-nature-rs.git"
META_REV = "4f0b603c521e0b4e20239c827f1a0975442bb740"
META_BASE = "b0e997ac1e667de486c3ed7931ccc931289218a7"
STOP = False


def interrupted(_signal: int, _frame: object) -> None:
    global STOP
    STOP = True


def save(path: Path, value: object) -> None:
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, indent=2) + "\n")
    pending.replace(path)


def root_checkout_status(pins: dict[str, str]) -> dict[str, list[str]]:
    """Accept exact tracked gitlinks or legacy untracked pinned siblings."""
    layout = root_layout_status(ROOT, pins)
    return {
        "allowed_sibling_checkouts": layout["allowed_siblings"],
        "tracked_gitlinks": layout["tracked_gitlinks"],
        "unexpected_root_paths": layout["unexpected"],
        "missing_sibling_checkouts": layout["missing"],
    }


def unexpected_fork_status(status: str) -> list[str]:
    """Allow only Cargo's tracked lockfile update after explicit resolution."""
    return [line for line in status.splitlines() if line != " M Cargo.lock"]


def spotify_resolved_features(log: Path, expected_rev: str) -> dict[str, list[str]]:
    """Read Cargo's resolved node features, not just manifest declarations."""
    metadata_lines = [line for line in log.read_text(errors="replace").splitlines()
                      if line.startswith("{") and '"packages"' in line and '"resolve"' in line]
    if len(metadata_lines) != 1:
        raise ValueError("Spotify cargo metadata JSON missing or ambiguous")
    metadata = json.loads(metadata_lines[0])
    packages = {package["id"]: package for package in metadata["packages"]}
    wanted = {f"librespot-{name}" for name in ("core", "playback", "metadata", "protocol")}
    expected_source = f"git+{FORK}?rev={expected_rev}#{expected_rev}"
    matched: dict[str, list[str]] = {}
    for node in metadata["resolve"]["nodes"]:
        package = packages.get(node["id"])
        if package is None or package["name"] not in wanted:
            continue
        source = package.get("source") or ""
        if source != expected_source:
            raise ValueError(f"{package['name']} has unexpected resolved source: {source}")
        if package["name"] in matched:
            raise ValueError(f"multiple resolved identities for {package['name']}")
        matched[package["name"]] = sorted(node["features"])
    if set(matched) != wanted:
        raise ValueError(f"missing resolved Librespot packages: {wanted - set(matched)}")
    playback = set(matched["librespot-playback"])
    if playback != {"native-tls"}:
        raise ValueError(f"Librespot playback enabled unexpected backend/TLS features: {sorted(playback)}")
    return matched


def members(pgid: int) -> list[dict[str, str]]:
    listing = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat="], text=True,
        capture_output=True, check=True, timeout=5,
    )
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
        # descendants after it has been polled; this runner owns no other jobs.
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
    return {"ok": not errors and not remaining, "remaining": remaining, "errors": errors}


def run(name: str, argv: list[str], cwd: Path, output: Path,
        report: dict) -> dict:
    log = output / f"{name}.log"
    entry: dict = {"name": name, "argv": argv, "cwd": str(cwd),
                   "log": str(log), "status": "RUNNING"}
    report["active_command"] = entry
    save(output / "report.json", report)
    with log.open("wb") as stream:
        child = subprocess.Popen(argv, cwd=cwd, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        code = 130
        try:
            entry["owned_pgid"] = child.pid
            save(output / "report.json", report)
            while not STOP:
                try:
                    code = child.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    print(f"[{name}] still running", flush=True)
        finally:
            entry["cleanup"] = clean_group(child)
    text = log.read_text(errors="replace")
    passed = sum(map(int, re.findall(r"test result: ok\.\s+(\d+) passed;", text)))
    passed_names = [match.rsplit("::", 1)[-1] for match in re.findall(
        r"^test\s+([^\n]+?)\s+\.\.\.\s+ok\s*$", text, re.MULTILINE,
    )]
    ignored = sum(map(int, re.findall(
        r"test result: ok\.[^\n]*?;\s+(\d+) ignored;", text,
    )))
    entry.update({"status": "PASS" if code == 0 and entry["cleanup"]["ok"] else "FAIL",
                  "exit_code": code, "passed_tests": passed,
                  "passed_named_tests": passed_names, "ignored_tests": ignored})
    report["commands"].append(entry)
    report.pop("active_command", None)
    save(output / "report.json", report)
    if entry["status"] == "FAIL":
        print(f"[{name}] exit={code}; cleanup={entry['cleanup']['ok']}\n" +
              "\n".join(text.splitlines()[-80:]), flush=True)
    return entry


def main() -> int:
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    enable_subreaper()
    if len(sys.argv) != 2 or not os.getenv("CI"):
        print("usage: Gitea CI librespot_candidate_check.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = ROOT / "scripts/release/sources.json"
    original_manifest = manifest.read_bytes()
    (output / "sources.json").write_bytes(original_manifest)
    root_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                            text=True).strip()
    _, _, pins = read_manifest(manifest)
    root_status_before = root_checkout_status(pins)
    before = source_state(ROOT, list(workspace_map()), host_platform())
    save(output / "sources-before.json", before)
    errors = source_issues(before, before, True)
    if root_status_before["unexpected_root_paths"] or root_status_before["missing_sibling_checkouts"]:
        errors.append(f"root checkout contains unexpected or missing paths: {root_status_before}")
    for name, pin in pins.items():
        if before.get(name, {}).get("revision") != pin:
            errors.append(f"{name}: checkout differs from sources.json")
    workspace_deps = tomllib.loads((ROOT / "sotf/Cargo.toml").read_text())[
        "workspace"
    ]["dependencies"]
    for package in ("librespot-core", "librespot-playback", "librespot-metadata",
                    "librespot-protocol"):
        dependency = workspace_deps.get(package, {})
        tls_features = ["native-tls"] if package != "librespot-protocol" else None
        if (dependency.get("git") != FORK or dependency.get("rev") != REV or
                dependency.get("version") != "0.8" or
                dependency.get("default-features") is not False or
                (tls_features is not None and dependency.get("features") != tls_features)):
            errors.append(f"{package}: missing reviewed minimal-feature fork declaration")
    if workspace_deps.get("oauth2", {}).get("version") != "5":
        errors.append("Spotify OAuth2 v5 workspace declaration is absent")
    for workspace in ("sotf", "autoeq"):
        declared = tomllib.loads((ROOT / workspace / "Cargo.toml").read_text())[
            "workspace"
        ]["dependencies"].get("metaheuristics-nature", {})
        if (declared.get("git") != META_FORK or declared.get("rev") != META_REV
                or declared.get("version") != "10.1"):
            errors.append(f"{workspace}: metaheuristics does not use the reviewed shared fork")
    report: dict = {"status": "RUNNING", "root_revision": root_revision,
                    "root_status_before": root_status_before,
                    "fork_revision": REV, "fork_base": BASE,
                    "official_base": OFFICIAL_BASE,
                    "meta_fork_revision": META_REV, "meta_official_base": META_BASE,
                    "commands": [], "errors": errors}
    save(output / "report.json", report)
    if not errors:
        with tempfile.TemporaryDirectory(prefix="librespot-candidate-") as temp:
            fork = Path(temp) / "librespot"
            meta_fork = Path(temp) / "metaheuristics-nature"
            steps = [("fork-clone", ["git", "clone", "--no-checkout", FORK, str(fork)], ROOT),
                     ("fork-checkout", ["git", "checkout", "--detach", REV], fork),
                     ("meta-clone", ["git", "clone", "--no-checkout", META_FORK, str(meta_fork)], ROOT),
                     ("meta-checkout", ["git", "checkout", "--detach", META_REV], meta_fork)]
            for name, argv, cwd in steps:
                outcome = run(name, argv, cwd, output, report)
                if outcome["status"] != "PASS":
                    errors.append(f"{name}: source acquisition failed")
                    break
            if not errors:
                actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fork,
                                                 text=True).strip()
                parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=fork,
                                                 text=True).strip()
                compatibility_parent = subprocess.check_output(
                    ["git", "rev-parse", "HEAD^^"], cwd=fork, text=True,
                ).strip()
                playback_parent = subprocess.check_output(
                    ["git", "rev-parse", "HEAD^^^"], cwd=fork, text=True,
                ).strip()
                older_parent = subprocess.check_output(
                    ["git", "rev-parse", "HEAD^^^^"], cwd=fork, text=True,
                ).strip()
                official = subprocess.check_output(["git", "rev-parse", "HEAD^^^^^"], cwd=fork,
                                                   text=True).strip()
                if (actual != REV or parent != BASE
                        or compatibility_parent != COMPATIBILITY_PARENT
                        or playback_parent != PLAYBACK_PARENT
                        or older_parent != OLDER_PARENT
                        or official != OFFICIAL_BASE):
                    errors.append("fork revision or official base differs from reviewed candidate")
                dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=fork,
                                                text=True).rstrip("\n")
                if dirty:
                    errors.append(f"fork checkout was dirty before validation: {dirty}")
                lock = fork / "Cargo.lock"
                save(output / "fork-before.json", {
                    "revision": actual, "parent": parent,
                    "compatibility_parent": compatibility_parent,
                    "playback_parent": playback_parent, "older_parent": older_parent,
                    "official_base": official,
                    "dirty": dirty,
                    "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()
                    if lock.is_file() else None,
                })
                meta_actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=meta_fork,
                                                      text=True).strip()
                meta_parent = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=meta_fork,
                                                      text=True).strip()
                meta_dirty = subprocess.check_output(["git", "status", "--porcelain"],
                                                     cwd=meta_fork, text=True).rstrip("\n")
                if meta_actual != META_REV or meta_parent != META_BASE or meta_dirty:
                    errors.append("metaheuristics fork revision, ancestry, or cleanliness differs")
                meta_lock = meta_fork / "Cargo.lock"
                save(output / "meta-before.json", {
                    "revision": meta_actual, "parent": meta_parent, "dirty": meta_dirty,
                    "lock_sha256": hashlib.sha256(meta_lock.read_bytes()).hexdigest()
                    if meta_lock.is_file() else None,
                })
            if not errors:
                for name, cwd in (("librespot-lock-resolution", fork),
                                  ("meta-lock-resolution", meta_fork)):
                    outcome = run(name, ["cargo", "generate-lockfile"], cwd,
                                  output, report)
                    if outcome["status"] != "PASS" or not (cwd / "Cargo.lock").is_file():
                        errors.append(f"{name}: explicit fork lock resolution failed")
                    if not outcome["cleanup"]["ok"] or errors:
                        break
                if not errors:
                    save(output / "fork-lock-resolution.json", {
                        "librespot_before": json.loads((output / "fork-before.json").read_text())["lock_sha256"],
                        "librespot_after": hashlib.sha256((fork / "Cargo.lock").read_bytes()).hexdigest(),
                        "meta_before": json.loads((output / "meta-before.json").read_text())["lock_sha256"],
                        "meta_after": hashlib.sha256((meta_fork / "Cargo.lock").read_bytes()).hexdigest(),
                    })
            if not errors:
                meta_checks = [
                    ("meta-no-default", ["cargo", "check", "--locked", "--lib", "--no-default-features"]),
                    ("meta-all-features", ["cargo", "test", "--locked", "--all-features", "--all-targets"]),
                ]
                if host_platform() == "linux":
                    meta_checks.append((
                        "meta-wasm-no-default",
                        ["cargo", "check", "--locked", "--lib", "--no-default-features", "--target", "wasm32-unknown-unknown"],
                    ))
                for name, argv in meta_checks:
                    outcome = run(name, argv, meta_fork, output, report)
                    if (outcome["status"] != "PASS" or outcome["ignored_tests"]
                            or (name == "meta-all-features" and (
                                outcome["passed_tests"] == 0 or
                                "seeded_generators_replay_values_and_streams"
                                not in outcome["passed_named_tests"]))):
                        errors.append(f"{name}: fork check or exact seeded regression failed")
                    if not outcome["cleanup"]["ok"]:
                        break
            if not errors:
                metadata = run(
                    "spotify-resolved-features",
                    ["cargo", "metadata", "--locked", "--format-version", "1"],
                    ROOT / "sotf", output, report,
                )
                if metadata["status"] != "PASS":
                    errors.append("Spotify locked Cargo metadata failed")
                else:
                    try:
                        report["librespot_resolved_features"] = spotify_resolved_features(
                            Path(metadata["log"]), REV,
                        )
                    except Exception as error:
                        errors.append(f"Librespot resolved feature audit failed: {error}")
            if not errors:
                tests = [
                    ("playback-pcm-eof-seek", fork, ["cargo", "test", "-p", "librespot-playback", "--no-default-features", "--features", "native-tls", "symphonia_six_decodes_stereo_pcm_without_changing_channel_order"]),
                    ("playback-standard-tags", fork, ["cargo", "test", "-p", "librespot-playback", "--no-default-features", "--features", "native-tls", "symphonia_six_standard_tags_preserve_replaygain_and_local_metadata"]),
                    ("playback-local-duration", fork, ["cargo", "test", "-p", "librespot-playback", "--no-default-features", "--features", "native-tls", "local_wav_fixture_preserves_one_second_duration"]),
                    ("dither-distributions", fork, ["cargo", "test", "-p", "librespot-playback", "--no-default-features", "--features", "native-tls", "seeded_dither_distributions_preserve_zero_mean_and_variance"]),
                    ("dither-channels", fork, ["cargo", "test", "-p", "librespot-playback", "--no-default-features", "--features", "native-tls", "high_pass_dither_keeps_independent_channel_histories"]),
                    ("dither-replay", fork, ["cargo", "test", "-p", "librespot-playback", "--no-default-features", "--features", "native-tls", "seeded_dither_replay_is_bit_identical"]),
                    ("oauth-native", fork, ["cargo", "test", "-p", "librespot-oauth", "--no-default-features", "--features", "native-tls", "bridge_preserves_oauth_request_and_response"]),
                    ("oauth-rustls", fork, ["cargo", "test", "-p", "librespot-oauth", "--no-default-features", "--features", "rustls-tls-native-roots", "bridge_preserves_oauth_request_and_response"]),
                    ("oauth-webpki", fork, ["cargo", "test", "-p", "librespot-oauth", "--no-default-features", "--features", "rustls-tls-webpki-roots", "bridge_preserves_oauth_request_and_response"]),
                    ("oauth-webpki-mixed-provider", fork, ["cargo", "test", "-p", "librespot-oauth", "--no-default-features", "--features", "rustls-tls-webpki-roots,rustls/ring", "selected_tls_backend_builds_blocking_and_async_clients"]),
                    ("fork-playback-all-targets", fork, ["cargo", "check", "-p", "librespot-playback", "--all-targets", "--no-default-features", "--features", "native-tls"]),
                    ("fork-oauth-native-all-targets", fork, ["cargo", "check", "-p", "librespot-oauth", "--all-targets", "--no-default-features", "--features", "native-tls"]),
                    ("fork-oauth-rustls-all-targets", fork, ["cargo", "check", "-p", "librespot-oauth", "--all-targets", "--no-default-features", "--features", "rustls-tls-native-roots"]),
                    ("fork-oauth-webpki-all-targets", fork, ["cargo", "check", "-p", "librespot-oauth", "--all-targets", "--no-default-features", "--features", "rustls-tls-webpki-roots"]),
                    ("spotify-mocks", ROOT / "sotf", ["cargo", "test", "--locked", "-p", "sotf-service-spotify", "--lib"]),
                    ("spotify-all-targets", ROOT / "sotf", ["cargo", "check", "--locked", "-p", "sotf-service-spotify", "--all-targets", "--all-features"]),
                ]
                for _name, cwd, argv in tests:
                    if cwd == fork and "--locked" not in argv:
                        argv.insert(2, "--locked")
                for name, cwd, argv in tests:
                    if STOP:
                        errors.append("interrupted")
                        break
                    outcome = run(name, argv, cwd, output, report)
                    minimum = (0 if name.endswith("all-targets") else
                               41 if name == "spotify-mocks" else
                               1 if name == "oauth-webpki-mixed-provider" else
                               2 if name.startswith("oauth-") else 1)
                    expected_names = {
                        "playback-pcm-eof-seek": {
                            "symphonia_six_decodes_stereo_pcm_without_changing_channel_order"},
                        "playback-standard-tags": {
                            "symphonia_six_standard_tags_preserve_replaygain_and_local_metadata"},
                        "playback-local-duration": {
                            "local_wav_fixture_preserves_one_second_duration"},
                        "dither-distributions": {
                            "seeded_dither_distributions_preserve_zero_mean_and_variance"},
                        "dither-channels": {
                            "high_pass_dither_keeps_independent_channel_histories"},
                        "dither-replay": {"seeded_dither_replay_is_bit_identical"},
                        "oauth-native": {
                            "blocking_bridge_preserves_oauth_request_and_response",
                            "async_bridge_preserves_oauth_request_and_response"},
                        "oauth-rustls": {
                            "blocking_bridge_preserves_oauth_request_and_response",
                            "async_bridge_preserves_oauth_request_and_response"},
                        "oauth-webpki": {
                            "blocking_bridge_preserves_oauth_request_and_response",
                            "async_bridge_preserves_oauth_request_and_response"},
                        "oauth-webpki-mixed-provider": {
                            "selected_tls_backend_builds_blocking_and_async_clients"},
                    }.get(name, set())
                    if (outcome["status"] != "PASS" or outcome["passed_tests"] < minimum
                            or outcome["ignored_tests"] or
                            not expected_names.issubset(set(outcome["passed_named_tests"]))):
                        errors.append(f"{name}: command failed, named test inventory incomplete, or tests ignored")
                    if not outcome["cleanup"]["ok"]:
                        break
            if fork.is_dir() and (fork / ".git").is_dir():
                lock = fork / "Cargo.lock"
                fork_revision_after = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=fork, text=True,
                ).strip()
                if fork_revision_after != REV:
                    errors.append("Librespot fork revision changed during qualification")
                if lock.is_file():
                    (output / "fork-Cargo.lock").write_bytes(lock.read_bytes())
                expected_lock = (output / "fork-lock-resolution.json")
                if not expected_lock.is_file() or not lock.is_file():
                    errors.append("Librespot fork resolved lock or provenance is missing")
                else:
                    expected = json.loads(expected_lock.read_text())["librespot_after"]
                    if hashlib.sha256(lock.read_bytes()).hexdigest() != expected:
                        errors.append("Librespot fork lock changed after explicit resolution")
                dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=fork,
                                                text=True).rstrip("\n")
                save(output / "fork-after.json", {
                    "revision": fork_revision_after,
                    "dirty": dirty,
                    "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()
                    if lock.is_file() else None,
                })
                if unexpected_fork_status(dirty):
                    errors.append("fork source files changed during qualification")
            if meta_fork.is_dir() and (meta_fork / ".git").is_dir():
                lock = meta_fork / "Cargo.lock"
                meta_revision_after = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=meta_fork, text=True,
                ).strip()
                if meta_revision_after != META_REV:
                    errors.append("metaheuristics fork revision changed during qualification")
                if lock.is_file():
                    (output / "meta-Cargo.lock").write_bytes(lock.read_bytes())
                expected_lock = (output / "fork-lock-resolution.json")
                if not expected_lock.is_file() or not lock.is_file():
                    errors.append("metaheuristics fork resolved lock or provenance is missing")
                else:
                    expected = json.loads(expected_lock.read_text())["meta_after"]
                    if hashlib.sha256(lock.read_bytes()).hexdigest() != expected:
                        errors.append("metaheuristics fork lock changed after explicit resolution")
                dirty = subprocess.check_output(["git", "status", "--porcelain"],
                                                cwd=meta_fork, text=True).rstrip("\n")
                save(output / "meta-after.json", {
                    "revision": meta_revision_after,
                    "dirty": dirty,
                    "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest()
                    if lock.is_file() else None,
                })
                if unexpected_fork_status(dirty):
                    errors.append("metaheuristics fork source files changed during qualification")
    try:
        after = source_state(ROOT, list(workspace_map()), host_platform())
        save(output / "sources-after.json", after)
        errors.extend(source_issues(before, after, True))
        if manifest.read_bytes() != original_manifest:
            errors.append("source manifest changed")
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip() != root_revision:
            errors.append("root revision changed")
        root_status_after = root_checkout_status(pins)
        report["root_status_after"] = root_status_after
        if root_status_after != root_status_before or root_status_after["unexpected_root_paths"]:
            errors.append("root checkout status changed or contains unexpected paths")
    except Exception as error:
        errors.append(f"after-source guard failed: {error}")
    report["status"] = "PASS" if not errors and not STOP else "FAIL"
    report["errors"] = errors
    save(output / "report.json", report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        if len(sys.argv) == 2:
            output = Path(sys.argv[1]).resolve()
            report_path = output / "report.json"
            if output.is_dir():
                report = (json.loads(report_path.read_text()) if report_path.is_file()
                          else {"commands": [], "errors": []})
                report["status"] = "FAIL"
                report.setdefault("errors", []).append(f"runner exception: {error}")
                try:
                    after = source_state(ROOT, list(workspace_map()), host_platform())
                    save(output / "sources-after.json", after)
                    before_path = output / "sources-before.json"
                    if before_path.is_file():
                        before = json.loads(before_path.read_text())
                        report["errors"].extend(source_issues(before, after, True))
                    else:
                        report["errors"].append("before-source snapshot unavailable")
                except Exception as guard_error:
                    report["errors"].append(f"failure-path source guard: {guard_error}")
                save(report_path, report)
        raise
