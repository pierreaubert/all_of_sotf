"""Inventory checks for the pinned serial_test 4 gate."""
import unittest

from scripts.release.serial_test_4_check import parse_tests

NAME = "manager::tests::verified_rate_cache_stores_multiple_device_channel_entries"


class InventoryTests(unittest.TestCase):
    def test_exact_positive_inventory(self):
        parsed = parse_tests(f"test {NAME} ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n", {NAME})
        self.assertEqual(parsed["passed"], [NAME])

    def test_wrong_or_missing_name_fails(self):
        for log in ("test other ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n",
                    "test result: ok. 0 passed; 0 failed; 0 ignored;\n"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_tests(log, {NAME})

    def test_ignored_and_failure_fail(self):
        for log in (f"test {NAME} ... ignored\ntest result: ok. 0 passed; 0 failed; 1 ignored;\n",
                    f"test {NAME} ... FAILED\ntest result: FAILED. 0 passed; 1 failed; 0 ignored;\n"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_tests(log, {NAME})

    def test_duplicate_and_count_mismatch_fail(self):
        for log in (f"test {NAME} ... ok\ntest {NAME} ... ok\ntest result: ok. 2 passed; 0 failed; 0 ignored;\n",
                    f"test {NAME} ... ok\ntest result: ok. 2 passed; 0 failed; 0 ignored;\n"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_tests(log, {NAME})
