#!/usr/bin/env python3
"""Run native CLAP and VST3 validators over one fresh macOS NIH pack receipt.

This validates already-packaged artifacts only. It does not build, package,
install, sign, publish, or launch a host for the plugins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.release import package_nih_artifacts as packer
from scripts.release.process_supervision import clean_group, enable_subreaper

SCHEMA = 1
DEFAULT_CLAP_VALIDATOR = Path("/Users/pierre/.local/bin/clap-validator")
DEFAULT_PLUGINVAL = Path("/Applications/pluginval.app/Contents/MacOS/pluginval")
DEFAULT_TIMEOUT_SECONDS = 60
MAX_TIMEOUT_SECONDS = 900
STOP = False


def interrupted(_signum: int, _frame: object) -> None:
    global STOP
    STOP = True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_sha256(path: Path) -> str | None:
    try:
        return sha256(path)
    except OSError:
        return None


def _within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _check_external_output(output_dir: Path, input_root: Path) -> Path:
    raw = output_dir.expanduser()
    if not raw.is_absolute():
        raise ValueError("--evidence-dir must be absolute")
    packer._no_symlink_components(raw)
    if not raw.parent.is_dir():
        raise ValueError("--evidence-dir parent must already exist")
    candidate = raw.parent.resolve(strict=True) / raw.name
    source_root = ROOT.resolve(strict=True)
    input_root = input_root.resolve(strict=True)
    if _within(candidate, source_root):
        raise ValueError("validator evidence must be outside the source checkout")
    if _within(candidate, input_root) or _within(input_root, candidate):
        raise ValueError("validator evidence and packed input tree must be separate")
    if candidate.exists():
        raise ValueError("--evidence-dir must name a fresh directory")
    return candidate


def _validate_package(
    receipt_path: Path,
    *,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Revalidate the pack receipt and the underlying locked build proof."""
    raw = receipt_path.expanduser()
    if not raw.is_absolute():
        raise ValueError("--input-receipt must be absolute")
    packer._no_symlink_components(raw)
    if not raw.is_file():
        raise ValueError("pack receipt must be a regular file")
    receipt_bytes = raw.read_bytes()
    receipt_hash = hashlib.sha256(receipt_bytes).hexdigest()
    try:
        receipt = json.loads(receipt_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"pack receipt is not valid JSON: {error}") from error
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        raise ValueError("unsupported NIH pack receipt schema")
    if (receipt.get("status") != "PACKAGED" or receipt.get("target") != "macos-arm64"
            or receipt.get("target_triple") != "aarch64-apple-darwin"
            or receipt.get("profile") != "dist"):
        raise ValueError("input is not a packaged macOS ARM64 dist-profile receipt")
    qualification = receipt.get("qualification")
    if (not isinstance(qualification, dict)
            or qualification.get("native_validators") != "pending"
            or qualification.get("host_loading") != "pending"
            or qualification.get("release_qualification") != "pending"):
        raise ValueError("pack receipt qualification fields must remain pending")

    build_proof = receipt.get("input_receipt")
    if not isinstance(build_proof, dict):
        raise ValueError("pack receipt is missing its build-only input proof")
    build_receipt_value = build_proof.get("path")
    recorded_build_hash = build_proof.get("sha256")
    if (not isinstance(build_receipt_value, str) or not Path(build_receipt_value).is_absolute()
            or not isinstance(recorded_build_hash, str)
            or len(recorded_build_hash) != 64):
        raise ValueError("pack receipt build-only input path/hash is invalid")
    build_receipt_path = Path(build_receipt_value)
    packer._no_symlink_components(build_receipt_path)
    if not build_receipt_path.is_file() or sha256(build_receipt_path) != recorded_build_hash:
        raise ValueError("underlying build receipt is missing or has changed")

    build_report, built_features, actual_build_hash = packer._validate_build_receipt(
        build_receipt_path, "macos-arm64", current=current
    )
    if actual_build_hash != recorded_build_hash:
        raise ValueError("pack receipt build proof differs from validated build receipt")
    package_root = raw.parent
    if package_root.resolve(strict=True) == ROOT.resolve(strict=True):
        raise ValueError("packaged input tree cannot be the source checkout")
    if _within(package_root.resolve(strict=True), ROOT.resolve(strict=True)):
        raise ValueError("packaged input tree must be outside the source checkout")

    features = list(packer.NIH_FEATURES)
    if [item.get("name") for item in receipt.get("features", [])] != features:
        raise ValueError("pack receipt feature inventory differs from the canonical 43 NIH features")
    if len(built_features) != len(features):
        raise ValueError("underlying build proof does not validate all 43 NIH features")
    built_by_feature = {item["feature"]: item for item in built_features}
    recorded_features = {item["name"]: item for item in receipt["features"]}
    for feature in features:
        built = built_by_feature.get(feature)
        packaged = recorded_features[feature]
        if (built is None or packaged.get("input_sha256") != built["sha256"]
                or packaged.get("input_size") != built["size"]
                or Path(str(packaged.get("input", ""))).absolute() != built["input"].absolute()):
            raise ValueError(f"pack receipt feature provenance differs for {feature}")

    artifact_root = package_root / "artifacts"
    if artifact_root.is_symlink() or not artifact_root.is_dir():
        raise ValueError("packed artifact tree is missing or is a symlink")
    physical_files: dict[str, Path] = {}
    for path in artifact_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink found in packed artifact tree: {path}")
        if path.is_file():
            physical_files[str(path.relative_to(package_root))] = path
    inventory = receipt.get("artifact_inventory")
    if not isinstance(inventory, list) or len(inventory) != 129:
        raise ValueError("pack receipt must inventory exactly 129 artifact files")
    recorded: dict[str, dict[str, Any]] = {}
    for row in inventory:
        if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
                or row["path"] in recorded):
            raise ValueError("pack receipt artifact inventory has an invalid or duplicate path")
        recorded[row["path"]] = row
    if set(recorded) != set(physical_files):
        raise ValueError("physical packed files do not match the 129-file receipt inventory")

    expected_paths = set()
    for feature in features:
        base = packer.feature_base(feature)
        display = packer.vst3_name(feature)
        expected_paths.update({
            f"artifacts/sotf-daw/dist/clap/{base}.clap",
            f"artifacts/sotf-daw/dist/vst3/{display}.vst3/Contents/MacOS/{base}",
            f"artifacts/sotf-daw/dist/vst3/{display}.vst3/Contents/Info.plist",
        })
    if set(physical_files) != expected_paths:
        raise ValueError("packed artifact paths do not match the exact 43 CLAP/VST3 bundle layout")

    per_feature_paths: dict[str, dict[str, Path]] = {}
    for feature in features:
        base = packer.feature_base(feature)
        display = packer.vst3_name(feature)
        clap = package_root / "artifacts/sotf-daw/dist/clap" / f"{base}.clap"
        bundle = package_root / "artifacts/sotf-daw/dist/vst3" / f"{display}.vst3"
        vst3 = bundle / "Contents/MacOS" / base
        plist_path = bundle / "Contents/Info.plist"
        for artifact in (clap, vst3, plist_path):
            packer._no_symlink_components(artifact, beneath=package_root)
            if not artifact.is_file() or artifact.stat().st_size == 0:
                raise ValueError(f"packed artifact is missing or empty: {artifact}")
        packer.assert_macho_arm64(clap)
        packer.assert_macho_arm64(vst3)
        clap_hash = sha256(clap)
        vst3_hash = sha256(vst3)
        if clap_hash != vst3_hash or clap_hash != built_by_feature[feature]["sha256"]:
            raise ValueError(f"CLAP/VST3 payload does not match its raw build artifact for {feature}")
        plist = plistlib.loads(plist_path.read_bytes())
        if (plist.get("CFBundleExecutable") != base
                or plist.get("CFBundleIdentifier") != f"org.spinorama.sotf.{base}.vst3"
                or plist.get("CFBundlePackageType") != "BNDL"):
            raise ValueError(f"VST3 bundle metadata differs for {feature}")
        per_feature_paths[feature] = {
            "clap": clap,
            "vst3_bundle": bundle,
            "vst3_binary": vst3,
            "payload_sha256": built_by_feature[feature]["sha256"],
        }

    if len(physical_files) != 129:
        raise ValueError(f"expected 129 physical packed files, found {len(physical_files)}")
    for relative, path in physical_files.items():
        row = recorded[relative]
        if (row.get("size") != path.stat().st_size or path.stat().st_size == 0
                or row.get("sha256") != sha256(path)):
            raise ValueError(f"packed artifact hash/size differs from receipt: {relative}")

    source_snapshot = receipt.get("source_snapshot")
    before = build_report.get("sources_before", {})
    _server, _owner, pins = packer.read_manifest(ROOT / "scripts/release/sources.json")
    if (not isinstance(source_snapshot, dict)
            or source_snapshot.get("root_revision") != before.get("root_revision")
            or source_snapshot.get("sources_manifest_sha256") != before.get("sources_manifest_sha256")
            or source_snapshot.get("pins") != pins):
        raise ValueError("pack receipt source pin snapshot differs from its validated build proof")
    return {
        "package_root": package_root.resolve(strict=True),
        "package_receipt_path": raw,
        "package_receipt_sha256": receipt_hash,
        "build_receipt_path": build_receipt_path,
        "build_receipt_sha256": actual_build_hash,
        "build_report": build_report,
        "features": features,
        "files": physical_files,
        "inventory": recorded,
        "per_feature_paths": per_feature_paths,
    }


