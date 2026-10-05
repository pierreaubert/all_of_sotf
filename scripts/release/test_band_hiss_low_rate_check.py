"""Fail closed on missing, ignored, or extra exact Rust observations."""
from __future__ import annotations

import unittest

from scripts.release.band_hiss_low_rate_check import exact_positive, rate_test_completed


class BandHissInventoryTests(unittest.TestCase):
    def test_exact_positive(self) -> None:
        name = "params::default_sync_tests::native_band_split_constructs_with_requested_cutoff_at_fractional_low_rate"
        log = f"test {name} ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n"
        self.assertTrue(exact_positive(log, name))
        self.assertTrue(rate_test_completed("Test process-varying-sample-rates completed"))

    def test_missing_ignored_failed_or_extra_rejected(self) -> None:
        name = "params::default_sync_tests::native_hiss_uses_effective_low_rate_cutoff_without_changing_host_request"
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
