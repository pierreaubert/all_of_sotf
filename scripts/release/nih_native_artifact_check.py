#!/usr/bin/env python3
"""Run the complete 43-plugin Linux artifact lane in owned processes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import clean_group, enable_subreaper

OUTPUT = ROOT / "target/release-gitea/nih-native-linux"
STOP = False
LINUX_TRIPLETS = {"x86_64": "x86_64-linux", "aarch64": "aarch64-linux"}
ELF_MACHINES = {"x86_64-linux": 62, "aarch64-linux": 183}


def native_linux_triplet(expected: str | None = None, machine: str | None = None) -> str:
    machine = machine or platform.machine()
    architecture = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    triplet = LINUX_TRIPLETS.get(architecture)
    if triplet is None:
        raise ValueError(f"unsupported native Linux architecture: {machine}")
    expected = expected or os.environ.get("SOTF_LINUX_TARGET_TRIPLET") or triplet
    if expected not in ELF_MACHINES:
        raise ValueError(f"unsupported expected Linux target triplet: {expected}")
    if expected != triplet:
        raise ValueError(f"native host {triplet} does not match expected target triplet {expected}")
    return triplet


def execution_preflight(local_mode: bool, *, system: str | None = None,
                        disposable: str | None = None, docker_marker: bool | None = None,
                        ci: str | None = None, expected_triplet: str | None = None,
                        machine: str | None = None) -> str:
    system = system if system is not None else platform.system()
    disposable = disposable if disposable is not None else os.environ.get("DISPOSABLE")
    docker_marker = docker_marker if docker_marker is not None else Path("/.dockerenv").exists()
    ci = ci if ci is not None else os.environ.get("CI")
    if system != "Linux":
        raise ValueError("native Linux container required")
    if disposable != "1" or not docker_marker:
        raise ValueError("DISPOSABLE=1 and /.dockerenv are required")
    if not local_mode and ci != "true":
        raise ValueError("legacy Gitea mode requires CI=true")
    return native_linux_triplet(expected_triplet, machine)


def local_output_path(evidence_dir: Path | None, evidence_root: Path | None,
                      *, timestamp: str | None = None) -> Path:
    if (evidence_dir is None) == (evidence_root is None):
        raise ValueError("local mode requires exactly one of --evidence-dir or --evidence-root")
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    if evidence_dir is not None:
        if not evidence_dir.is_absolute():
            raise ValueError("--evidence-dir must be an absolute path")
        output = evidence_dir.expanduser().resolve()
    else:
        if not evidence_root.is_absolute():
            raise ValueError("--evidence-root must be an absolute path")
        root = evidence_root.expanduser().resolve()
        output = root / f"nih-native-linux-{timestamp}"
    root_resolved = ROOT.resolve()
    if output == root_resolved or root_resolved in output.parents:
        raise ValueError("local evidence must be outside the source checkout")
    output.mkdir(parents=True, exist_ok=False)
    return output


def assert_elf_architecture(path: Path, expected_triplet: str) -> None:
    try:
        with path.open("rb") as stream:
            header = stream.read(20)
    except OSError as error:
        raise ValueError(f"cannot read imported plugin binary {path}: {error}") from error
    if len(header) < 20 or header[:4] != b"\x7fELF" or header[4] != 2 or header[5] not in (1, 2):
        raise ValueError(f"imported plugin is not a valid 64-bit ELF binary: {path}")
    byte_order = "little" if header[5] == 1 else "big"
    machine = int.from_bytes(header[18:20], byte_order)
    expected_machine = ELF_MACHINES[expected_triplet]
    if machine != expected_machine:
        actual = next((name for name, value in ELF_MACHINES.items() if value == machine), f"e_machine={machine}")
        raise ValueError(f"imported plugin architecture {actual} does not match {expected_triplet}: {path}")


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def save(report: dict) -> None:
    path = OUTPUT / "report.json"
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n")
    pending.replace(path)


def snapshot(pins: dict[str, str]) -> dict:
    return {
        "root_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "manifest_sha256": hashlib.sha256((ROOT / "scripts/release/sources.json").read_bytes()).hexdigest(),
        "root_layout": root_layout_status(ROOT, pins),
        "workspaces": qa.source_state(ROOT, list(workspace_map()), "linux"),
    }


def source_errors(before: dict, after: dict, pins: dict[str, str]) -> list[str]:
    errors = qa.source_issues(before["workspaces"], after["workspaces"], True)
    if before["root_revision"] != after["root_revision"]:
        errors.append("root revision changed")
    if before["manifest_sha256"] != after["manifest_sha256"]:
        errors.append("sources.json changed")
    if before["root_layout"] != after["root_layout"]:
        errors.append("root checkout layout changed")
    for label, state in (("before", before), ("after", after)):
        layout = state["root_layout"]
        if layout["missing"] or layout["unexpected"] or layout["allowed_siblings"]:
            errors.append(f"{label}: root layout differs from pinned gitlinks: {layout}")
        if set(layout["tracked_gitlinks"]) != set(pins):
            errors.append(f"{label}: nine pinned gitlinks are incomplete")
        for name, revision in pins.items():
            source = state["workspaces"].get(name, {})
            if source.get("revision") != revision:
                errors.append(f"{label}: {name} differs from pinned source revision")
            if not source.get("lock_sha256"):
                errors.append(f"{label}: {name} canonical Cargo.lock hash is missing")
            if name == "autoeq" and not source.get("nested_lock_sha256"):
                errors.append(f"{label}: AutoEQ nested demo Cargo.lock hash is missing")
    return errors


def run_owned(name: str, argv: list[str], report: dict, env: dict[str, str]) -> dict:
    if STOP:
        raise KeyboardInterrupt("stopped before launch")
    log = OUTPUT / "logs" / f"{name}.log"
    entry: dict = {"name": name, "argv": argv, "log": str(log), "status": "RUNNING"}
    report["active_command"] = entry
    save(report)
    with log.open("w") as stream:
        if STOP:
            raise KeyboardInterrupt("stopped before process launch")
        child = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        status = 130
        try:
            entry["owned_pgid"] = child.pid
            save(report)
            heartbeat = time.monotonic()
            while not STOP:
                try:
                    status = child.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() - heartbeat >= 30:
                        print(f"[{name}] still running", flush=True)
                        heartbeat = time.monotonic()
        finally:
            entry["owned_group_cleanup"] = clean_group(child)
    entry["exit_code"] = status
    entry["status"] = "PASS" if status == 0 and not STOP and entry["owned_group_cleanup"]["ok"] else "FAIL"
    report["commands"].append(entry)
    report.pop("active_command", None)
    save(report)
    return entry


def features() -> list[str]:
    manifest = ROOT / "sotf-daw/crates/sotf-plugins/crates/plugins-nih/Justfile"
    matches = re.findall(r'^NIH_FEATURES := "([^"]+)"$', manifest.read_text(), re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("NIH feature inventory is missing or ambiguous")
    names = matches[0].split()
    if len(names) != 43 or len(set(names)) != 43:
        raise ValueError(f"expected 43 distinct NIH features, found {len(names)}")
    return names


def vst3_name(feature: str) -> str:
    # Match the Linux Justfile's sotf_ prefix, underscore-to-space conversion,
    # and uppercase-first-letter substitution without changing acronym tails.
    words = feature.replace("-", " ").split()
    return "SOTF " + " ".join(word[0].upper() + word[1:] for word in words)


def validator_results(kind: str, staged_names: set[str]) -> dict:
    folder = OUTPUT / "logs" / f"{kind}-validators"
    with (folder / "results.tsv").open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    names = {row["plugin"] for row in rows}
    if len(rows) != 43 or names != staged_names or any(row["exit_code"] != "0" for row in rows):
        raise ValueError(f"{kind}: incomplete or failing 43-plugin validator inventory")
    for row in rows:
        log = Path(row["log"])
        if log.parent != folder or not log.is_file() or log.stat().st_size == 0:
            raise ValueError(f"{kind}: missing validator transcript for {row['plugin']}")
    transcript = (OUTPUT / "logs" / f"{kind}-validate.log").read_text(errors="replace")
    if f"{kind} validation: 43 passed, 0 failed of 43" not in transcript:
        raise ValueError(f"{kind}: full validator summary is missing")
    return {"count": len(rows), "names": sorted(names)}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_results(expected_features: list[str], expected_triplet: str | None = None) -> dict:
    expected_triplet = native_linux_triplet(expected_triplet)
    build_log = (OUTPUT / "logs/plugin-formats-build.log").read_text(errors="replace")
    if "Built 43/43 plugins in dist/nih-linux/ (0 failed)" not in build_log:
        raise ValueError("complete 43-feature NIH build summary is missing")
    feature_logs = OUTPUT / "logs/nih-features"
    if {path.stem for path in feature_logs.glob("*.log")} != set(expected_features):
        raise ValueError("NIH build logs differ from the declared 43 features")
    if any(not (feature_logs / f"{name}.log").is_file() or
           (feature_logs / f"{name}.log").stat().st_size == 0 for name in expected_features):
        raise ValueError("one or more NIH feature build transcripts are empty")
    staged = OUTPUT / "artifacts/sotf-daw/dist"
    clap = list((staged / "clap-linux").glob("*.clap"))
    vst3 = list((staged / "vst3-linux").glob("*.vst3"))
    expected_clap = {"sotf_" + name.replace("-", "_") for name in expected_features}
    if len(clap) != 43 or {path.stem for path in clap} != expected_clap or len(vst3) != 43:
        raise ValueError("staged CLAP/VST3 artifacts do not cover all 43 NIH features")
    vst3_names = {path.stem for path in vst3}
    expected_vst3 = {vst3_name(name) for name in expected_features}
    if vst3_names != expected_vst3 or len(expected_vst3) != 43:
        raise ValueError("staged VST3 bundle names differ from the exact NIH feature mapping")
    for bundle in vst3:
        binary = bundle / "Contents" / expected_triplet / f"{bundle.stem}.so"
        if not binary.is_file() or binary.stat().st_size == 0:
            raise ValueError(f"VST3 bundle lacks its matching binary: {bundle}")
        assert_elf_architecture(binary, expected_triplet)
    for binary in clap:
        if binary.stat().st_size == 0:
            raise ValueError(f"CLAP binary is empty: {binary}")
        assert_elf_architecture(binary, expected_triplet)
    inventory = json.loads((OUTPUT / "artifact-inventory.json").read_text())
    files = sorted(path for path in (OUTPUT / "artifacts").rglob("*") if path.is_file())
    recorded = {row["path"]: row for row in inventory}
    physical = {str(path.relative_to(OUTPUT)) for path in files}
    if set(recorded) != physical:
        raise ValueError("artifact hash inventory does not match staged files")
    for path in files:
        row = recorded[str(path.relative_to(OUTPUT))]
        if row["size"] != path.stat().st_size or row["size"] == 0 or row["sha256"] != file_sha256(path):
            raise ValueError(f"artifact size or SHA256 differs: {path}")
    return {
        "features": expected_features,
        "clap": validator_results("clap", {path.stem for path in clap}),
        "vst3": validator_results("vst3", vst3_names),
        "files_hashed": len(files),
    }


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the native Linux 43-plugin artifact lane")
    parser.add_argument("--local", action="store_true",
                        help="run in a disposable native Linux container without claiming Gitea CI")
    parser.add_argument("--evidence-dir", type=Path,
                        help="create fresh evidence at this absolute path (local mode only)")
    parser.add_argument("--evidence-root", type=Path,
                        help="create fresh timestamped evidence below this root (local mode only)")
    return parser


def main(argv: list[str] | None = None) -> int:
    global OUTPUT
    args = argument_parser().parse_args(argv)
    if not args.local and (args.evidence_dir is not None or args.evidence_root is not None):
        print("--evidence-dir and --evidence-root require --local", file=sys.stderr)
        return 2
    try:
        expected_triplet = execution_preflight(args.local)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.local:
        try:
            OUTPUT = local_output_path(args.evidence_dir, args.evidence_root)
        except (OSError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    enable_subreaper()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=False)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {"status": "RUNNING", "run_mode": "local" if args.local else "gitea",
                    "target_triplet": expected_triplet, "commands": [], "errors": []}
    before: dict | None = None
    try:
        before = snapshot(pins)
        report["before"] = before
        save(report)
        report["errors"].extend(source_errors(before, before, pins))
        if report["errors"]:
            return 1
        expected_features = features()
        env = os.environ.copy()
        env["SOTF_LINUX_TARGET_TRIPLET"] = expected_triplet
        env["SOTF_ARTIFACT_EVIDENCE_DIR"] = str(OUTPUT)
        private = OUTPUT / "private-home"
        private.mkdir()
        env.update(HOME=str(private), XDG_CONFIG_HOME=str(private / "config"),
                   XDG_CACHE_HOME=str(private / "cache"), XDG_DATA_HOME=str(private / "data"),
                   PULSE_SERVER=f"unix:{OUTPUT}/no-pulse", PIPEWIRE_REMOTE="no-pipewire",
                   JACK_NO_START_SERVER="1")
        fetch = run_owned("validators-fetch", ["bash", "scripts/release/fetch_linux_plugin_validators.sh"], report, env)
        if fetch["status"] != "PASS":
            report["errors"].append("pinned plugin validator fetch failed")
            return 1
        bin_path = (OUTPUT / "validators/bin-path.txt").read_text().strip()
        if bin_path != str(OUTPUT / "validators/bin"):
            raise ValueError("validator executable path differs from job-local evidence")
        env["PATH"] = f"{bin_path}:/usr/libexec:{env.get('PATH', '')}"
        build = run_owned("plugin-artifact", ["dbus-run-session", "--", "xvfb-run", "-a", "-s",
                                               "-screen 0 1440x900x24 +extension RANDR +extension XTEST",
                                               "bash", "scripts/release/artifact_check.sh", "plugins", "linux"], report, env)
        if build["status"] != "PASS":
            report["errors"].append("43-plugin build or validator command failed")
            return 1
        report["inventory"] = artifact_results(expected_features, expected_triplet)
    except KeyboardInterrupt:
        report["errors"].append("interrupted")
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        if STOP:
            report["errors"].append("interrupted")
        try:
            after = snapshot(pins)
            report["after"] = after
            if before is not None:
                report["errors"].extend(source_errors(before, after, pins))
        except Exception as error:
            report["errors"].append(f"after snapshot failed: {type(error).__name__}: {error}")
        report["status"] = "PASS" if not report["errors"] and len(report["commands"]) == 2 else "FAIL"
        save(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
