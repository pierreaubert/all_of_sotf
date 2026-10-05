#!/usr/bin/env python3
"""Run the complete 43-plugin Linux artifact lane in owned Gitea processes."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.buildbot.ci_matrix import workspace_map
from scripts.release import qa
from scripts.release.checkout_sources import read_manifest, root_layout_status
from scripts.release.process_supervision import clean_group, enable_subreaper

OUTPUT = ROOT / "target/release-gitea/nih-native-linux"
STOP = False


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


def artifact_results(expected_features: list[str]) -> dict:
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
        binary = bundle / "Contents/x86_64-linux" / f"{bundle.stem}.so"
        if not binary.is_file() or binary.stat().st_size == 0:
            raise ValueError(f"VST3 bundle lacks its matching binary: {bundle}")
    for binary in clap:
        if binary.stat().st_size == 0:
            raise ValueError(f"CLAP binary is empty: {binary}")
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


def main() -> int:
    if os.environ.get("CI") != "true" or os.environ.get("DISPOSABLE") != "1" or not Path("/.dockerenv").exists():
        print("Disposable Gitea Linux container required", file=sys.stderr)
        return 2
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    enable_subreaper()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "logs").mkdir(exist_ok=False)
    _, _, pins = read_manifest(ROOT / "scripts/release/sources.json")
    report: dict = {"status": "RUNNING", "commands": [], "errors": []}
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
        report["inventory"] = artifact_results(expected_features)
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
