"""Guard regressions for the AUD132 scalar diagnostic runner."""

from pathlib import Path
import os
import signal
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts.release import aud132_scalar_hr_check as gate


class Aud132ScalarGuardTests(unittest.TestCase):
    def test_named_inventory_accepts_only_exact_single_golden_test(self) -> None:
        ok = (
            "test module::aud132_preserves_small_fft_and_512_pre_edit_full_output_controls ... ok\n"
            "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 1 filtered out\n"
        )
        failed = ok.replace(" ... ok", " ... FAILED").replace(
            "ok. 1 passed; 0 failed", "FAILED. 0 passed; 1 failed"
        )
        self.assertTrue(gate.positive_inventory(ok))
        self.assertTrue(gate.positive_inventory(failed, allow_golden_failure=True))
        self.assertFalse(gate.positive_inventory(failed))
        self.assertFalse(gate.positive_inventory(ok.replace("0 ignored", "1 ignored")))
        self.assertFalse(gate.positive_inventory(ok.replace(
            "aud132_preserves_small_fft_and_512_pre_edit_full_output_controls",
            "unrelated_test")))

    def test_output_requires_nonempty_finite_f32_samples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "full.f32le"
            for raw in (b"", b"\x00", struct.pack("<f", float("nan")),
                        struct.pack("<f", float("inf"))):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    gate.validate_output(path)
            path.write_bytes(struct.pack("<ff", 0.0, -0.25))
            gate.validate_output(path)

    def test_compare_rejects_missing_six_capture_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "missing comparison capture"):
                gate.compare_outputs(Path(directory), {})

    def test_prelaunch_signal_prevents_cargo_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            report = {"cases": []}
            with patch.object(gate, "STOP", True), patch.object(gate.subprocess, "Popen") as spawn:
                with self.assertRaises(KeyboardInterrupt):
                    gate.run_case("native", output, None, False, False, report)
                spawn.assert_not_called()
            self.assertEqual(report["cases"][0]["status"], "INTERRUPTED_BEFORE_LAUNCH")

    def test_actual_sigterm_reaps_owned_group_and_preserves_report(self) -> None:
        gate.enable_subreaper()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "cargo"
            ready = root / "ready"
            graceful = root / "graceful"
            descendant_ready = root / "descendant-ready"
            descendant_graceful = root / "descendant-graceful"
            binary.write_text(
                "#!/usr/bin/env python3\n"
                "import os, signal, subprocess, sys, time\n"
                "from pathlib import Path\n"
                "def stop(_signum, _frame):\n"
                "    Path(os.environ['AUD132_GRACEFUL']).write_text('stopped')\n"
                "    raise SystemExit(0)\n"
                "signal.signal(signal.SIGTERM, stop)\n"
                "program = \"import os, signal, time; from pathlib import Path; def_stop = lambda *_: (Path(os.environ['AUD132_DESC_GRACEFUL']).write_text('stopped'), os._exit(0)); signal.signal(signal.SIGTERM, def_stop); Path(os.environ['AUD132_DESC_READY']).write_text('ready'); time.sleep(60)\"\n"
                "subprocess.Popen([sys.executable, '-c', program])\n"
                "while not Path(os.environ['AUD132_DESC_READY']).exists(): time.sleep(0.01)\n"
                "Path(os.environ['AUD132_READY']).write_text('ready')\n"
                "while True: time.sleep(1)\n"
            )
            binary.chmod(0o755)
            report = {"cases": []}
            previous = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, gate.interrupted)

            def signal_when_ready() -> None:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not ready.exists():
                    time.sleep(0.01)
                os.kill(os.getpid(), signal.SIGTERM)

            worker = threading.Thread(target=signal_when_ready)
            worker.start()
            try:
                with patch.dict(os.environ, {"PATH": f"{root}:{os.environ['PATH']}",
                                             "AUD132_READY": str(ready),
                                             "AUD132_GRACEFUL": str(graceful),
                                             "AUD132_DESC_READY": str(descendant_ready),
                                             "AUD132_DESC_GRACEFUL": str(descendant_graceful)}):
                    with self.assertRaises(ValueError):
                        gate.run_fork_contract(root, root, report)
            finally:
                worker.join(timeout=6)
                signal.signal(signal.SIGTERM, previous)
                gate.STOP = False
            self.assertTrue(ready.exists(), "child never installed its TERM handler")
            self.assertEqual(graceful.read_text(), "stopped")
            self.assertEqual(descendant_graceful.read_text(), "stopped")
            self.assertTrue(report["cases"][0]["cleanup"]["ok"])
            self.assertEqual(report["cases"][0]["cleanup"]["remaining"], [])
            self.assertEqual(report["cases"][0]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
