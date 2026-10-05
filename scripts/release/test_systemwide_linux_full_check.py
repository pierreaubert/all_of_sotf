"""Supervisor and inventory guards for the isolated systemwide Linux recipes."""

from __future__ import annotations

import os
import hashlib
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

    def test_qa_inventory_requires_positive_at_most_one_ignored(self) -> None:
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured;"]),
            (True, 0),
        )
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 failed; 1 ignored; 0 measured;"]),
            (True, 1),
        )
        self.assertEqual(
            gate.positive_qa_inventory(["test result: ok. 5 passed; 0 failed; 2 ignored; 0 measured;"]),
            (False, 2),
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

    def test_generated_receipt_binds_exact_sources_commands_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(dir=gate.ROOT / "target") as directory:
            evidence = Path(directory)
            artifacts = evidence / "generated-artifacts"
            artifacts.mkdir()
            entries = []
            for mode in ("iir", "fir", "mixed"):
                name = f"dsp_{mode}.json"
                data = f'{{"mode":"{mode}"}}'.encode()
                (artifacts / name).write_bytes(data)
                entries.append({"name": name, "bytes": len(data),
                                "sha256": hashlib.sha256(data).hexdigest()})
            (evidence / "systemwide-graph.log").write_text(
                "test plugin_artifact::tests::all_generated_room_eq_files_build_graphs ... ok\n"
                "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured;\n"
            )
            current = {"sotf-systemwide": {"revision": "abc", "dirty": False,
                                            "lock_sha256": "lock", "nested_lock_sha256": None}}
            layout = {"missing": [], "unexpected": []}
            manifest = b"pinned manifest"
            receipt = {"status": "PASS", "root_revision": "root",
                       "sources_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                       "source_issues": [], "root_layout_before": layout,
                       "root_layout_after": layout, "sources_before": current,
                       "sources_after": current, "artifacts": entries,
                       "commands": [{"name": name, "status": "PASS", "exit_code": 0,
                                     "cleanup_ok": True, "owned_group_survivors": []}
                                    for name in ("generate-iir", "generate-fir",
                                                 "generate-mixed", "systemwide-graph")]}
            self.assertEqual(gate.generated_coverage(
                receipt, current, "root", manifest, layout, evidence), [])
            receipt["sources_after"] = {"sotf-systemwide": dict(current["sotf-systemwide"],
                                                       lock_sha256="different")}
            self.assertTrue(gate.generated_coverage(
                receipt, current, "root", manifest, layout, evidence))
            receipt["sources_after"] = current
            (artifacts / "dsp_fir.json").write_bytes(b"changed")
            self.assertTrue(gate.generated_coverage(
                receipt, current, "root", manifest, layout, evidence))


if __name__ == "__main__":
    unittest.main()
