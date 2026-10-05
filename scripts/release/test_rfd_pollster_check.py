"""Focused supervisor and source-guard checks for the Linux portal lane."""

from __future__ import annotations

import copy
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from scripts.release import rfd_pollster_check as gate


class NativeDialogGateTests(unittest.TestCase):
    def snapshot(self) -> dict:
        return {
            "root_revision": "root-sha",
            "manifest_sha256": "manifest-hash",
            "root_layout": {"unexpected": [], "missing": [], "allowed_siblings": [],
                            "tracked_gitlinks": ["sotf"]},
            "workspaces": {
                "sotf": {
                    "revision": "sotf-sha",
                    "dirty": False,
                    "lock_sha256": "original-lock",
                    "captured_at": "first-observation",
                }
            },
        }

    def test_timestamp_only_source_snapshot_change_is_accepted(self) -> None:
        before = self.snapshot()
        after = copy.deepcopy(before)
        after["workspaces"]["sotf"]["captured_at"] = "second-observation"
        self.assertEqual(gate.source_errors(before, after, {"sotf": "sotf-sha"}), [])

    def test_changed_canonical_lock_is_rejected(self) -> None:
        before = self.snapshot()
        after = copy.deepcopy(before)
        after["workspaces"]["sotf"]["lock_sha256"] = "changed-lock"
        self.assertIn("sotf: Cargo.lock changed", gate.source_errors(before, after, {"sotf": "sotf-sha"}))

    def test_stop_before_launch_does_not_spawn_process(self) -> None:
        report = {"commands": []}
        with mock.patch.object(gate, "STOP", True), mock.patch.object(gate.subprocess, "Popen") as spawn:
            with self.assertRaises(KeyboardInterrupt):
                gate.run_owned("must-not-start", [sys.executable, "-c", "pass"], report)
        spawn.assert_not_called()
        self.assertEqual(report["commands"], [])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux subreaper owns adopted descendants")
    def test_zero_exit_parent_with_ready_descendant_is_reaped(self) -> None:
        code = (
            "import subprocess,sys; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']); "
            "print('READY parent exited with descendant', flush=True)"
        )
        gate.enable_subreaper()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "logs").mkdir()
            report: dict = {"commands": []}
            with mock.patch.object(gate, "OUTPUT", output), mock.patch.object(gate, "STOP", False):
                result = gate.run_owned("owned-descendant", [sys.executable, "-c", code], report)
            self.assertIn("READY parent exited with descendant", (output / "logs/owned-descendant.log").read_text())
            self.assertEqual(result["exit_code"], 0)
            self.assertTrue(result["owned_group_cleanup"]["ok"])
            self.assertEqual(result["owned_group_cleanup"]["remaining"], [])
            self.assertEqual(result["status"], "PASS")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux signal and subreaper contract")
    def test_sigterm_after_both_ready_markers_stops_owned_group_and_next_launch(self) -> None:
        child_code = (
            "import signal,sys; "
            "signal.signal(signal.SIGTERM, lambda *_: (print('CHILD TERM',flush=True),sys.exit(0))); "
            "print('CHILD READY',flush=True); signal.pause()"
        )
        parent_code = (
            "import signal,subprocess,sys; "
            f"child=subprocess.Popen([sys.executable,'-c',{child_code!r}])\n"
            "def stop(*_): print('PARENT TERM',flush=True); child.wait(timeout=5); sys.exit(0)\n"
            "signal.signal(signal.SIGTERM,stop); print('PARENT READY',flush=True); child.wait()"
        )
        gate.enable_subreaper()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "logs").mkdir()
            report: dict = {"commands": []}
            result: dict = {}

            def exercise() -> None:
                result["command"] = gate.run_owned(
                    "signal-owned", [sys.executable, "-c", parent_code], report
                )

            with mock.patch.object(gate, "OUTPUT", output), mock.patch.object(gate, "STOP", False):
                worker = threading.Thread(target=exercise, daemon=True)
                worker.start()
                log = output / "logs/signal-owned.log"
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    body = log.read_text() if log.exists() else ""
                    if "PARENT READY" in body and "CHILD READY" in body:
                        break
                    time.sleep(0.05)
                else:
                    gate.STOP = True
                    worker.join(timeout=20)
                    self.fail("parent and descendant did not both signal readiness")
                prior = signal.signal(signal.SIGTERM, gate.interrupted)
                try:
                    os.kill(os.getpid(), signal.SIGTERM)
                finally:
                    signal.signal(signal.SIGTERM, prior)
                worker.join(timeout=20)
                self.assertFalse(worker.is_alive(), "owned supervisor must finish after SIGTERM")
                body = log.read_text()
                self.assertIn("PARENT TERM", body)
                self.assertIn("CHILD TERM", body)
                self.assertEqual(result["command"]["owned_group_cleanup"]["remaining"], [])
                self.assertTrue(result["command"]["owned_group_cleanup"]["ok"])
                self.assertEqual(result["command"]["status"], "FAIL")
                with mock.patch.object(gate.subprocess, "Popen") as spawn:
                    with self.assertRaises(KeyboardInterrupt):
                        gate.run_owned("not-launched", [sys.executable, "-c", "pass"], report)
                    spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
