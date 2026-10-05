"""Check exact-test evidence before running the remote RNNoise matrix."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.release.rnnoise_exact_clock_check import inventory


class InventoryTests(unittest.TestCase):
    def test_exact_named_inventory_and_documented_manual_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "tests.log"
            log.write_text(
                "test first_clock ... ok\n"
                "test second_clock ... ok\n"
                "test manual_capture ... ignored, manual evidence\n"
                "test result: ok. 2 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out\n"
            )
            result = inventory(log, {"first_clock", "second_clock"},
                               {"manual_capture": "manual evidence"})
            self.assertEqual(result["passed"], ["first_clock", "second_clock"])
            self.assertEqual(result["ignored"], {"manual_capture": "manual evidence"})

    def test_missing_named_test_cannot_qualify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "tests.log"
            log.write_text(
                "test first_clock ... ok\n"
                "test replacement_clock ... ok\n"
                "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
            )
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                inventory(log, {"first_clock", "second_clock"}, {})

    def test_unexpected_ignore_cannot_qualify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "tests.log"
            log.write_text(
                "test first_clock ... ok\n"
                "test second_clock ... ignored, unexpected\n"
                "test result: ok. 1 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out\n"
            )
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                inventory(log, {"first_clock"}, {"second_clock": "approved manual reason"})

    def test_failed_summary_cannot_qualify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "tests.log"
            log.write_text(
                "test first_clock ... ok\n"
                "test second_clock ... FAILED\n"
                "test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured\n"
            )
            with self.assertRaisesRegex(ValueError, "successful test summary"):
                inventory(log, {"first_clock", "second_clock"}, {})


if __name__ == "__main__":
    unittest.main()
