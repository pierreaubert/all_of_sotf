"""Preflight generated RoomEQ command stopping and owned-process cleanup."""

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

from scripts.release import generated_roomeq_check as gate


class ProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = signal.getsignal(signal.SIGTERM)
        self.interrupted = gate.INTERRUPTED
        gate.INTERRUPTED = False

    def tearDown(self) -> None:
        signal.signal(signal.SIGTERM, self.previous)
        gate.INTERRUPTED = self.interrupted

    def test_stop_before_launch(self) -> None:
        gate.INTERRUPTED = True
        with patch.object(gate.subprocess, "Popen") as launch:
            with self.assertRaises(KeyboardInterrupt):
                gate.run("blocked", [sys.executable, "-c", "pass"], Path.cwd(),
                         Path("unused.log"), os.environ.copy(), {"commands": []},
                         Path("unused-report.json"))
            launch.assert_not_called()

    def test_real_signal_stops_ready_parent_and_descendant(self) -> None:
        gate.enable_subreaper()
        target = gate.ROOT / "target/release-gitea"
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="roomeq-supervision-", dir=target) as directory:
            evidence = Path(directory)
            ready = evidence / "parent-ready"
            child_ready = evidence / "child-ready"
            stopped = evidence / "parent-stopped"
            child_stopped = evidence / "child-stopped"
            script = evidence / "owned.py"
            script.write_text(
                "import os, signal, subprocess, sys, time\n"
                "from pathlib import Path\n"
                "child = None\n"
                "def stop(*_):\n"
                "    Path(os.environ['PARENT_STOPPED']).write_text('yes')\n"
                "    child.wait(timeout=5)\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                "program = (\"import os, signal, time; from pathlib import Path; \"\n"
                "\"stop = lambda *_: (Path(os.environ['CHILD_STOPPED']).write_text('yes'), os._exit(0)); \"\n"
                "\"signal.signal(signal.SIGTERM, stop); \"\n"
                "\"Path(os.environ['CHILD_READY']).write_text('yes'); time.sleep(60)\")\n"
                "child = subprocess.Popen([sys.executable, '-c', program])\n"
                "while not Path(os.environ['CHILD_READY']).exists(): time.sleep(0.01)\n"
                "Path(os.environ['PARENT_READY']).write_text('yes')\n"
                "while True: time.sleep(1)\n"
            )
            env = os.environ.copy()
            env.update({"PARENT_READY": str(ready), "CHILD_READY": str(child_ready),
                        "PARENT_STOPPED": str(stopped), "CHILD_STOPPED": str(child_stopped)})
            signal.signal(signal.SIGTERM, lambda *_: setattr(gate, "INTERRUPTED", True))

            def signal_when_ready() -> None:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not ready.is_file():
                    time.sleep(0.01)
                os.kill(os.getpid(), signal.SIGTERM)

            sender = threading.Thread(target=signal_when_ready)
            sender.start()
            try:
                entry = gate.run("owned", [sys.executable, str(script)], evidence,
                                 evidence / "owned.log", env, {"commands": []},
                                 evidence / "report.json")
            finally:
                sender.join(timeout=6)
            self.assertTrue(ready.is_file())
            self.assertTrue(child_ready.is_file())
            self.assertTrue(stopped.is_file())
            self.assertTrue(child_stopped.is_file())
            self.assertEqual(entry["status"], "FAIL")
            self.assertEqual(entry["exit_code"], 130)
            self.assertTrue(entry["cleanup_ok"])
            self.assertEqual(entry["owned_group_survivors"], [])


if __name__ == "__main__":
    unittest.main()
