"""Exercise the owned-group cleanup contract before long all-feature checks."""

import ctypes
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.release import all_features_candidate_check as gate


class SupervisionTests(unittest.TestCase):
    def test_stop_before_run_does_not_launch(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(gate, "STOP", True), \
             mock.patch.object(gate.subprocess, "Popen") as spawn:
            with self.assertRaises(KeyboardInterrupt):
                gate.run("stopped", ["cargo", "check"], Path(directory))
            spawn.assert_not_called()
            self.assertFalse((Path(directory) / "stopped.log").exists())

    def test_stop_after_log_open_does_not_launch(self):
        original_open = Path.open

        def stop_when_log_opens(path, *args, **kwargs):
            if path.name == "stopped.log":
                gate.STOP = True
            return original_open(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(gate, "STOP", False), \
             mock.patch.object(Path, "open", stop_when_log_opens), \
             mock.patch.object(gate.subprocess, "Popen") as spawn:
            with self.assertRaises(KeyboardInterrupt):
                gate.run("stopped", ["cargo", "check"], Path(directory))
            spawn.assert_not_called()

    def test_owned_descendant_is_reaped(self):
        previous = ctypes.c_int()
        libc = ctypes.CDLL(None, use_errno=True) if sys.platform == "linux" else None
        if libc is not None:
            self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)
            self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        parent_tail = "" if libc is not None else "time.sleep(60)"
        child = subprocess.Popen(
            [sys.executable, "-c", "import subprocess,time; p=subprocess.Popen(['sleep','60']); "
             "print(p.pid,flush=True); " + parent_tail],
            stdout=subprocess.PIPE, text=True, start_new_session=True)
        try:
            self.assertTrue(child.stdout.readline().strip().isdigit())
            if libc is not None:
                self.assertEqual(child.wait(), 0, "parent must exit and leave an adopted descendant")
            result = {}
            self.assertTrue(gate.cleanup(child, result), result)
            self.assertEqual(result["survivors"], [])
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            if libc is not None:
                self.assertEqual(libc.prctl(36, previous.value, 0, 0, 0), 0)

    def test_inspection_failure_is_not_accepted_as_cleanup(self):
        child = mock.Mock(pid=987654321)
        child.returncode = 0
        child.poll.return_value = 0
        with mock.patch.object(gate, "members", side_effect=OSError("ps unavailable")), \
             mock.patch.object(gate.os, "killpg"):
            result = {}
            self.assertFalse(gate.cleanup(child, result))
            self.assertTrue(result["cleanup_errors"])


if __name__ == "__main__":
    unittest.main()
