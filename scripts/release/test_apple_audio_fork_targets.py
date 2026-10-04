"""Preflight guards for device-free Apple fork cross-compilation."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.release import apple_audio_fork_targets as gate


class ApplePreflightTests(unittest.TestCase):
    def test_missing_sdk_cannot_be_treated_as_a_present_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "WatchOS.sdk"
            self.assertFalse(gate.valid_sdk(str(path)))
            path.mkdir()
            self.assertTrue(gate.valid_sdk(str(path)))
            self.assertFalse(gate.valid_sdk(str(Path(temporary) / "WatchOS")))

    def test_object_probe_rejects_text_and_wrong_architecture(self) -> None:
        self.assertTrue(gate.is_arm64_macho_object("Mach-O 64-bit arm64 object"))
        self.assertFalse(gate.is_arm64_macho_object("Mach-O 64-bit x86_64 object"))
        self.assertFalse(gate.is_arm64_macho_object("ASCII text, with very long lines"))

    def test_source_guard_rejects_generated_source_changes(self) -> None:
        with mock.patch.object(
            gate.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, stdout=" M src/lib.rs\n", stderr=""),
        ):
            self.assertEqual(gate.source_status(Path(".")), [" M src/lib.rs"])
