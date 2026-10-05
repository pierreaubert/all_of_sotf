"""Positive and negative AUD145 test-inventory parser fixtures."""
import unittest

from scripts.release.aud145_r2_check import named_test


class Aud145InventoryTests(unittest.TestCase):
    def test_engine_name_and_positive_summary(self) -> None:
        named_test(
            "test engine::processing_thread::tests::misc::compiled_legacy_eq_host_falls_back_after_ordered_placement_event ... ok\n"
            "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out;\n",
            "engine::processing_thread::tests::misc::compiled_legacy_eq_host_falls_back_after_ordered_placement_event",
        )

    def test_public_capture_name_and_positive_summary(self) -> None:
        named_test(
            "test capture_base_rate_placement_matrix ... ok\n"
            "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out;\n",
            "capture_base_rate_placement_matrix",
        )

    def test_wrong_name_fails(self) -> None:
        with self.assertRaises(ValueError):
            named_test("test unrelated ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n", "engine::processing_thread::tests::misc::required")

    def test_ignored_result_fails(self) -> None:
        with self.assertRaises(ValueError):
            named_test("test engine::processing_thread::tests::misc::required ... ok\ntest result: ok. 1 passed; 0 failed; 1 ignored;\n", "engine::processing_thread::tests::misc::required")


if __name__ == "__main__":
    unittest.main()
