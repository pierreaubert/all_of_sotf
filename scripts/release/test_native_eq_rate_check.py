"""Fail closed on missing, ignored, or extra exact Rust observations."""
from __future__ import annotations

import unittest

from scripts.release.native_eq_rate_check import STATE_TESTS, exact_positive, validator_completion


class NativeEqInventoryTests(unittest.TestCase):
    def test_exact_positive(self) -> None:
        name = "params::native_eq_lowrate_tests::native_eq_frequency_preserves_valid_requests_and_rejects_invalid_clock"
        log = f"test {name} ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n"
        self.assertTrue(exact_positive(log, name))
        names = ("process-varying-sample-rates", *STATE_TESTS)
        completed = "\n".join(f"Test {name} completed" for name in names)
        self.assertTrue(all(validator_completion(completed).values()))
        for name in names:
            self.assertFalse(all(validator_completion(completed.replace(
                f"Test {name} completed", f"Test {name} failed"
            )).values()))

    def test_missing_ignored_failed_or_extra_rejected(self) -> None:
        name = "params::native_eq_lowrate_tests::native_eq_keeps_requested_state_across_validator_clocks_and_reactivation"
        good = f"test {name} ... ok\n\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n"
        for log in (
            good.replace("... ok", "... ignored"),
            good.replace("... ok", "... FAILED"),
            good.replace("1 passed", "2 passed"),
            good + "test unrelated ... ok\n",
            good.replace(name, "unrelated"),
        ):
            self.assertFalse(exact_positive(log, name))
        self.assertFalse(all(validator_completion("process-varying-sample-rates").values()))
        self.assertFalse(all(validator_completion("Test process-varying-sample-rates failed").values()))


if __name__ == "__main__":
    unittest.main()
