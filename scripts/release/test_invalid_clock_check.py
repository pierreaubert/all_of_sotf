"""Positive test inventory checks for the live output clock gate."""
from __future__ import annotations

import unittest
from unittest import mock

from scripts.release import invalid_clock_check as gate


class ClockGateTests(unittest.TestCase):
    def test_exact_named_positive_inventory(self) -> None:
        names = sorted(gate.REQUIRED["engine-frame-format"])
        log = "".join(f"test {name} ... ok\n" for name in names)
        log += f"test result: ok. {len(names)} passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
        result = gate.parse_tests(log, set(names))
        self.assertEqual(result["passed"], names)

    def test_missing_or_ignored_required_test_is_rejected(self) -> None:
        names = sorted(gate.REQUIRED["engine-frame-format"])
        only_one = f"test {names[0]} ... ok\n"
        summary = "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 1 filtered out\n"
        with self.assertRaises(ValueError):
            gate.parse_tests(only_one + summary, set(names))
        ignored = f"test {names[1]} ... ignored, manual\n"
        summary = "test result: ok. 1 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out\n"
        with self.assertRaises(ValueError):
            gate.parse_tests(only_one + ignored + summary, set(names))

    def test_summary_must_match_named_positive_count(self) -> None:
        name = sorted(gate.REQUIRED["engine-frame-format"])[0]
        log = f"test {name} ... ok\n"
        log += "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
        with self.assertRaises(ValueError):
            gate.parse_tests(log, {name})

    def test_rust_should_panic_markers_count_as_exact_named_passes(self) -> None:
        names = (
            "param_specs::tests::default_bool_panics_on_float_param",
            "param_specs::tests::default_choice_label_panics_on_non_choice",
            "param_specs::tests::find_by_key_panics_when_missing",
        )
        log = "".join(f"test {name} - should panic ... ok\n" for name in names)
        log += "test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
        result = gate.parse_tests(log, set(names))
        self.assertEqual(result["passed"], list(names))
        with self.assertRaises(ValueError):
            gate.parse_tests(log.replace(" - should panic ... ok", " - arbitrary marker ... ok", 1), set(names))

    def test_only_exact_manual_kernel_control_ignore_is_allowed(self) -> None:
        name = sorted(gate.REQUIRED["host-lib"])[0]
        ignored_name, reason = next(iter(gate.HOST_MANUAL_IGNORE.items()))
        log = f"test {name} ... ok\n"
        log += f"test {ignored_name} ... ignored, {reason}\n"
        log += "test result: ok. 1 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out\n"
        result = gate.parse_tests(log, {name}, gate.HOST_MANUAL_IGNORE)
        self.assertEqual(result["ignored"], [(ignored_name, reason)])
        self.assertEqual(len(result["coverage_limits"]), 1)
        for changed in (log.replace(reason, "unreviewed skip"),
                        log.replace(ignored_name, "another_test"),
                        log.replace("1 ignored", "2 ignored")):
            with self.assertRaises(ValueError):
                gate.parse_tests(changed, {name}, gate.HOST_MANUAL_IGNORE)

    def test_interrupted_prelaunch_does_not_spawn(self) -> None:
        with mock.patch.object(gate.OWNED, "STOP", True), mock.patch.object(gate.OWNED.subprocess, "Popen") as spawn:
            with self.assertRaises(KeyboardInterrupt):
                gate.OWNED.run_owned("blocked", ["cargo", "test"], {"commands": []}, {})
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
