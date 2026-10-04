"""Supervisor proofs for the Mac CoreAudio fork qualification lane."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from scripts.release import coreaudio_fork_check as gate


class SupervisorTests(unittest.TestCase):
    def test_malformed_process_inventory_fails_closed(self) -> None:
        with mock.patch.object(
            gate.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, stdout="42 ?? 42 S\n", stderr=""),
        ):
            with self.assertRaisesRegex(ValueError, "unparseable process inventory"):
                gate.members(42)

    def test_leader_exit_still_cleans_owned_descendant(self) -> None:
        leader = subprocess.Popen(
            [sys.executable, "-c", "import subprocess,sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])"],
            start_new_session=True,
        )
        try:
            leader.wait(timeout=5)
            result = gate.cleanup(leader)
            self.assertTrue(result["ok"], result)
            self.assertEqual(gate.members(leader.pid), [])
        finally:
            try:
                os.killpg(leader.pid, 9)
            except ProcessLookupError:
                pass
            leader.wait(timeout=5)

    def test_repeated_signal_requests_stop_and_reaps_command_group(self) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                ready = directory / "ready"
                graceful = directory / "graceful"
                child_code = (
                    "import pathlib,signal,sys,time\n"
                    "ready,graceful=map(pathlib.Path,sys.argv[1:3])\n"
                    "def stop(_signum,_frame):\n"
                    "    graceful.write_text('terminated')\n"
                    "    raise SystemExit(0)\n"
                    "signal.signal(signal.SIGTERM,stop)\n"
                    "ready.write_text('ready')\n"
                    "while True: time.sleep(0.1)\n"
                )
                gate.INTERRUPTED = False
                previous = signal.signal(signum, gate.interrupt)

                def signal_ready_command() -> None:
                    deadline = time.monotonic() + 5
                    while not ready.is_file() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    os.kill(os.getpid(), signum)

                timer = threading.Thread(target=signal_ready_command)
                try:
                    timer.start()
                    result = gate.command("interrupted", [sys.executable, "-c", child_code,
                                                          str(ready), str(graceful)],
                                          directory, directory)
                    self.assertTrue(ready.is_file(), "child did not install its signal handler")
                    self.assertEqual(result["status"], "FAIL")
                    self.assertTrue(result["cleanup"]["ok"], result)
                    self.assertEqual(gate.members(result["owned_pgid"]), [])
                    self.assertEqual(graceful.read_text(), "terminated")
                    gate.interrupt(signum, None)
                    with mock.patch.object(gate.subprocess, "Popen",
                                           side_effect=AssertionError("launched after stop")):
                        next_result = gate.command("must-not-launch", ["false"], directory, directory)
                    self.assertTrue(next_result["not_started"])
                finally:
                    timer.join(timeout=6)
                    signal.signal(signum, previous)
                    gate.INTERRUPTED = False
