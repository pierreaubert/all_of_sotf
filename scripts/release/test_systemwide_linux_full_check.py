"""Supervisor and inventory guards for the isolated systemwide Linux recipes."""

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

from scripts.release import systemwide_linux_full_check as gate
from scripts.release.librespot_candidate_check import enable_subreaper


class SystemwideLinuxGateTests(unittest.TestCase):
    def test_stopped_runner_does_not_launch_a_command(self) -> None:
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "target") as directory:
            output = Path(directory)
            with patch.object(gate, "STOP", True), patch.object(gate.subprocess, "Popen") as popen:
                with self.assertRaises(KeyboardInterrupt):
                    gate.run_check("stopped", [sys.executable, "-c", "pass"],
                                   output, output, {"results": []})
                popen.assert_not_called()

    def test_signal_stops_and_reaps_owned_process(self) -> None:
        enable_subreaper()
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "target") as directory:
            output = Path(directory)
            report: dict[str, object] = {"results": []}
            old_handler = signal.getsignal(signal.SIGTERM)
            ready = output / "child-ready"
            observed = threading.Event()

            def signal_after_child_ready() -> None:
                for _ in range(500):
                    if ready.is_file():
                        observed.set()
                        os.kill(os.getpid(), signal.SIGTERM)
                        return
                    time.sleep(0.01)

            sender = threading.Thread(target=signal_after_child_ready)
            try:
                signal.signal(signal.SIGTERM, lambda _number, _frame: setattr(gate, "STOP", True))
                gate.STOP = False
                sender.start()
                with self.assertRaises(KeyboardInterrupt):
                    gate.run_check("interrupted", [sys.executable, "-c",
                                   f"from pathlib import Path; Path({str(ready)!r}).write_text('ready'); "
                                   "import time; time.sleep(5)"], output, output, report)
                self.assertTrue(observed.is_set())
                entry = report["results"][0]
                self.assertEqual(entry["exit_code"], 130)
                self.assertTrue(entry["cleanup"]["ok"])
                self.assertEqual(entry["cleanup"]["remaining"], [])
            finally:
                sender.join()
                gate.STOP = False
                signal.signal(signal.SIGTERM, old_handler)

    def test_qa_inventory_requires_positive_zero_ignored(self) -> None:
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured;"]),
            (True, 0),
        )
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 failed; 1 ignored; 0 measured;"]),
            (False, 1),
        )
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 failed; 0 measured;"]),
            (False, 0),
        )
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 1 failed; 0 ignored;"]),
            (False, 0),
        )
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 ignored;"]),
            (False, 0),
        )


if __name__ == "__main__":
    unittest.main()
