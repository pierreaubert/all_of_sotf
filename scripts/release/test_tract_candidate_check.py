"""Gitea-only supervisor regressions for tract candidate qualification."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from unittest import mock

from scripts.release import tract_candidate_check as gate


class SupervisorTests(unittest.TestCase):
    def test_malformed_process_inventory_fails_closed(self) -> None:
        with mock.patch.object(
            gate.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, stdout="42 ?? 42 S\n", stderr=""),
        ):
            with self.assertRaisesRegex(ValueError, "unparseable process inventory"):
                gate.members(42)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux subreaper proof")
    def test_owned_group_leader_exit_reaps_spawned_descendant(self) -> None:
        gate.enable_subreaper()
        leader = subprocess.Popen(
            [sys.executable, "-c", "import subprocess,sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])"],
            start_new_session=True,
        )
        try:
            leader.wait(timeout=5)
            deadline = time.monotonic() + 5
            while not gate.members(leader.pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(gate.members(leader.pid), "descendant never entered owned process group")
            result = gate.cleanup(leader)
            self.assertTrue(result["ok"], result)
            self.assertEqual(gate.members(leader.pid), [])
        finally:
            try:
                os.killpg(leader.pid, 9)
            except ProcessLookupError:
                pass
            leader.wait(timeout=5)

    def test_inspection_failure_is_red_even_if_group_is_gone(self) -> None:
        leader = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        leader.wait(timeout=5)
        actual = gate.members
        calls = 0

        def flaky(pgid: int) -> list[dict[str, str]]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("process inventory failed")
            return actual(pgid)

        with mock.patch.object(gate, "members", side_effect=flaky):
            result = gate.cleanup(leader)
        self.assertFalse(result["ok"])
        self.assertTrue(any("inventory failed" in error for error in result["errors"]))
