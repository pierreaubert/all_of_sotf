"""Bounded inventory retries and cleanup restricted to owned process groups."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from scripts.release import process_supervision as supervision


class ProcessInventoryTests(unittest.TestCase):
    def test_timeout_then_authoritative_empty_inventory(self):
        with patch.object(supervision.subprocess, "run", side_effect=[
            subprocess.TimeoutExpired("ps", 5),
            subprocess.CompletedProcess("ps", 0, "", ""),
        ]) as run:
            self.assertEqual(supervision.members(123), [])
            self.assertEqual(run.call_count, 2)

    def test_timeout_exhaustion_is_failure(self):
        with patch.object(supervision.subprocess, "run", side_effect=
                          subprocess.TimeoutExpired("ps", 5)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                supervision.members(123)
            self.assertEqual(run.call_count, 3)

    def test_malformed_inventory_is_failure_without_retry(self):
        with patch.object(supervision.subprocess, "run", return_value=
                          subprocess.CompletedProcess("ps", 0, "garbage\n", "")) as run:
            with self.assertRaises(ValueError):
                supervision.members(123)
            self.assertEqual(run.call_count, 1)

    def test_inventory_contains_only_owned_group(self):
        with patch.object(supervision.subprocess, "run", return_value=
                          subprocess.CompletedProcess(
                              "ps", 0, "1 0 1 S\n123 1 123 S\n124 123 123 Z\n", "")):
            self.assertEqual([row["pid"] for row in supervision.members(123)],
                             ["123", "124"])

    def test_hard_inventory_error_is_failure_without_retry(self):
        with patch.object(supervision.subprocess, "run", side_effect=
                          subprocess.CalledProcessError(1, "ps")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                supervision.members(123)
            self.assertEqual(run.call_count, 1)


class OwnedCleanupTests(unittest.TestCase):
    def child(self):
        child = Mock()
        child.pid = 123
        child.poll.return_value = 0
        child.wait.return_value = 0
        return child

    def test_empty_group_never_receives_signal(self):
        with (patch.object(supervision.sys, "platform", "darwin"),
              patch.object(supervision.subprocess, "run", return_value=
                           subprocess.CompletedProcess("ps", 0, "", "")),
              patch.object(supervision.os, "killpg") as kill):
            self.assertTrue(supervision.clean_group(self.child())["ok"])
            kill.assert_not_called()

    def test_inspection_failure_cannot_turn_into_success(self):
        with (patch.object(supervision.sys, "platform", "darwin"),
              patch.object(supervision, "members", side_effect=[
                  subprocess.TimeoutExpired("ps", 5), [], [], [],
              ]), patch.object(supervision.os, "killpg") as kill):
            result = supervision.clean_group(self.child())
            self.assertFalse(result["ok"])
            self.assertTrue(result["errors"])
            self.assertEqual(kill.call_args.args[0], 123)

    def test_owned_descendant_receives_scoped_signal(self):
        owned = [{"pid": "124", "ppid": "123", "pgid": "123", "state": "S"}]
        with (patch.object(supervision.sys, "platform", "darwin"),
              patch.object(supervision, "members", side_effect=[owned, [], [], []]),
              patch.object(supervision.os, "killpg") as kill):
            self.assertTrue(supervision.clean_group(self.child())["ok"])
            kill.assert_called_once_with(123, supervision.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
