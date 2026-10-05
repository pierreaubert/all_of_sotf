"""Fail closed on missing, ignored, or extra exact Rust observations."""
from __future__ import annotations

import unittest

from scripts.release.upmixer_rate_check import exact_positive, rate_test_completed


class UpmixerInventoryTests(unittest.TestCase):
    def test_exact_positive(self) -> None:
        name = "test::tests::upmixer_tests::upmixer_initializes_and_processes_at_all_validator_sample_rates"
        log = f"test {name} ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n"
        self.assertTrue(exact_positive(log, name))
        self.assertTrue(rate_test_completed("Test process-varying-sample-rates completed"))

    def test_missing_ignored_failed_or_extra_rejected(self) -> None:
        name = "test::tests::upmixer_tests::unsupported_sample_rate_refusal_preserves_prepared_state"
        good = f"test {name} ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n"
        for log in (
            good.replace("... ok", "... ignored"),
            good.replace("... ok", "... FAILED"),
            good.replace("1 passed", "2 passed"),
            good + "test unrelated ... ok\n",
            good.replace(name, "unrelated"),
        ):
            self.assertFalse(exact_positive(log, name))
        self.assertFalse(rate_test_completed("process-varying-sample-rates"))
        self.assertFalse(rate_test_completed("Test process-varying-sample-rates failed"))


if __name__ == "__main__":
    unittest.main()
