#!/usr/bin/env python3
"""Qualify two native low-rate fixes without hiding other validator failures."""
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

OUTPUT = ROOT / "target/release-gitea/band-hiss-low-rate"
owned.OUTPUT = OUTPUT
TESTS = (
    ("plugins-nih", "params::default_sync_tests", "native_band_split_constructs_with_requested_cutoff_at_fractional_low_rate"),
    ("plugins-nih", "params::default_sync_tests", "native_hiss_uses_effective_low_rate_cutoff_without_changing_host_request"),
    ("plugins-nih", "wrapper::process_tests", "bandsplit_state_migration_preserves_legacy_mode_and_rejects_layout_conflict"),
    ("plugins-nih", "params::hiss_profile_tests", "hiss_native_malformed_rejected_live_retained"),
    ("plugins-nih", "params::hiss_profile_tests", "hiss_native_process_path_allocates_and_locks_nothing"),
    ("sotf-plugin-band-split", "tests", "test_initialize_rejects_frequency_above_sample_rate_limit"),
    ("sotf-plugin-band-split", "tests", "test_dynamic_frequency_validation_is_transactional"),
)
FEATURES = (("band-split", "sotf_band_split"), ("hiss-reducer", "sotf_hiss_reducer"))
EXPECTED_DAW = "834d68a4abb2568378a22acae07194983d4f09b5"


def exact_positive(log: str, full_name: str) -> bool:
    rows = re.findall(r"^test (\S+) \.\.\. (ok|FAILED|ignored)$", log, re.MULTILINE)
    summaries = re.findall(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;", log, re.MULTILINE)
    return rows == [(full_name, "ok")] and summaries == [("ok", "1", "0", "0")]


def rate_test_completed(log: str) -> bool:
    return ("Test process-varying-sample-rates completed" in log
            and "Test process-varying-sample-rates failed" not in log)


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
        if pins.get("sotf-daw") != EXPECTED_DAW:
            report["errors"].append("DAW source pin differs from reviewed BandSplit/Hiss child")
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
            for package, module, name in TESTS:
                full = f"{module}::{name}"
                argv = ["bash", "-c", 'cd "$1" || exit 1; shift; exec "$@"', "band-hiss-test",
                        str(ROOT / "sotf-daw"), "cargo", "test", "--locked", "-p", package,
                        "--lib", full, "--", "--exact", "--show-output"]
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
        validator_failures = []
        for feature, stem in FEATURES:
            if report["errors"] or owned.STOP:
                break
            artifact = OUTPUT / f"{stem}.clap"
            build = owned.run_owned(f"build-{feature}", ["bash", "-c",
                'cd "$1" || exit 1; cargo build --release --locked -p plugins-nih --no-default-features --features "$2" || exit 1; cp "target/release/libplugins_nih$3" "$4"',
                "band-hiss-build", str(ROOT / "sotf-daw"), feature, SUFFIX, str(artifact)], report, env)
            if build["status"] != "PASS" or not artifact.is_file() or artifact.stat().st_size == 0:
                report["errors"].append(f"{feature} CLAP build failed")
                continue
            report.setdefault("artifacts", {})[stem] = {"sha256": sha256(artifact), "bytes": artifact.stat().st_size}
            entry = owned.run_owned(f"validate-{feature}", ["clap-validator", "validate", str(artifact)], report, env)
            log = Path(entry["log"]).read_text(errors="replace")
            rate_completed = rate_test_completed(log)
            report["validator"][stem] = {"exit_code": entry["exit_code"], "log_sha256": sha256(Path(entry["log"])),
                                          "rate_test_completed": rate_completed}
            if entry["status"] != "PASS" or not rate_completed:
                validator_failures.append(f"{feature} strict CLAP validator failed or omitted rate test; retained for review")
        report["errors"].extend(validator_failures)
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
        report["status"] = "PASS" if not report["errors"] and len(report["positive"]) == len(TESTS) and len(report["validator"]) == 2 else "REVIEW_REQUIRED"
        report["complete"] = report["status"] == "PASS"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
