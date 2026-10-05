#!/usr/bin/env python3
"""Qualify native EQ low-rate processing, state, and the unchanged strict CLAP validator."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if platform.system() == "Darwin":
    from scripts.release import nih_macos_artifact_check as owned
    SUFFIX = ".dylib"
    FETCH = "fetch_macos_plugin_validators.sh"
elif platform.system() == "Linux":
    from scripts.release import nih_native_artifact_check as owned
    SUFFIX = ".so"
    FETCH = "fetch_linux_plugin_validators.sh"
else:
    raise RuntimeError("Linux or macOS disposable runner required")
from scripts.release.checkout_sources import read_manifest

OUTPUT = ROOT / "target/release-gitea/native-eq-rate"
owned.OUTPUT = OUTPUT
TESTS = (
    ("params::native_eq_lowrate_tests", "native_eq_frequency_preserves_valid_requests_and_rejects_invalid_clock"),
    ("params::native_eq_lowrate_tests", "native_eq_keeps_requested_state_across_validator_clocks_and_reactivation"),
    ("params::native_eq_lowrate_tests", "native_eq_changed_request_sync_is_allocation_free_and_keeps_host_value"),
    ("params::native_eq_route_tests", "state_restore_commits_explicit_route_and_schema_failure_is_transactional"),
    ("params::native_eq_route_tests", "apply_commits_pair_route_and_failed_apply_keeps_the_previous_state"),
    ("plugin::native_eq_wrapper_admission", "clap_eq_audio_refusal_preserves_state_and_control_retry_applies"),
)
LINUX_TESTS = (
    ("plugin::native_eq_vst3_wrapper_admission", "vst3_eq_control_state_bytes_round_trip_with_audible_gain"),
    ("plugin::native_eq_vst3_wrapper_admission", "vst3_eq_audio_hook_refuses_populated_state_trait_level"),
)
STATE_TESTS = (
    "state-reproducibility-basic",
    "state-reproducibility-binary",
    "state-reproducibility-buffered",
)
FEATURE = "eq"
STEM = "sotf_eq"
EXPECTED_DAW = "b8d21e564e5b415dc55f112cdfb4ec4377ab05d8"
MAC_BUNDLE_HELPER_SHA256 = "734e5b5b8220dfd3c1dd176b1a5c9d2c3f15ae0a7c07b4d5df8d1e08c9b50258"


def exact_positive(log: str, full_name: str) -> bool:
    rows = re.findall(r"^test (\S+) \.\.\. (ok|FAILED|ignored)$", log, re.MULTILINE)
    summaries = re.findall(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", log, re.MULTILINE)
    return rows == [(full_name, "ok")] and summaries == [("ok", "1", "0", "0")]


def validator_completion(log: str) -> dict[str, bool]:
    names = ("process-varying-sample-rates", *STATE_TESTS)
    return {name: (f"Test {name} completed" in log and f"Test {name} failed" not in log)
            for name in names}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise RuntimeError("disposable CI required")
    if platform.system() == "Darwin" and os.environ.get("RELEASE_MAC_NONHARDWARE") != "1":
        raise RuntimeError("nonhardware macOS gate required")
    if sys.flags.optimize or not sys.dont_write_bytecode:
        raise RuntimeError("unoptimized Python without bytecode writes required")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, owned.interrupted)
    signal.signal(signal.SIGINT, owned.interrupted)
    report: dict[str, object] = {"complete": False, "status": "RUNNING", "commands": [],
                                 "errors": [], "positive": [], "validator": {}}
    owned.save(report)
    try:
        pins = read_manifest(ROOT / "scripts/release/sources.json")[2]
        expected_daw = EXPECTED_DAW
        if pins.get("sotf-daw") != expected_daw:
            report["errors"].append("DAW source pin differs from reviewed EQ child")
        if platform.system() == "Darwin":
            helper = ROOT / "scripts/release/package_macos_clap.sh"
            if not helper.is_file() or sha256(helper) != MAC_BUNDLE_HELPER_SHA256:
                report["errors"].append("reviewed Mac CLAP bundle helper is missing or changed")
        before = owned.snapshot(pins)
        report["before"] = before
        report["errors"].extend(owned.source_errors(before, before, pins))
        env = os.environ.copy()
        env["SOTF_ARTIFACT_EVIDENCE_DIR"] = str(OUTPUT)
        for key in ("CARGO_HOME", "RUSTUP_HOME"):
            if not env.get(key) or not Path(env[key]).is_absolute():
                report["errors"].append(f"original {key} must be absolute")
        private = OUTPUT / "private-home"
        private.mkdir(exist_ok=True)
        (private / ".cargo").mkdir(exist_ok=True)
        env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
                   XDG_CACHE_HOME=str(private / "cache"), XDG_DATA_HOME=str(private / "data"),
                   PULSE_SERVER=f"unix:{OUTPUT}/no-pulse", PIPEWIRE_REMOTE="no-pipewire",
                   JACK_NO_START_SERVER="1")
        owned.save(report)
    except BaseException as exc:
        report["errors"].append(f"setup {type(exc).__name__}: {exc}")
        report["status"] = "FAIL"
        report["complete"] = False
        owned.save(report)
        return 1
    try:
        if not report["errors"]:
            owned.enable_subreaper()
            for module, name in TESTS + (LINUX_TESTS if platform.system() == "Linux" else ()):
                full = f"{module}::{name}"
                argv = ["bash", "-c", 'cd "$1" || exit 1; shift; exec "$@"', "native-eq-test",
                        str(ROOT / "sotf-daw"), "cargo", "test", "--locked", "-p", "plugins-nih",
                        "--no-default-features", "--features", "eq", "--lib", full, "--", "--exact", "--show-output"]
                entry = owned.run_owned(name, argv, report, env)
                log = Path(entry["log"]).read_text(errors="replace")
                if entry["status"] != "PASS" or not exact_positive(log, full):
                    report["errors"].append(f"missing exact positive: {name}")
                else:
                    report["positive"].append(name)
                if owned.STOP or not entry["owned_group_cleanup"]["ok"]:
                    break
        if not report["errors"] and not owned.STOP:
            fetch = owned.run_owned("validator-fetch", ["bash", f"scripts/release/{FETCH}"], report, env)
            if fetch["status"] != "PASS":
                report["errors"].append("pinned validator fetch failed")
            else:
                folder = OUTPUT / "validators"
                binary = folder / "bin/clap-validator"
                if (folder / "bin-path.txt").read_text().strip() != str(folder / "bin") or not binary.is_file():
                    report["errors"].append("validator provenance missing")
                else:
                    report["validator_binary_sha256"] = sha256(binary)
                    env["PATH"] = str(folder / "bin") + ":" + env.get("PATH", "")
        if not report["errors"] and not owned.STOP:
            artifact = OUTPUT / f"{STEM}.clap"
            build = owned.run_owned(f"build-{FEATURE}", ["bash", "-c",
                'cd "$1" || exit 1; cargo build --release --locked -p plugins-nih --no-default-features --features "$2" || exit 1; if [ "$3" = .dylib ]; then bash "$5" "target/release/libplugins_nih$3" "$4"; else cp "target/release/libplugins_nih$3" "$4"; fi',
                "eq-build", str(ROOT / "sotf-daw"), FEATURE, SUFFIX, str(artifact), str(ROOT / "scripts/release/package_macos_clap.sh")], report, env)
            payload = (artifact / "Contents/MacOS/sotf_eq") if platform.system() == "Darwin" else artifact
            if build["status"] != "PASS" or not payload.is_file() or payload.stat().st_size == 0:
                report["errors"].append("EQ CLAP build failed")
            else:
                report.setdefault("artifacts", {})[STEM] = {"sha256": sha256(payload), "bytes": payload.stat().st_size}
                entry = owned.run_owned(f"validate-{FEATURE}", ["clap-validator", "validate", str(artifact)], report, env)
                log = Path(entry["log"]).read_text(errors="replace")
                completed = validator_completion(log)
                report["validator"][STEM] = {"exit_code": entry["exit_code"], "log_sha256": sha256(Path(entry["log"])),
                                              "completed": completed}
                if entry["status"] != "PASS" or not all(completed.values()):
                    report["errors"].append("EQ strict CLAP validator failed or omitted rate/state tests; retained for review")
    except BaseException as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            after = owned.snapshot(pins)
            report["after"] = after
            report["errors"].extend(owned.source_errors(before, after, pins))
        except BaseException as exc:
            report["errors"].append(f"final source inspection {type(exc).__name__}: {exc}")
        if owned.STOP:
            report["errors"].append("interrupted")
        report["status"] = "PASS" if not report["errors"] and len(report["positive"]) == len(TESTS) + (len(LINUX_TESTS) if platform.system() == "Linux" else 0) and len(report["validator"]) == 1 else "REVIEW_REQUIRED"
        report["complete"] = report["status"] == "PASS"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
