"""Check Rubato gate supervision and strict full-test inventory."""

import signal
import unittest

from scripts.release import rubato_fractional_check
from scripts.release.test_gpui_overlay_check import prove_signal_cleanup


class RubatoSupervisorTests(unittest.TestCase):
    def test_sigint_cleans_owned_child_and_blocks_next_command(self) -> None:
        prove_signal_cleanup(rubato_fractional_check, signal.SIGINT)

    def test_sigterm_cleans_owned_child_and_blocks_next_command(self) -> None:
        prove_signal_cleanup(rubato_fractional_check, signal.SIGTERM)

    def test_full_report_rejects_ignored_tests(self) -> None:
        self.assertEqual(
            rubato_fractional_check.full_test_counts(
                "test result: ok. 3 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out\n"
            ), (3, 1),
        )
