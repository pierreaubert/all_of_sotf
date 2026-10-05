"""Preflight the NIH Gitea runner's inventory and owned-process guards."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts.release import nih_default_native_check as gate


class InventoryTests(unittest.TestCase):
    REQUIRED = {"fractional_rate_reaches_dsp"}
    PASS = "test wrapper::fractional_rate_reaches_dsp ... ok\n"

    def test_exact_positive_inventory(self) -> None:
        result = gate.parse_tests(
            self.PASS + "test result: ok. 1 passed; 0 failed; 0 ignored;\n",
            self.REQUIRED,
        )
        self.assertTrue(result["accepted"])

    def test_missing_required_name_is_rejected(self) -> None:
        output = ("test wrapper::other ... ok\n"
                  "test result: ok. 1 passed; 0 failed; 0 ignored;\n")
        self.assertFalse(gate.parse_tests(output, self.REQUIRED)["accepted"])

    def test_ignored_and_count_mismatch_are_rejected(self) -> None:
        for summary in (
            "test result: ok. 1 passed; 0 failed; 1 ignored;\n",
            "test result: ok. 2 passed; 0 failed; 0 ignored;\n",
        ):
            with self.subTest(summary=summary):
                self.assertFalse(gate.parse_tests(self.PASS + summary, self.REQUIRED)["accepted"])


class OwnedProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
        self.interrupted = gate.INTERRUPTED
        gate.INTERRUPTED = False

    def tearDown(self) -> None:
        signal.signal(signal.SIGTERM, self.previous[0])
        signal.signal(signal.SIGINT, self.previous[1])
        gate.INTERRUPTED = self.interrupted

    def test_stop_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            gate.INTERRUPTED = True
            with patch.object(gate.subprocess, "Popen") as launch:
                with self.assertRaisesRegex(RuntimeError, "before starting"):
                    gate.run_owned("blocked", [sys.executable, "-c", "pass"],
                                   evidence, evidence, {"commands": []})
                launch.assert_not_called()

    def test_real_interrupt_stops_ready_parent_and_descendant(self) -> None:
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as directory:
                evidence = Path(directory)
                ready = evidence / "ready"
                child_ready = evidence / "child-ready"
                stopped = evidence / "stopped"
                child_stopped = evidence / "child-stopped"
                script = evidence / "owned.py"
                script.write_text(
                    "import os, signal, subprocess, sys, time\n"
                    "from pathlib import Path\n"
                    "child = None\n"
                    "def stop(*_):\n"
                    "    Path(os.environ['STOPPED']).write_text('yes')\n"
                    "    child.wait(timeout=5)\n"
                    "    raise SystemExit(0)\n"
                    "signal.signal(signal.SIGTERM, stop)\n"
                    "signal.signal(signal.SIGINT, stop)\n"
                    "program = (\"import os, signal, time; from pathlib import Path; \"\n"
                    "\"def_stop = lambda *_: (Path(os.environ['CHILD_STOPPED']).write_text('yes'), os._exit(0)); \"\n"
                    "\"signal.signal(signal.SIGTERM, def_stop); signal.signal(signal.SIGINT, def_stop); \"\n"
                    "\"Path(os.environ['CHILD_READY']).write_text('yes'); time.sleep(60)\")\n"
                    "child = subprocess.Popen([sys.executable, '-c', program])\n"
                    "while not Path(os.environ['CHILD_READY']).exists(): time.sleep(0.01)\n"
                    "Path(os.environ['READY']).write_text('yes')\n"
                    "while True: time.sleep(1)\n"
                )
                values = {"READY": str(ready), "CHILD_READY": str(child_ready),
                          "STOPPED": str(stopped), "CHILD_STOPPED": str(child_stopped)}
                previous_values = {key: os.environ.get(key) for key in values}
                os.environ.update(values)
                gate.INTERRUPTED = False
                signal.signal(signum, gate.interrupt)

                def send_when_ready() -> None:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline and not ready.is_file():
                        time.sleep(0.01)
                    os.kill(os.getpid(), signum)

                sender = threading.Thread(target=send_when_ready)
                sender.start()
                try:
                    entry = gate.run_owned("interrupt", [sys.executable, str(script)],
                                           evidence, evidence, {"commands": []})
                finally:
                    sender.join(timeout=6)
                    for key, value in previous_values.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
                self.assertTrue(ready.is_file())
                self.assertTrue(child_ready.is_file())
                self.assertTrue(stopped.is_file())
                self.assertTrue(child_stopped.is_file())
                self.assertEqual(entry["status"], "FAIL")
                self.assertTrue(entry["cleanup"]["ok"])
                self.assertEqual(entry["cleanup"]["remaining"], [])


if __name__ == "__main__":
    unittest.main()
