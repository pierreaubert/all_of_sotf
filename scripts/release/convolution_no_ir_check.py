#!/usr/bin/env python3
"""Focused no-IR restore proof; the full 43-plugin validator remains separate."""
from __future__ import annotations

import json
import hashlib
import os
import platform
from pathlib import Path
import re
import signal
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if platform.system() == "Darwin":
    from scripts.release import nih_macos_artifact_check as owned
    SUFFIX = ".dylib"
    FETCH = "fetch_macos_plugin_validators.sh"
else:
    from scripts.release import nih_native_artifact_check as owned
    SUFFIX = ".so"
    FETCH = "fetch_linux_plugin_validators.sh"
from scripts.release.checkout_sources import read_manifest

OUTPUT = ROOT / "target/release-gitea/convolution-no-ir"
owned.OUTPUT = OUTPUT

NEW = (
    "dry_state_restore_publishes_mix_and_gain_without_pending_resource",
    "invalid_ir_restore_preserves_visible_scalars_and_dry_resource_state",
    "removing_committed_ir_keeps_parameter_restore_transactional",
)
RESOURCE = (
    "clap_state_stream_handles_short_reads_and_rejects_untrusted_lengths",
    "clap_state_restore_stages_true_stereo_resource_and_survives_rejections",
    "vst3_component_state_restore_stages_true_stereo_resource_and_preserves_audio",
)
STATE = (
    "state-reproducibility-basic",
    "state-reproducibility-buffered",
    "state-reproducibility-binary",
)


def rust_positive(log: str, full_name: str) -> bool:
    leaves = re.findall(r"^test (\S+) \.\.\. (ok|FAILED|ignored)$", log, re.MULTILINE)
    summaries = re.findall(
        r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored;",
        log, re.MULTILINE,
    )
    return leaves == [(full_name, "ok")] and summaries == [("ok", "1", "0", "0")]


def clap_state_positives(log: str) -> bool:
    completed = re.findall(r"Test (state-reproducibility-[\w-]+) completed", log)
    failed = re.findall(r"Test (state-reproducibility-[\w-]+) failed", log)
    return not failed and len(completed) == len(set(completed)) and set(STATE) <= set(completed)


def compiled_artifact_evidence() -> dict[str, object]:
    built = ROOT / "sotf-daw/target/release" / f"libplugins_nih{SUFFIX}"
    staged = OUTPUT / "sotf_convolution.clap"
    if not built.is_file() or not staged.is_file() or built.stat().st_size == 0:
        raise ValueError("Convolution cdylib or staged CLAP is missing or empty")
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (built, staged)]
    if digests[0] != digests[1] or built.stat().st_size != staged.stat().st_size:
        raise ValueError("staged CLAP differs from compiled Convolution cdylib")
    return {"built": str(built), "staged": str(staged), "bytes": staged.stat().st_size,
            "sha256": digests[0], "packaging": "flat NIH CLAP cdylib"}


