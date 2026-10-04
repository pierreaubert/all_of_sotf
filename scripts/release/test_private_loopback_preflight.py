"""Disposable Gitea supervision regressions for the private PCM preflight."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import private_loopback_preflight as lane


class PrivateLoopbackSupervisorTests(unittest.TestCase):
    def test_owned_group_descendant_is_terminated_and_reaped(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("Linux child subreaper contract")
        lane.become_subreaper()
        child = subprocess.Popen(
            [sys.executable, "-c", "import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])"],
            start_new_session=True,
        )
        record: dict = {}
        try:
            child.wait()
            # The adopted descendant remains in the child's owned process group.
            self.assertTrue(any(item["pid"] != child.pid for item in lane.members(child.pid)))
            self.assertTrue(lane.stop_group(child, record), record)
            self.assertEqual(record["survivors"], [])
            self.assertTrue(record.get("reaped_descendants"), record)
        finally:
            lane.stop_group(child, {})

    def test_initial_source_failure_still_writes_terminal_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            with mock.patch.object(sys, "argv", ["private_loopback_preflight.py", str(output)]), \
                 mock.patch.object(lane, "source_state", side_effect=[RuntimeError("initial snapshot failed"), {}]):
                self.assertNotEqual(lane.main(), 0)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("initial snapshot failed" in error for error in report["issues"]))
            self.assertTrue((output / "sources-after.json").exists())

    def test_final_source_failure_still_writes_terminal_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            with mock.patch.object(sys, "argv", ["private_loopback_preflight.py", str(output)]), \
                 mock.patch.object(lane, "source_state", side_effect=[{}, RuntimeError("final snapshot failed")]), \
                 mock.patch.object(lane, "source_issues", return_value=[]), \
                 mock.patch.object(lane, "become_subreaper", side_effect=RuntimeError("preflight setup failed")):
                self.assertNotEqual(lane.main(), 0)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("final snapshot failed" in error for error in report["issues"]))

    def test_interrupted_owned_command_records_group_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            commands: list[dict] = []
            active: list[dict] = []
            process = mock.Mock(pid=os.getpid())
            process.poll.return_value = None
            process.wait.side_effect = KeyboardInterrupt("test interrupt")
            with mock.patch.object(lane.subprocess, "Popen", return_value=process), \
                 mock.patch.object(lane, "stop_group", return_value=True) as cleanup:
                result = lane.owned_command(["example"], {}, output / "command.log", commands, active)
            self.assertEqual(result["exit_code"], 130)
            self.assertTrue(result["interrupted"])
            self.assertTrue(result["cleanup_ok"])
            self.assertEqual(commands, [result])
            self.assertTrue(active[0]["cleanup_ok"])
            cleanup.assert_called_once()
            self.assertTrue((output / "owned-process-groups.json").exists())


if __name__ == "__main__":
    unittest.main()
