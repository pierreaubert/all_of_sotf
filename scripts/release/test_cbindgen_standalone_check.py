"""Check that upstream header fixtures have exact positive inventory."""
from __future__ import annotations

import unittest

from scripts.release.cbindgen_standalone_check import fixture_results


NAMES = ["test_alpha", "test_beta"]
SUMMARY = "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s\n"


class FixtureInventoryTests(unittest.TestCase):
    def test_exact_positive_inventory(self):
        log = "test test_alpha ... ok\ntest test_beta ... ok\n" + SUMMARY
        self.assertEqual(fixture_results(log, NAMES)["names"], NAMES)

    def test_missing_or_extra_name_rejected(self):
        for lines in ("test test_alpha ... ok\n", "test test_alpha ... ok\ntest test_gamma ... ok\n"):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                fixture_results(lines + SUMMARY, NAMES)

    def test_duplicate_or_ignored_rejected(self):
        for lines in ("test test_alpha ... ok\ntest test_alpha ... ok\n",
                      "test test_alpha ... ok\ntest test_beta ... ignored\n"):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                fixture_results(lines + SUMMARY, NAMES)

    def test_summary_mismatch_rejected(self):
        log = "test test_alpha ... ok\ntest test_beta ... ok\n"
        for summary in ("", SUMMARY.replace("2 passed", "1 passed"),
                        SUMMARY.replace("0 ignored", "1 ignored")):
            with self.subTest(summary=summary), self.assertRaises(ValueError):
                fixture_results(log + summary, NAMES)


if __name__ == "__main__":
    unittest.main()