def validator_evidence() -> dict[str, object]:
    folder = OUTPUT / "validators"
    binary_dir = (folder / "bin-path.txt").read_text().strip()
    if binary_dir != str(folder / "bin"):
        raise ValueError("validator binary path differs from job-local archive")
    binary = folder / "bin/clap-validator"
    if not binary.is_file() or binary.stat().st_size == 0:
        raise ValueError("pinned CLAP validator binary missing")
    rows = (folder / "provenance.tsv").read_text().splitlines()
    if len(rows) != 2 or {row.split("\t", 1)[0] for row in rows} != {"pluginval", "clap-validator"}:
        raise ValueError("validator download provenance inventory differs")
    return {"binary": str(binary), "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "provenance": rows}


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1":
        raise RuntimeError("requires disposable CI")
    if platform.system() == "Darwin" and os.environ.get("RELEASE_MAC_NONHARDWARE") != "1":
        raise RuntimeError("macOS nonhardware gate is required")
    if sys.flags.optimize or sys.dont_write_bytecode is False:
        raise RuntimeError("unoptimized Python with bytecode disabled required")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, owned.interrupted)
    signal.signal(signal.SIGINT, owned.interrupted)
    report = {"complete": False, "commands": [], "errors": [], "positive": []}
    owned.save(report)
    try:
        pins = read_manifest(ROOT / "scripts/release/sources.json")[2]
        before = owned.snapshot(pins)
        report["before"] = before
        owned.save(report)
        report["errors"].extend(owned.source_errors(before, before, pins))
        env = os.environ.copy()
        for home in ("CARGO_HOME", "RUSTUP_HOME"):
            if not env.get(home) or not Path(env[home]).is_absolute():
                report["errors"].append(f"original {home} must be absolute")
        env["SOTF_ARTIFACT_EVIDENCE_DIR"] = str(OUTPUT)
        private = OUTPUT / "private-home"
        private.mkdir(exist_ok=True)
        (private / ".cargo").mkdir(exist_ok=True)
        env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
                   XDG_CACHE_HOME=str(private / "cache"), XDG_DATA_HOME=str(private / "data"),
                   PULSE_SERVER=f"unix:{OUTPUT}/no-pulse", PIPEWIRE_REMOTE="no-pipewire",
                   JACK_NO_START_SERVER="1")
    except BaseException as exc:
        report["errors"].append(f"setup {type(exc).__name__}: {exc}")
        report["status"] = "FAIL"
        report["complete"] = True
        owned.save(report)
        return 1
    try:
        if report["errors"]:
            return 1
        owned.enable_subreaper()
        for name in (*NEW, *RESOURCE):
            full_name = ("params::convolution_no_ir_restore_tests::" if name in NEW else
                         "wrapper::process_tests::native_convolution_state_callbacks::") + name
            argv = ["bash", "-c", 'cd "$1" || exit 1; shift; exec "$@"', "convolution-test",
                    str(ROOT / "sotf-daw"), "cargo", "test", "--locked", "-p", "plugins-nih",
                    "--lib", "--no-default-features", "--features", "convolution", full_name,
                    "--", "--exact", "--show-output"]
            entry = owned.run_owned(name, argv, report, env)
            log = Path(entry["log"]).read_text(errors="replace")
            if entry["status"] != "PASS" or not rust_positive(log, full_name):
                report["errors"].append(f"missing positive exact Rust test: {name}")
            else:
                report["positive"].append(name)
            if owned.STOP or not entry["owned_group_cleanup"]["ok"]:
                break
        if not report["errors"] and not owned.STOP:
            build = owned.run_owned("convolution-clap-build", ["bash", "-c",
                'cd "$1" || exit 1; cargo build --release --locked -p plugins-nih --no-default-features --features convolution || exit 1; cp "target/release/libplugins_nih$2" "$3"',
                "convolution-build", str(ROOT / "sotf-daw"), SUFFIX,
                str(OUTPUT / "sotf_convolution.clap")], report, env)
            if build["status"] != "PASS":
                report["errors"].append("Convolution CLAP build failed")
            else:
                report["artifact"] = compiled_artifact_evidence()
        if not report["errors"] and not owned.STOP:
            fetch = owned.run_owned("validator-fetch", ["bash", f"scripts/release/{FETCH}"], report, env)
            if fetch["status"] != "PASS":
                report["errors"].append("pinned validator fetch failed")
            else:
                report["validator"] = validator_evidence()
                env["PATH"] = str(OUTPUT / "validators/bin") + ":" + env.get("PATH", "")
        if not report["errors"] and not owned.STOP:
            entry = owned.run_owned("strict-clap-convolution", ["clap-validator", "validate", str(OUTPUT / "sotf_convolution.clap")], report, env)
            log = Path(entry["log"]).read_text(errors="replace")
            if not clap_state_positives(log):
                report["errors"].append("strict CLAP state test inventory missing, failed, or duplicated")
            else:
                report["positive"].extend(STATE)
            if entry["status"] != "PASS":
                report["errors"].append("strict CLAP validator failed")
    except BaseException as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            report["after"] = owned.snapshot(pins)
            report["errors"].extend(owned.source_errors(before, report["after"], pins))
        except BaseException as exc:
            report["errors"].append(f"final source inspection {type(exc).__name__}: {exc}")
        if owned.STOP:
            report["errors"].append("interrupted")
        report["complete"] = True
        report["status"] = "PASS" if not report["errors"] and len(report["positive"]) == 9 else "FAIL"
        owned.save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
