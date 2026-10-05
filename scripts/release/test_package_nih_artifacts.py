"""Focused validation of pack-only NIH receipt consumption and bundle output."""

from __future__ import annotations

import json
import plistlib
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.release import package_nih_artifacts as packer
from scripts.release.checkout_sources import read_manifest


class PackageNihArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.evidence = self.base / "input-evidence"
        self.evidence.mkdir()
        self.target_dir = self.evidence / "cargo-target"
        self.target_dir.mkdir()
        self.current = self.current_snapshot()

    def current_snapshot(self) -> dict:
        _, _, pins = read_manifest(packer.ROOT / "scripts/release/sources.json")
        sources = {}
        for index, name in enumerate(sorted(packer.workspace_map())):
            source = {
                "revision": pins[name], "dirty": False,
                "lock_sha256": f"{index + 1:064x}",
            }
            if name == "autoeq":
                source["nested_lock_sha256"] = "a" * 64
            sources[name] = source
        return {
            "root_revision": "b" * 40,
            "sources_manifest_sha256": packer.file_sha256(
                packer.ROOT / "scripts/release/sources.json"),
            "sources": sources,
            "root_layout": {
                "missing": [], "unexpected": [], "tracked_gitlinks": sorted(pins),
                "allowed_siblings": [],
            },
            "issues": [],
        }

    @staticmethod
    def macho_arm64() -> bytes:
        return struct.pack("<IiiIIII", 0xFEEDFACF, packer.MACOS_ARM64_CPU_TYPE,
                           0, 6, 1, 0, 0) + b"fixture-payload"

    @staticmethod
    def elf_arm64() -> bytes:
        return b"\x7fELF\x02\x01\x01" + b"\x00" * 11 + struct.pack("<H", 183) + b"fixture-payload"

    def make_report(self, target: str) -> Path:
        extension = "dylib" if target == "macos-arm64" else "so"
        header = self.macho_arm64() if target == "macos-arm64" else self.elf_arm64()
        results = []
        spec_by_label = {
            str(item["label"]): item
            for item in packer.CONTRACT["targets"][target]["plugins"]["build_only"]
        }
        for feature in packer.NIH_FEATURES:
            label = f"plugin-{feature}"
            path = (self.evidence / "artifacts" / target / "plugins" / label /
                    f"libplugins_nih.{extension}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(header + feature.encode("ascii"))
            argv = [str(part) for part in spec_by_label[label]["argv"]]
            argv.extend(["--target-dir", str(self.target_dir.resolve())])
            results.append({
                "target": target,
                "group": "plugins",
                "step": label,
                "status": "built",
                "artifact": str(path),
                "sha256": packer.file_sha256(path),
                "exit_code": 0,
                "argv": argv,
                "owned_group_cleanup": {"ok": True, "remaining": [], "errors": []},
            })
        before = {
            "root_revision": self.current["root_revision"],
            "sources_manifest_sha256": self.current["sources_manifest_sha256"],
            "sources": self.current["sources"],
            "root_layout": self.current["root_layout"],
            "issues": [],
        }
        report = {
            "schema": 1,
            "mode": "build-only",
            "status": "INCOMPLETE",
            "release_complete": False,
            "source_root": str(packer.ROOT),
            "source_snapshot_unchanged": True,
            "sources_before": before,
            "sources_after": before,
            "cargo_environment": {
                "cargo_net_offline": "true",
                "cargo_target_dir": str(self.target_dir.resolve()),
            },
            "results": results,
        }
        path = self.evidence / "local-release-groups-report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def package(self, target: str, report: Path, output: Path) -> Path:
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            return packer.package_from_receipt(report, target, output)

    def test_macos_receipt_produces_exact_bundle_layout_and_inventory(self) -> None:
        report = self.make_report("macos-arm64")
        output = self.base / "macos-package"
        receipt_path = self.package("macos-arm64", report, output)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["profile"], "dist")
        self.assertEqual(receipt["target_triple"], "aarch64-apple-darwin")
        self.assertEqual(len(receipt["features"]), 43)
        self.assertEqual(len(receipt["artifact_inventory"]), 129)
        feature = "fletcher-munson"
        base = packer.feature_base(feature)
        display = packer.vst3_name(feature)
        clap = output / "artifacts/sotf-daw/dist/clap" / f"{base}.clap"
        binary = output / "artifacts/sotf-daw/dist/vst3" / f"{display}.vst3/Contents/MacOS/{base}"
        info = binary.parents[1] / "Info.plist"
        self.assertEqual(clap.read_bytes(), binary.read_bytes())
        input_binary = (
            self.evidence / "artifacts/macos-arm64/plugins"
            / f"plugin-{feature}/libplugins_nih.dylib"
        )
        self.assertEqual(clap.read_bytes(), input_binary.read_bytes())
        plist = plistlib.loads(info.read_bytes())
        self.assertEqual(plist["CFBundleExecutable"], base)
        self.assertEqual(plist["CFBundleIdentifier"], f"org.spinorama.sotf.{base}.vst3")
        self.assertEqual(plist["CFBundleName"], display)
        self.assertEqual(plist["CFBundlePackageType"], "BNDL")
        self.assertEqual(receipt["qualification"], {
            "native_validators": "pending",
            "host_loading": "pending",
            "release_qualification": "pending",
        })

    def test_linux_receipt_produces_architecture_specific_bundle_layout(self) -> None:
        report = self.make_report("linux-arm64")
        output = self.base / "linux-package"
        receipt_path = self.package("linux-arm64", report, output)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["target_triple"], "aarch64-unknown-linux-gnu")
        self.assertEqual(len(receipt["artifact_inventory"]), 86)
        feature = "speech-denoiser"
        base = packer.feature_base(feature)
        display = packer.vst3_name(feature)
        clap = output / "artifacts/sotf-daw/dist/clap-linux" / f"{base}.clap"
        vst3 = (output / "artifacts/sotf-daw/dist/vst3-linux" / f"{display}.vst3"
                / "Contents/aarch64-linux" / f"{display}.so")
        self.assertEqual(clap.read_bytes(), vst3.read_bytes())
        packer.assert_elf_architecture(vst3, "aarch64-linux")

    def test_receipt_without_persisted_dist_argv_is_rejected(self) -> None:
        report = self.make_report("macos-arm64")
        data = json.loads(report.read_text())
        data["results"][0].pop("argv")
        report.write_text(json.dumps(data))
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            with self.assertRaisesRegex(ValueError, "build command proof"):
                packer._validate_build_receipt(report, "macos-arm64")

    def test_receipt_with_release_profile_is_rejected(self) -> None:
        report = self.make_report("linux-arm64")
        data = json.loads(report.read_text())
        argv = data["results"][0]["argv"]
        argv[argv.index("dist")] = "release"
        report.write_text(json.dumps(data))
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            with self.assertRaisesRegex(
                ValueError, "does not prove the expected locked offline dist profile"
            ):
                packer._validate_build_receipt(report, "linux-arm64")

    def test_modified_input_hash_is_rejected_before_output_creation(self) -> None:
        report = self.make_report("macos-arm64")
        data = json.loads(report.read_text())
        artifact = Path(data["results"][0]["artifact"])
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        output = self.base / "should-not-exist"
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            with self.assertRaisesRegex(ValueError, "hash differs"):
                packer.package_from_receipt(report, "macos-arm64", output)
        self.assertFalse(output.exists())

    def test_wrong_macho_architecture_is_rejected_even_with_updated_hash(self) -> None:
        report = self.make_report("macos-arm64")
        data = json.loads(report.read_text())
        row = data["results"][0]
        artifact = Path(row["artifact"])
        artifact.write_bytes(struct.pack("<IiiIIII", 0xFEEDFACF, 0x01000007,
                                         0, 6, 1, 0, 0) + b"x86_64")
        row["sha256"] = packer.file_sha256(artifact)
        report.write_text(json.dumps(data))
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            with self.assertRaisesRegex(ValueError, "not an ARM64 Mach-O"):
                packer._validate_build_receipt(report, "macos-arm64")

    def test_macho_executable_is_not_accepted_as_a_dynamic_library(self) -> None:
        report = self.make_report("macos-arm64")
        data = json.loads(report.read_text())
        row = data["results"][0]
        artifact = Path(row["artifact"])
        artifact.write_bytes(
            struct.pack("<IiiIIII", 0xFEEDFACF, packer.MACOS_ARM64_CPU_TYPE,
                        0, 2, 1, 0, 0) + b"executable"
        )
        row["sha256"] = packer.file_sha256(artifact)
        report.write_text(json.dumps(data))
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            with self.assertRaisesRegex(ValueError, "not a Mach-O dynamic library"):
                packer._validate_build_receipt(report, "macos-arm64")

    def test_symlinked_plugin_input_is_rejected(self) -> None:
        report = self.make_report("linux-arm64")
        data = json.loads(report.read_text())
        artifact = Path(data["results"][0]["artifact"])
        external = self.base / "outside.so"
        external.write_bytes(artifact.read_bytes())
        artifact.unlink()
        artifact.symlink_to(external)
        report.write_text(json.dumps(data))
        with mock.patch.object(packer, "_current_provenance", return_value=self.current):
            with self.assertRaisesRegex(ValueError, "symlink path component"):
                packer._validate_build_receipt(report, "linux-arm64")

    def test_symlinked_receipt_parent_is_rejected_before_read(self) -> None:
        report = self.make_report("macos-arm64")
        link = self.base / "receipt-link"
        link.symlink_to(self.evidence, target_is_directory=True)
        linked_report = link / report.name
        output = self.base / "unwritten-output"
        with self.assertRaisesRegex(ValueError, "symlink path component"):
            packer.package_from_receipt(linked_report, "macos-arm64", output)
        self.assertFalse(output.exists())

    def test_symlinked_output_parent_is_rejected_without_touching_target(self) -> None:
        report = self.make_report("linux-arm64")
        real_parent = self.base / "real-output-parent"
        real_parent.mkdir()
        link = self.base / "output-link"
        link.symlink_to(real_parent, target_is_directory=True)
        output = link / "candidate"
        with self.assertRaisesRegex(ValueError, "symlink path component"):
            packer.package_from_receipt(report, "linux-arm64", output)
        self.assertFalse((real_parent / "candidate").exists())

    def test_missing_extra_and_duplicate_feature_results_are_rejected(self) -> None:
        cases = ("missing", "extra", "duplicate")
        for case in cases:
            with self.subTest(case=case):
                report = self.make_report("linux-arm64")
                data = json.loads(report.read_text())
                if case == "missing":
                    data["results"].pop(0)
                elif case == "extra":
                    extra = dict(data["results"][0])
                    extra["step"] = "plugin-unlisted-feature"
                    data["results"].append(extra)
                else:
                    data["results"].append(dict(data["results"][0]))
                report.write_text(json.dumps(data))
                with mock.patch.object(packer, "_current_provenance", return_value=self.current):
                    with self.assertRaisesRegex(
                        ValueError, "duplicate NIH feature|exactly the canonical 43"
                    ):
                        packer._validate_build_receipt(report, "linux-arm64")

    def test_receipt_mutation_during_copy_removes_partial_output(self) -> None:
        report = self.make_report("macos-arm64")
        output = self.base / "partial-output"
        original_write = packer._write_artifacts

        def write_then_mutate(*args, **kwargs):
            inventory = original_write(*args, **kwargs)
            report.write_text(report.read_text(encoding="utf-8") + " ", encoding="utf-8")
            return inventory

        with mock.patch.object(packer, "_current_provenance", return_value=self.current), \
                mock.patch.object(packer, "_write_artifacts", side_effect=write_then_mutate):
            with self.assertRaisesRegex(ValueError, "receipt changed during packaging"):
                packer.package_from_receipt(report, "macos-arm64", output)
        self.assertFalse(output.exists())

    def test_source_mutation_during_copy_removes_partial_output(self) -> None:
        report = self.make_report("linux-arm64")
        output = self.base / "partial-source-output"
        changed = json.loads(json.dumps(self.current))
        changed["sources"]["sotf-daw"]["lock_sha256"] = "f" * 64
        with mock.patch.object(packer, "_current_provenance", side_effect=(self.current, changed)):
            with self.assertRaisesRegex(
                ValueError, "current checkout is not clean and pin-matched|snapshot is stale"
            ):
                packer.package_from_receipt(report, "linux-arm64", output)
        self.assertFalse(output.exists())

    def test_source_lock_snapshot_must_still_match_current(self) -> None:
        report = self.make_report("linux-arm64")
        stale = json.loads(json.dumps(self.current))
        stale["sources"]["sotf-daw"]["lock_sha256"] = "f" * 64
        with mock.patch.object(packer, "_current_provenance", return_value=stale):
            with self.assertRaisesRegex(ValueError, "snapshot is stale"):
                packer._validate_build_receipt(report, "linux-arm64")


if __name__ == "__main__":
    unittest.main()
