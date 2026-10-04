#!/usr/bin/env python3
"""Gitea-only, device-free watchOS/visionOS object builds for pinned audio forks."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.release import coreaudio_fork_check as supervisor


FORKS = {
    "psm": {
        "url": "https://github.com/pierreaubert/stacker.git",
        "rev": "48bf8e3abfb350de9387a675275a629e4daf9717",
        "parent": "cdf19cf36cd0343a97c174ee6f7f8241f88b35f0",
        "tree": "ba821b8dee01f06db14c52820c94d9dee5402d5f",
        "changed": ["psm/src/arch/aarch_aapcs64.s", "psm/src/arch/arm_aapcs.s",
                    "psm/src/arch/x86.s", "psm/src/arch/x86_64.s"],
        "licenses": {"LICENSE-APACHE": "16fe87b06e802f094b3fbb0894b137bca2b16ef1",
                     "LICENSE-MIT": "39e0ed6602151f235148e6c08413aa7eda5b9038"},
    },
    "coreaudio": {
        "url": supervisor.FORK_URL,
        "rev": supervisor.FORK_REV,
        "parent": supervisor.OFFICIAL_PARENT,
        "tree": supervisor.FORK_TREE,
        "changed": ["src/audio_unit/mod.rs", "src/audio_unit/render_callback.rs"],
        "licenses": supervisor.LICENSE_BLOBS,
    },
}
TARGETS = {"aarch64-apple-watchos": "watchos", "aarch64-apple-visionos": "xros"}


def valid_sdk(path: str) -> bool:
    sdk = Path(path.strip())
    return sdk.suffix == ".sdk" and sdk.is_dir()


def is_arm64_macho_object(description: str) -> bool:
    return "Mach-O" in description and "arm64" in description and "object" in description


def source_status(fork: Path) -> list[str]:
    # Cargo.lock is ignored by both pinned forks, but its bytes are hashed.
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                          cwd=fork, text=True, capture_output=True, check=True,
                          timeout=5).stdout.splitlines()


def main() -> int:
    if (sys.platform != "darwin" or os.environ.get("CI") != "true"
            or os.environ.get("SOTF_GITEA_DISPOSABLE_RUNNER") != "1"):
        print("Apple target qualification requires disposable macOS CI", file=sys.stderr)
        return 2
    if len(sys.argv) != 2:
        print("usage: apple_audio_fork_targets.py EVIDENCE_DIR", file=sys.stderr)
        return 2
    signal.signal(signal.SIGINT, supervisor.interrupt)
    signal.signal(signal.SIGTERM, supervisor.interrupt)
    evidence = Path(sys.argv[1]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    report: dict = {"scope": "aarch64 watchOS and visionOS device library/object builds only",
                    "commands": [], "forks": {}, "targets": {}, "errors": []}
    root_revision = supervisor.git(ROOT, "rev-parse", "HEAD")
    root_status = source_status(ROOT)
    if root_status:
        print(f"root checkout dirty before qualification: {root_status}", file=sys.stderr)
        return 2
    report["root_before"] = {"revision": root_revision,
                             "sources_sha256": supervisor.sha256(ROOT / "scripts/release/sources.json")}

    def run(name: str, argv: list[str], cwd: Path) -> str:
        entry = supervisor.command(name, argv, cwd, evidence)
        report["commands"].append({key: value for key, value in entry.items() if key != "text"})
        (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if entry["status"] != "PASS":
            raise RuntimeError(f"{name}: failed or owned process cleanup incomplete")
        return entry["text"].strip()

    try:
        with tempfile.TemporaryDirectory(prefix="apple-audio-forks-") as temporary:
            scratch = Path(temporary)
            run("xcode-select", ["xcode-select", "-p"], scratch)
            run("xcode-version", ["xcodebuild", "-version"], scratch)
            run("xcode-sdks", ["xcodebuild", "-showsdks"], scratch)
            report["host_targets_before"] = run(
                "host-rust-targets", ["rustup", "target", "list", "--installed", "--toolchain", "1.99.0"], scratch
            ).splitlines()
            sdk_paths: dict[str, str] = {}
            for target, sdk_name in TARGETS.items():
                try:
                    path = run(f"{sdk_name}-sdk", ["xcrun", "--sdk", sdk_name,
                                                   "--show-sdk-path"], scratch)
                    if not valid_sdk(path):
                        raise RuntimeError(f"{sdk_name}: SDK path missing or invalid: {path!r}")
                    sdk_paths[target] = path
                    report["targets"][target] = {"sdk": path, "status": "READY"}
                except Exception as error:
                    last = report["commands"][-1] if report["commands"] else {}
                    if (supervisor.INTERRUPTED or last.get("name") != f"{sdk_name}-sdk"
                            or not last.get("cleanup", {}).get("ok", False)):
                        raise RuntimeError(f"{sdk_name}: qualification interrupted or cleanup failed") from error
                    report["targets"][target] = {"status": "PENDING_SDK", "error": str(error)}
                    report["errors"].append(f"{target}: SDK prerequisite missing: {error}")
            if report["errors"]:
                raise RuntimeError("Apple SDK prerequisites unavailable; no SDK installed or target skipped")

            # Copy the installed compiler into an owned Rustup home. Only the
            # two target std components may be installed there by rustup.
            rustc = Path(run("host-rustc", ["rustup", "which", "rustc", "--toolchain", "1.99.0"],
                             scratch))
            source_toolchain = rustc.parent.parent
            if not rustc.is_file() or not source_toolchain.name.startswith("1.99.0-"):
                raise RuntimeError("existing Rust 1.99.0 toolchain path is invalid")
            rustup_home = scratch / "rustup"
            cargo_home = scratch / "cargo"
            (rustup_home / "toolchains").mkdir(parents=True)
            cargo_home.mkdir()
            run("copy-toolchain", ["ditto", str(source_toolchain),
                                   str(rustup_home / "toolchains" / source_toolchain.name)], scratch)
            private_env = ["env", f"RUSTUP_HOME={rustup_home}", f"CARGO_HOME={cargo_home}",
                           "RUSTUP_TOOLCHAIN=1.99.0"]
            for target in TARGETS:
                run(f"install-std-{target}", private_env + ["rustup", "target", "add",
                    "--toolchain", "1.99.0", target], scratch)
            installed = set(run("private-rust-targets", private_env + ["rustup", "target",
                                "list", "--installed", "--toolchain", "1.99.0"], scratch).splitlines())
            if not set(TARGETS).issubset(installed):
                raise RuntimeError("disposable Rustup home lacks required target std components")
            report["private_targets_after"] = sorted(installed)

            for name, pin in FORKS.items():
                fork = scratch / name
                run(f"clone-{name}", ["git", "clone", "--no-checkout", pin["url"], str(fork)], scratch)
                run(f"checkout-{name}", ["git", "checkout", "--detach", pin["rev"]], fork)
                if (supervisor.git(fork, "rev-parse", "HEAD") != pin["rev"]
                        or supervisor.git(fork, "rev-parse", "HEAD^") != pin["parent"]
                        or supervisor.git(fork, "rev-parse", "HEAD^{tree}") != pin["tree"]):
                    raise RuntimeError(f"{name}: fork provenance mismatch")
                changed = supervisor.git(fork, "diff", "--name-only", "HEAD^", "HEAD").splitlines()
                if changed != pin["changed"] or source_status(fork):
                    raise RuntimeError(f"{name}: changed-file inventory or source status mismatch")
                for license_name, blob in pin["licenses"].items():
                    if supervisor.git(fork, "rev-parse", f"HEAD:{license_name}") != blob:
                        raise RuntimeError(f"{name}: license blob mismatch")
                manifest = fork / ("psm/Cargo.toml" if name == "psm" else "Cargo.toml")
                target_dir = manifest.parent / "target"
                fork_env = private_env + [f"CARGO_TARGET_DIR={target_dir}"]
                run(f"resolve-{name}", fork_env + ["cargo", "generate-lockfile",
                    "--manifest-path", str(manifest)], fork)
                lock = manifest.parent / "Cargo.lock"
                if not lock.is_file():
                    raise RuntimeError(f"{name}: resolved lock absent")
                lock_hash = supervisor.sha256(lock)
                shutil.copy2(lock, evidence / f"{name}.Cargo.lock")
                report["forks"][name] = {"rev": pin["rev"], "parent": pin["parent"],
                                         "tree": pin["tree"], "changed": changed,
                                         "licenses": pin["licenses"], "lock_sha256": lock_hash}

                for target, sdk_name in TARGETS.items():
                    sdk = sdk_paths[target]
                    clang = run(f"clang-{sdk_name}", ["xcrun", "--sdk", sdk_name,
                                                       "--find", "clang"], scratch)
                    env = fork_env + [f"SDKROOT={sdk}",
                        f"CARGO_TARGET_{target.upper().replace('-', '_')}_LINKER={clang}",
                        f"CC_{target.replace('-', '_')}={clang}"]
                    run(f"build-{name}-{sdk_name}", env + ["cargo", "build", "--locked",
                        "--lib", "--target", target, "--manifest-path", str(manifest), "-vv"], fork)
                    if name == "psm":
                        objects = list((target_dir / target / "debug" / "build")
                                       .glob("psm-*/out/*aarch_aapcs64*.o"))
                        if not objects:
                            raise RuntimeError(f"{target}: PSM assembly object absent")
                        for index, obj in enumerate(objects):
                            desc = run(f"object-psm-{sdk_name}-{index}", ["file", str(obj)], scratch)
                            if not is_arm64_macho_object(desc):
                                raise RuntimeError(f"{target}: PSM object is not Mach-O arm64: {desc}")
                            shutil.copy2(obj, evidence / f"psm-{sdk_name}-{index}.o")
                        report["targets"][target]["psm_objects"] = len(objects)
                    else:
                        rlib = target_dir / target / "debug" / "libcoreaudio.rlib"
                        if not rlib.is_file():
                            raise RuntimeError(f"{target}: CoreAudio rlib absent")
                        archive = run(f"archive-coreaudio-{sdk_name}", ["ar", "-t", str(rlib)], scratch)
                        object_members = [member for member in archive.splitlines() if member.endswith(".o")]
                        if not object_members:
                            raise RuntimeError(f"{target}: CoreAudio archive lacks compiled object")
                        extracted = scratch / f"coreaudio-object-{sdk_name}"
                        extracted.mkdir()
                        run(f"extract-coreaudio-{sdk_name}",
                            ["ar", "-x", str(rlib), object_members[0]], extracted)
                        object_path = extracted / object_members[0]
                        if not object_path.is_file():
                            raise RuntimeError(f"{target}: CoreAudio archive member absent after extract")
                        desc = run(f"object-coreaudio-{sdk_name}", ["file", str(object_path)], scratch)
                        if not is_arm64_macho_object(desc):
                            raise RuntimeError(f"{target}: CoreAudio object is not Mach-O arm64: {desc}")
                        shutil.copy2(object_path, evidence / f"coreaudio-{sdk_name}.o")
                        report["targets"][target]["coreaudio_rlib_sha256"] = supervisor.sha256(rlib)
                if (supervisor.git(fork, "rev-parse", "HEAD") != pin["rev"]
                        or supervisor.sha256(lock) != lock_hash or source_status(fork)):
                    raise RuntimeError(f"{name}: source or resolved lock changed during cross-build")
            for target in TARGETS:
                report["targets"][target]["status"] = "PASS"
    except Exception as error:
        report["errors"].append(str(error))
    try:
        report["root_after"] = {"revision": supervisor.git(ROOT, "rev-parse", "HEAD"),
                                "source_status": source_status(ROOT),
                                "sources_sha256": supervisor.sha256(ROOT / "scripts/release/sources.json")}
        if (report["root_after"]["revision"] != root_revision
                or report["root_after"]["source_status"]
                or report["root_after"]["sources_sha256"]
                != report["root_before"]["sources_sha256"]):
            report["errors"].append("root source checkout changed during qualification")
    except Exception as error:
        report["errors"].append(f"root after-state inspection failed: {error}")
    (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
