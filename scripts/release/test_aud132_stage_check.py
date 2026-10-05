"""Pure inventory checks for the diagnostic stage artifact gate."""
from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from scripts.release import aud132_stage_check as gate


class StageInventoryTests(unittest.TestCase):
    def test_exact_thirty_finite_vectors_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory)
            expected = gate.expected_inventory()
            self.assertEqual(len(expected), 30)
            for name, count in expected.items():
                (capture / name).write_bytes(struct.pack("<f", 0.25) * count)
            with mock.patch.object(gate, "CAPTURE", capture):
                self.assertEqual(len(gate.validate_vectors()), 30)
                (capture / "n256_canonical_stage_fft_left_complex.f32le").unlink()
                with self.assertRaisesRegex(ValueError, "stage inventory differs"):
                    gate.validate_vectors()
                (capture / "n256_canonical_stage_fft_left_complex.f32le").write_bytes(
                    struct.pack("<f", 0.25) * expected["n256_canonical_stage_fft_left_complex.f32le"]
                )
                (capture / "n512_canonical_stage_full_output.f32le").write_bytes(b"short")
                with self.assertRaisesRegex(ValueError, "expected 9728 f32 samples"):
                    gate.validate_vectors()
                (capture / "n512_canonical_stage_full_output.f32le").write_bytes(
                    struct.pack("<f", 0.25) * expected["n512_canonical_stage_full_output.f32le"]
                )
                (capture / "n2_canonical_stage_window.f32le").write_bytes(
                    struct.pack("<f", float("nan")) * expected["n2_canonical_stage_window.f32le"]
                )
                with self.assertRaisesRegex(ValueError, "nonfinite"):
                    gate.validate_vectors()