def _run_preflight_owned(
    name: str, argv: list[str], output: Path, env: dict[str, str],
    report: dict[str, Any], timeout_seconds: int = 15,
) -> tuple[dict[str, Any], str]:
    if STOP:
        raise KeyboardInterrupt("stopped before validator identity probe")
    log = output / "preflight" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "name": name, "argv": argv, "log": str(log),
        "timeout_seconds": timeout_seconds, "status": "RUNNING",
    }
    with log.open("wb") as stream:
        report.setdefault("preflight_commands", []).append(entry)
        report["active_command"] = entry
        _save(output, report)
        if STOP:
            report.pop("active_command", None)
            entry.update(status="FAIL", stopped=True)
            _save(output, report)
            raise KeyboardInterrupt("stopped before validator identity process launch")
        try:
            child = subprocess.Popen(
                argv, cwd=output, env=env, stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            entry.update(status="FAIL", launch_error=f"{type(error).__name__}: {error}")
            report.pop("active_command", None)
            _save(output, report)
            raise
        entry["owned_pgid"] = child.pid
        _save(output, report)
        deadline = time.monotonic() + timeout_seconds
        timed_out = False
        status = 130
        wait_error: BaseException | None = None
        cleanup_error: BaseException | None = None
        try:
            while not STOP:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    status = child.wait(timeout=min(1.0, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException as error:
            wait_error = error
        finally:
            try:
                entry["owned_group_cleanup"] = clean_group(child)
            except BaseException as error:
                cleanup_error = error
                entry["owned_group_cleanup"] = {
                    "ok": False, "remaining": [],
                    "errors": [f"clean_group raised {type(error).__name__}: {error}"],
                }
    output_error: BaseException | None = None
    try:
        output_text = log.read_text(encoding="utf-8", errors="replace")
        output_hash = sha256(log)
    except BaseException as error:
        output_error = error
        output_text = ""
        output_hash = None
    supervision_errors = []
    if wait_error is not None:
        supervision_errors.append(f"wait raised {type(wait_error).__name__}: {wait_error}")
    if cleanup_error is not None:
        supervision_errors.append(
            f"clean_group raised {type(cleanup_error).__name__}: {cleanup_error}"
        )
    if output_error is not None:
        supervision_errors.append(
            f"log read/hash raised {type(output_error).__name__}: {output_error}"
        )
    entry.update({
        "exit_code": child.returncode if child.returncode is not None else status,
        "timed_out": timed_out,
        "stopped": STOP,
        "output_sha256": output_hash,
        "supervision_errors": supervision_errors,
        "status": "PASS" if (child.returncode == 0 and not timed_out and not STOP
                              and entry["owned_group_cleanup"].get("ok") is True
                              and not supervision_errors) else "FAIL",
    })
    report.pop("active_command", None)
    _save(output, report)
    if wait_error is not None:
        raise wait_error
    if cleanup_error is not None:
        raise cleanup_error
    if output_error is not None:
        raise output_error
    return entry, output_text


def _validator_identity(
    path: Path, name: str, output: Path, env: dict[str, str], report: dict[str, Any],
) -> dict[str, Any]:
    raw = path.expanduser()
    if not raw.is_absolute():
        raise ValueError(f"{name} path must be absolute")
    packer._no_symlink_components(raw)
    if not raw.is_file() or not os.access(raw, os.X_OK):
        raise ValueError(f"{name} executable is missing or not executable: {raw}")
    lipo_result = subprocess.run(
        ["lipo", "-verify_arch", "arm64", str(raw)],
        capture_output=True, text=True, timeout=10,
    )
    if lipo_result.returncode != 0:
        raise ValueError(f"{name} executable lacks an ARM64 slice: {lipo_result.stderr.strip()}")
    expected = {
        "clap-validator": ("--version", "clap-validator 0.3.2"),
        "pluginval": ("--version", "pluginval - 1.0.4"),
    }[name]
    probes = []
    for suffix in (expected[0], "--help"):
        argv = [str(raw), suffix]
        probe_name = f"{name}-{suffix.lstrip('-')}"
        result, body = _run_preflight_owned(probe_name, argv, output, env, report)
        probe_path = Path(result["log"])
        probes.append({
            "argv": argv,
            "exit_code": result["exit_code"],
            "owned_group_cleanup": result["owned_group_cleanup"],
            "timed_out": result["timed_out"],
            "output": str(probe_path),
            "output_sha256": sha256(probe_path),
        })
        if result["status"] != "PASS":
            raise ValueError(f"{name} preflight {suffix} did not complete cleanly")
        if suffix == expected[0] and expected[1] not in body:
            raise ValueError(f"{name} version differs from the reviewed native validator")
    help_text = (output / "preflight" / f"{name}-help.log").read_text(encoding="utf-8")
    required = ("validate", "--help") if name == "clap-validator" else (
        "--validate", "--strictness-level", "--timeout-ms", "--output-dir"
    )
    if any(token not in help_text for token in required):
        raise ValueError(f"{name} CLI help does not prove the expected validation interface")
    return {
        "path": str(raw),
        "sha256": sha256(raw),
        "architecture_check": {
            "argv": ["lipo", "-verify_arch", "arm64", str(raw)],
            "exit_code": lipo_result.returncode,
            "stdout": lipo_result.stdout.strip(),
            "stderr": lipo_result.stderr.strip(),
        },
        "probes": probes,
    }


def _validator_commands(
    features: list[str], per_feature_paths: dict[str, dict[str, Path]], evidence: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    commands = []
    for feature in features:
        paths = per_feature_paths[feature]
        base = packer.feature_base(feature)
        display = packer.vst3_name(feature)
        commands.append({
            "feature": feature,
            "format": "clap",
            "path": paths["clap"],
            "hash_path": paths["clap"],
            "expected_sha256": paths["payload_sha256"],
            "argv_kind": "clap-validator",
            "argv_suffix": ["validate", str(paths["clap"])],
            "timeout_seconds": timeout_seconds,
            "log": evidence / "logs/clap" / f"{base}.log",
        })
        output_dir = evidence / "logs/pluginval-output" / feature
        commands.append({
            "feature": feature,
            "format": "vst3",
            "path": paths["vst3_bundle"],
            "hash_path": paths["vst3_binary"],
            "expected_sha256": paths["payload_sha256"],
            "argv_kind": "pluginval",
            "argv_suffix": [
                "--validate", str(paths["vst3_bundle"]), "--strictness-level", "5",
                "--timeout-ms", "30000", "--output-dir", str(output_dir),
            ],
            "timeout_seconds": timeout_seconds,
            "log": evidence / "logs/vst3" / f"{display}.log",
            "pluginval_output_dir": output_dir,
        })
    return commands


def _save(output: Path, report: dict[str, Any]) -> None:
    path = output / "validation-report.json"
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def _run_owned(
    command: dict[str, Any], executable: Path, env: dict[str, str],
    expected_executable_sha256: str, report: dict[str, Any], output: Path,
) -> dict[str, Any]:
    if STOP:
        entry = {
            "feature": command["feature"],
            "format": command["format"],
            "artifact": str(command["path"]),
            "artifact_sha256_before": None,
            "argv": [str(executable), *command["argv_suffix"]],
            "log": str(command["log"]),
            "timeout_seconds": command["timeout_seconds"],
            "status": "FAIL",
            "stopped": True,
            "launch_error": "stopped before validator launch",
        }
        report.pop("active_command", None)
        report["commands"].append(entry)
        _save(output, report)
        raise KeyboardInterrupt("stopped before validator launch")
    feature = str(command["feature"])
    kind = str(command["format"])
    validator_input = Path(command["path"])
    artifact = Path(command["hash_path"])
    packer._no_symlink_components(validator_input)
    packer._no_symlink_components(artifact)
    if not validator_input.exists() or (kind == "vst3" and not validator_input.is_dir()):
        raise ValueError(f"validator input is missing or has the wrong type: {validator_input}")
    digest_before = sha256(artifact)
    if digest_before != command["expected_sha256"]:
        raise ValueError(f"plugin payload changed before validation: {feature} ({kind})")
    executable_hash_before = sha256(executable)
    if executable_hash_before != expected_executable_sha256:
        raise ValueError(f"{command['argv_kind']} executable changed before launch")
    argv = [str(executable), *command["argv_suffix"]]
    entry: dict[str, Any] = {
        "feature": feature,
        "format": kind,
        "artifact": str(artifact),
        "validator_input": str(validator_input),
        "artifact_sha256_before": digest_before,
        "validator_executable_sha256_before": executable_hash_before,
        "argv": argv,
        "log": str(command["log"]),
        "timeout_seconds": command["timeout_seconds"],
        "status": "RUNNING",
    }
    Path(entry["log"]).parent.mkdir(parents=True, exist_ok=True)
    if kind == "vst3":
        Path(command["pluginval_output_dir"]).mkdir(parents=True, exist_ok=True)
    with Path(entry["log"]).open("wb") as stream:
        report["active_command"] = entry
        _save(output, report)
        if STOP:
            report.pop("active_command", None)
            entry.update(status="FAIL", stopped=True,
                         launch_error="stopped before validator process launch")
            report["commands"].append(entry)
            _save(output, report)
            raise KeyboardInterrupt("stopped before validator process launch")
        try:
            child = subprocess.Popen(
                argv, cwd=output, env=env, stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            after_hash = _safe_sha256(artifact)
            entry.update(
                status="FAIL", launch_error=f"{type(error).__name__}: {error}",
                artifact_sha256_after=after_hash,
                artifact_unchanged=digest_before == after_hash,
                validator_executable_sha256_after=_safe_sha256(executable),
            )
            report["commands"].append(entry)
            report.pop("active_command", None)
            _save(output, report)
            return entry
        entry["owned_pgid"] = child.pid
        _save(output, report)
        deadline = time.monotonic() + float(command["timeout_seconds"])
        timed_out = False
        status = 130
        wait_error: BaseException | None = None
        cleanup_error: BaseException | None = None
        try:
            while not STOP:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    status = child.wait(timeout=min(1.0, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException as error:
            wait_error = error
        finally:
            try:
                entry["owned_group_cleanup"] = clean_group(child)
            except BaseException as error:
                cleanup_error = error
                entry["owned_group_cleanup"] = {
                    "ok": False, "remaining": [],
                    "errors": [f"clean_group raised {type(error).__name__}: {error}"],
                }
    after_hash = _safe_sha256(artifact)
    executable_hash_after = _safe_sha256(executable)
    supervision_errors = []
    if wait_error is not None:
        supervision_errors.append(f"wait raised {type(wait_error).__name__}: {wait_error}")
    if cleanup_error is not None:
        supervision_errors.append(
            f"clean_group raised {type(cleanup_error).__name__}: {cleanup_error}"
        )
    entry.update({
        "exit_code": child.returncode if child.returncode is not None else status,
        "timed_out": timed_out,
        "stopped": STOP,
        "artifact_sha256_after": after_hash,
        "artifact_unchanged": digest_before == after_hash,
        "validator_executable_sha256_after": executable_hash_after,
        "validator_executable_unchanged": executable_hash_before == executable_hash_after,
        "supervision_errors": supervision_errors,
    })
    cleanup = entry["owned_group_cleanup"]
    entry["status"] = (
        "PASS" if entry["exit_code"] == 0 and not timed_out and not STOP
        and cleanup.get("ok") is True and digest_before == after_hash
        and executable_hash_before == executable_hash_after
        and not supervision_errors else "FAIL"
    )
    report["commands"].append(entry)
    report.pop("active_command", None)
    _save(output, report)
    if wait_error is not None:
        raise wait_error
    if cleanup_error is not None:
        raise cleanup_error
    return entry


def _final_package_check(
    validated: dict[str, Any],
) -> tuple[list[str], dict[str, Any] | None, dict[str, Any]]:
    errors = []
    inventory_after = []
    expected_paths = set(validated["files"])
    try:
        artifact_root = validated["package_root"] / "artifacts"
        for path in artifact_root.rglob("*"):
            if path.is_symlink():
                errors.append(f"symlink appeared in packed input during validation: {path}")
            elif path.is_file():
                relative = str(path.relative_to(validated["package_root"]))
                if relative not in expected_paths:
                    errors.append(f"unexpected packed input appeared during validation: {relative}")
    except OSError as error:
        errors.append(f"packed artifact inventory could not be rescanned: {error}")
    for relative, path in validated["files"].items():
        row = validated["inventory"][relative]
        try:
            current_size = path.stat().st_size
            current_hash = sha256(path)
        except OSError as error:
            current_size = None
            current_hash = None
            errors.append(f"packed input disappeared during native validation: {relative}: {error}")
        inventory_after.append({"path": relative, "size": current_size, "sha256": current_hash})
        if current_size != row["size"] or current_hash != row["sha256"]:
            errors.append(f"packed input changed during native validation: {relative}")
    final_hashes: dict[str, Any] = {"artifacts": inventory_after}
    for label, path, expected_hash in (
        ("package_receipt", validated["package_receipt_path"], validated["package_receipt_sha256"]),
        ("build_receipt", validated["build_receipt_path"], validated["build_receipt_sha256"]),
    ):
        try:
            packer._no_symlink_components(path)
            actual_hash = sha256(path)
        except (OSError, ValueError) as error:
            actual_hash = None
            errors.append(f"{label.replace('_', ' ')} changed during native validation: {error}")
        final_hashes[f"{label}_sha256"] = actual_hash
        if actual_hash != expected_hash:
            errors.append(f"{label.replace('_', ' ')} changed during native validation")
    current = None
    try:
        current = packer._current_provenance(ROOT, "macos-arm64")
        _, _, build_hash = packer._validate_build_receipt(
            validated["build_receipt_path"], "macos-arm64", current=current
        )
        if build_hash != validated["build_receipt_sha256"]:
            errors.append("underlying build proof no longer validates unchanged")
    except Exception as error:
        errors.append(f"underlying build proof changed or is stale: {error}")
    return errors, current, final_hashes


def _final_validator_check(report: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors = []
    hashes = {}
    for name, validator in report.get("validators", {}).items():
        path = Path(validator["path"])
        try:
            current_hash = sha256(path)
        except OSError as error:
            current_hash = None
            errors.append(f"{name} disappeared during validation: {error}")
        hashes[name] = current_hash
        if current_hash != validator.get("sha256"):
            errors.append(f"{name} executable changed during validation")
    return errors, hashes


def _format_result(commands: list[dict[str, Any]], kind: str) -> dict[str, int]:
    rows = [row for row in commands if row.get("format") == kind]
    return {
        "passed": sum(row.get("status") == "PASS" for row in rows),
        "failed": sum(row.get("status") == "FAIL" for row in rows),
        "not_run": 43 - len(rows),
        "expected": 43,
    }


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-receipt", type=Path, required=True,
                        help="absolute package-nih-report.json produced by package_nih_artifacts.py")
    parser.add_argument("--evidence-dir", type=Path, required=True,
                        help="fresh absolute external directory for validator reports and logs")
    parser.add_argument("--clap-validator", type=Path, default=DEFAULT_CLAP_VALIDATOR)
    parser.add_argument("--pluginval", type=Path, default=DEFAULT_PLUGINVAL)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help="outer per-plugin process deadline (1..900 seconds; default 60)")
    return parser


def main(argv: list[str] | None = None) -> int:
    global STOP
    STOP = False
    args = argument_parser().parse_args(argv)
    if not (platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")):
        print("native Apple Silicon macOS is required", file=sys.stderr)
        return 2
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        print("--timeout-seconds must be in 1..900", file=sys.stderr)
        return 2
    try:
        validated = _validate_package(args.input_receipt)
        output = _check_external_output(args.evidence_dir, validated["package_root"])
        output.mkdir(exist_ok=False)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, IndexError) as error:
        print(f"native NIH validation preflight failed: {error}", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "RUNNING",
        "target": "macos-arm64",
        "profile": "dist",
        "input_package_receipt": {
            "path": str(validated["package_receipt_path"]),
            "sha256": validated["package_receipt_sha256"],
        },
        "underlying_build_receipt": {
            "path": str(validated["build_receipt_path"]),
            "sha256": validated["build_receipt_sha256"],
            "source_snapshot": validated["build_report"]["sources_before"],
        },
        "features": [
            {
                "name": feature,
                "payload_sha256": validated["inventory"][
                    str(validated["per_feature_paths"][feature]["clap"].relative_to(
                        validated["package_root"]
                    ))
                ]["sha256"],
                "clap": str(validated["per_feature_paths"][feature]["clap"]),
                "vst3_bundle": str(validated["per_feature_paths"][feature]["vst3_bundle"]),
                "vst3_binary": str(validated["per_feature_paths"][feature]["vst3_binary"]),
            }
            for feature in validated["features"]
        ],
        "artifact_inventory_before": [
            {"path": path, "size": row["size"], "sha256": row["sha256"]}
            for path, row in sorted(validated["inventory"].items())
        ],
        "native_validator_qualification": "pending",
        "host_loading": "pending",
        "release_qualification": "pending",
        "outer_timeout_seconds": args.timeout_seconds,
        "expected_command_count": 86,
        "commands_started": False,
        "commands": [],
        "errors": [],
    }
    _save(output, report)
    try:
        signal.signal(signal.SIGINT, interrupted)
        signal.signal(signal.SIGTERM, interrupted)
        enable_subreaper()
        env = os.environ.copy()
        env.update(
            XDG_CONFIG_HOME=str(output / "xdg/config"),
            XDG_CACHE_HOME=str(output / "xdg/cache"),
            XDG_STATE_HOME=str(output / "xdg/state"),
            PULSE_SERVER=f"unix:{output}/no-pulse",
            PIPEWIRE_REMOTE="no-sotf-plugin-validation",
            JACK_NO_START_SERVER="1",
        )
        report["validators"] = {}
        report["validators"]["clap-validator"] = _validator_identity(
            args.clap_validator, "clap-validator", output, env, report
        )
        report["validators"]["pluginval"] = _validator_identity(
            args.pluginval, "pluginval", output, env, report
        )
        for key in ("clap-validator", "pluginval"):
            report["validators"][key]["version_verified"] = True
        command_specs = _validator_commands(
            validated["features"], validated["per_feature_paths"], output,
            args.timeout_seconds,
        )
        if len(command_specs) != report["expected_command_count"]:
            raise ValueError("canonical native validator command inventory is not exactly 86 entries")
        report["commands_started"] = True
        _save(output, report)
        for command in command_specs:
            if STOP:
                break
            validator_name = command["argv_kind"]
            executable = args.clap_validator if validator_name == "clap-validator" else args.pluginval
            expected_executable_hash = report["validators"][validator_name]["sha256"]
            _run_owned(command, executable, env, expected_executable_hash, report, output)
        final_errors, final_sources, final_hashes = _final_package_check(validated)
        report["errors"].extend(final_errors)
        report["source_snapshot_after"] = final_sources
        report["package_hashes_after"] = final_hashes
        tool_errors, tool_hashes = _final_validator_check(report)
        report["errors"].extend(tool_errors)
        report["validator_hashes_after"] = tool_hashes
        if STOP:
            report["errors"].append("validation interrupted")
        if len(report["commands"]) != len(command_specs):
            report["errors"].append("native validator command inventory is incomplete")
        if any(row["status"] != "PASS" for row in report["commands"]):
            report["errors"].append("one or more native validators failed or timed out")
        formats = {}
        report["format_results"] = {}
        for kind in ("clap", "vst3"):
            report["format_results"][kind] = _format_result(report["commands"], kind)
            formats[kind] = report["format_results"][kind]["passed"]
        complete = (not report["errors"] and formats == {"clap": 43, "vst3": 43}
                    and len(report["commands"]) == 86)
        report["native_validator_qualification"] = "passed" if complete else "failed"
        report["status"] = "VALIDATED" if complete else "INCOMPLETE"
        _save(output, report)
        return 0 if complete else 1
    except KeyboardInterrupt:
        report["errors"].append("validation interrupted")
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        expected_commands = report.get("expected_command_count", 86)
        if (len(report["commands"]) != expected_commands
                and "native validator command inventory is incomplete" not in report["errors"]):
            report["errors"].append("native validator command inventory is incomplete")
        if "source_snapshot_after" not in report:
            final_errors, final_sources, final_hashes = _final_package_check(validated)
            report["errors"].extend(final_errors)
            report["source_snapshot_after"] = final_sources
            report["package_hashes_after"] = final_hashes
        if "validator_hashes_after" not in report:
            tool_errors, tool_hashes = _final_validator_check(report)
            report["errors"].extend(tool_errors)
            report["validator_hashes_after"] = tool_hashes
        report.setdefault("errors", [])
        if report["status"] == "RUNNING":
            report["status"] = "INCOMPLETE"
            report["native_validator_qualification"] = "failed"
        if "format_results" not in report:
            report["format_results"] = {
                kind: _format_result(report["commands"], kind)
                for kind in ("clap", "vst3")
            }
        _save(output, report)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
