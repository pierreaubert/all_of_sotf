"""Pure preflight checks for the disposable AUD132 diagnostic runner."""

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.release import aud132_canonical_input_check as gate


class Aud132CanonicalInputTests(unittest.TestCase):
    def test_module_imports_from_checkout_root(self) -> None:
        self.assertEqual(gate.ROOT, Path(__file__).resolve().parents[2])

    def test_fixture_length_and_hash_fail_closed(self) -> None:
        gate.validate_fixture(gate.FIXTURE)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "input.f32le"
            data = gate.FIXTURE.read_bytes()
            fixture.write_bytes(data[:-1])
            with self.assertRaises(ValueError):
                gate.validate_fixture(fixture)
            fixture.write_bytes(bytes([data[0] ^ 1]) + data[1:])
            with self.assertRaises(ValueError):
                gate.validate_fixture(fixture)

    def test_positive_inventory_requires_named_leaf_and_clean_summary(self) -> None:
        good = (f"test stream_boundary_tests::{gate.TEST_NAME} ... ok\n"
                "test result: ok. 1 passed; 0 failed; 0 ignored; 146 filtered out;\n")
        self.assertTrue(gate.positive_inventory(good))
        self.assertFalse(gate.positive_inventory(good.replace(gate.TEST_NAME, "different_test")))
        self.assertFalse(gate.positive_inventory(good.replace("0 ignored", "1 ignored")))
        self.assertFalse(gate.positive_inventory(good.replace("1 passed", "0 passed")))

    def test_interruption_prevents_cargo_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report: dict = {"cases": []}
            gate.STOP = True
            try:
                with mock.patch.object(gate.subprocess, "Popen",
                                       side_effect=AssertionError("Cargo must not launch")) as popen:
                    with self.assertRaises(KeyboardInterrupt):
                        gate.run_case("interrupted", output, None, report)
                    popen.assert_not_called()
                self.assertEqual(report["cases"][0]["status"], "INTERRUPTED_BEFORE_LAUNCH")
            finally:
                gate.STOP = False


if __name__ == "__main__":
    unittest.main()
