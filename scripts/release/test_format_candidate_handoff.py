"""Safety preflight for handing off from formatter commands to compilation."""

import unittest

from scripts.release.format_candidate_check import safe_to_start_next_phase


class FormatCandidateHandoffTests(unittest.TestCase):
    def test_signal_before_first_command_prevents_handoff(self) -> None:
        self.assertFalse(safe_to_start_next_phase({"interrupted": True, "commands": []}))

    def test_signal_after_clean_command_prevents_handoff(self) -> None:
        report = {"interrupted": True, "commands": [
            {"cleanup_ok": True, "interrupted": False, "survivors": []}
        ]}
        self.assertFalse(safe_to_start_next_phase(report))

    def test_clean_source_failure_allows_independent_compile_evidence(self) -> None:
        report = {"interrupted": False, "commands": [
            {"exit_code": 1, "cleanup_ok": True, "interrupted": False, "survivors": []}
        ]}
        self.assertTrue(safe_to_start_next_phase(report))


if __name__ == "__main__":
    unittest.main()
