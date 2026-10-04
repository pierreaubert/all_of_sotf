"""Owned-process and source guard checks for the realfft lock resolver."""

from pathlib import Path
import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts.release import realfft_lock_resolve as resolver


class RealfftLockResolverTests(unittest.TestCase):
    def test_prelaunch_stop_never_starts_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(resolver, "STOP", True), patch.object(resolver.subprocess, "Popen") as spawn:
                with self.assertRaises(KeyboardInterrupt):
                    resolver.run("no-launch", ["cargo", "metadata"], output, output,
                                 {"commands": []})
                spawn.assert_not_called()

    def test_sigterm_reaps_ready_parent_and_descendant(self) -> None:
        resolver.enable_subreaper()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            parent_ready = output / "parent-ready"
            child_ready = output / "child-ready"
            parent_stopped = output / "parent-stopped"
            child_stopped = output / "child-stopped"
            script = output / "owned.py"
            script.write_text(
                "import os, signal, subprocess, sys, time\n"
                "from pathlib import Path\n"
                "def stop(_signum, _frame):\n"
                "    Path(os.environ['PARENT_STOPPED']).write_text('yes')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                "program = (\"import os, signal, time; from pathlib import Path; \"
                "\"stop = lambda *_: (Path(os.environ['CHILD_STOPPED']).write_text('yes'), os._exit(0)); \"
                "\"signal.signal(signal.SIGTERM, stop); \"
                "\"Path(os.environ['CHILD_READY']).write_text('yes'); time.sleep(60)\")\n"
                "subprocess.Popen([sys.executable, '-c', program])\n"
                "while not Path(os.environ['CHILD_READY']).exists(): time.sleep(0.01)\n"
                "Path(os.environ['PARENT_READY']).write_text('yes')\n"
                "while True: time.sleep(1)\n"
            )
            report = {"commands": []}
            previous = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, resolver.interrupted)

            def signal_when_ready() -> None:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not parent_ready.exists():
                    time.sleep(0.01)
                os.kill(os.getpid(), signal.SIGTERM)

            worker = threading.Thread(target=signal_when_ready)
            worker.start()
            try:
                with patch.dict(os.environ, {
                    "PARENT_READY": str(parent_ready), "CHILD_READY": str(child_ready),
                    "PARENT_STOPPED": str(parent_stopped), "CHILD_STOPPED": str(child_stopped),
                }):
                    with self.assertRaises(ValueError):
                        resolver.run("signal", [sys.executable, str(script)], output, output, report)
            finally:
                worker.join(timeout=6)
                signal.signal(signal.SIGTERM, previous)
                resolver.STOP = False
            self.assertTrue(parent_ready.exists())
            self.assertTrue(child_ready.exists())
            self.assertEqual(parent_stopped.read_text(), "yes")
            self.assertEqual(child_stopped.read_text(), "yes")
            self.assertTrue(report["commands"][0]["cleanup"]["ok"])
            self.assertEqual(report["commands"][0]["cleanup"]["remaining"], [])


if __name__ == "__main__":
    unittest.main()
