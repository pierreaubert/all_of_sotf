"""Exercise the owned-group cleanup contract before focused DSP checks."""

import ctypes
import os
import signal
import subprocess
import sys
import unittest
from unittest import mock

from scripts.release import f64_fractional_nih_check as gate


class SupervisionTests(unittest.TestCase):
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
        with mock.patch.object(gate, "group_members", side_effect=OSError("ps unavailable")), \
             mock.patch.object(gate.os, "killpg"):
            result = {}
            self.assertFalse(gate.cleanup(child, result))
            self.assertTrue(result["cleanup_errors"])


if __name__ == "__main__":
    unittest.main()
