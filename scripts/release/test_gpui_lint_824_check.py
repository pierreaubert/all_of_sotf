"""Fail-closed GPUI lint positive inventory checks."""
import unittest
from scripts.release.gpui_lint_824_check import TESTS, test_result


class InventoryTests(unittest.TestCase):
    def test_all_three_exact_positive_names(self):
        for name in TESTS.values():
            with self.subTest(name=name):
                log = f"running 1 test\ntest {name} ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 20 filtered out\n"
                self.assertTrue(test_result(log, name))

    def test_zero_selected_rejected(self):
        self.assertFalse(test_result("running 0 tests\ntest result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 20 filtered out\n", next(iter(TESTS.values()))))

    def test_wrong_named_positive_rejected(self):
        name = next(iter(TESTS.values()))
        self.assertFalse(test_result(f"test other::test ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 20 filtered out\n", name))

    def test_failed_or_ignored_rejected(self):
        name = next(iter(TESTS.values()))
        self.assertFalse(test_result(f"test {name} ... FAILED\ntest result: FAILED. 0 passed; 1 failed; 0 ignored\n", name))
        self.assertFalse(test_result(f"test {name} ... ok\ntest result: ok. 1 passed; 0 failed; 1 ignored\n", name))


if __name__ == "__main__":
    unittest.main()
