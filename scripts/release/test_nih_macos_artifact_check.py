"""Supervision and artifact regressions for the macOS NIH plugin lane."""

from __future__ import annotations

import copy
import hashlib
import json
import plistlib
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from scripts.release import nih_macos_artifact_check as gate


class NativeNihArtifactTests(unittest.TestCase):
    def state(self) -> dict:
        return {
            "root_revision": "root-sha",
            "manifest_sha256": "sources-hash",
            "root_layout": {"unexpected": [], "missing": [], "allowed_siblings": [],
                            "tracked_gitlinks": ["sotf-daw"]},
            "workspaces": {"sotf-daw": {"revision": "daw-sha", "dirty": False,
                                         "lock_sha256": "original", "captured_at": "first"}},
        }

    def test_timestamp_change_allowed_but_canonical_lock_change_rejected(self) -> None:
        before = self.state()
        after = copy.deepcopy(before)
        after["workspaces"]["sotf-daw"]["captured_at"] = "second"
        self.assertEqual(gate.source_errors(before, after, {"sotf-daw": "daw-sha"}), [])
        after["workspaces"]["sotf-daw"]["lock_sha256"] = "changed"
        self.assertIn("sotf-daw: Cargo.lock changed",
                      gate.source_errors(before, after, {"sotf-daw": "daw-sha"}))

    def test_missing_canonical_lock_hash_is_rejected(self) -> None:
        before = self.state()
        before["workspaces"]["sotf-daw"]["lock_sha256"] = None
        self.assertIn("before: sotf-daw canonical Cargo.lock hash is missing",
                      gate.source_errors(before, copy.deepcopy(before), {"sotf-daw": "daw-sha"}))

    def test_missing_nested_autoeq_lock_hash_is_rejected(self) -> None:
        before = self.state()
        before["root_layout"]["tracked_gitlinks"].append("autoeq")
        before["workspaces"]["autoeq"] = {"revision": "autoeq-sha", "dirty": False,
                                           "lock_sha256": "autoeq-lock", "nested_lock_sha256": None}
        pins = {"sotf-daw": "daw-sha", "autoeq": "autoeq-sha"}
        self.assertIn("before: AutoEQ nested demo Cargo.lock hash is missing",
                      gate.source_errors(before, copy.deepcopy(before), pins))

    def test_artifact_inventory_rejects_missing_feature_duplicate_validator_and_hash_tamper(self) -> None:
        features = ["eq", *(f"fixture-{index}" for index in range(42))]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            logs = output / "logs"
            logs.mkdir()
            for kind, label in (("vst3", "VST3"), ("clap", "CLAP")):
                (logs / f"{kind}-build.log").write_text(
                    f"Built 43/43 plugins in dist/nih/ (0 failed)\nBundled 43 {label} plugins\n"
                )
                (logs / f"nih-{kind}-features").mkdir()
            staged = output / "artifacts/sotf-daw/dist"
            clap = staged / "clap"
            vst3 = staged / "vst3"
            clap.mkdir(parents=True)
            vst3.mkdir()
            for feature in features:
                (logs / "nih-vst3-features" / f"{feature}.log").write_text(f"Built {feature}\n")
                (logs / "nih-clap-features" / f"{feature}.log").write_text(f"Built {feature}\n")
                (clap / f"sotf_{feature.replace('-', '_')}.clap").write_bytes(feature.encode())
                name = gate.vst3_name(feature)
                bundle = vst3 / f"{name}.vst3/Contents/MacOS"
                bundle.mkdir(parents=True)
                binary_name = "sotf_" + feature.replace("-", "_")
                (bundle / binary_name).write_bytes(feature.encode())
                (bundle.parent / "Info.plist").write_bytes(
                    plistlib.dumps({"CFBundleExecutable": binary_name})
                )
            for kind, names in (("clap", sorted(path.stem for path in clap.glob("*.clap"))),
                                ("vst3", sorted(path.stem for path in vst3.glob("*.vst3")))):
                folder = logs / f"{kind}-validators"
                folder.mkdir()
                lines = ["plugin\texit_code\tlog"]
                for name in names:
                    transcript = folder / f"{name}.log"
                    transcript.write_text("validator PASS\n")
                    lines.append(f"{name}\t0\t{transcript}")
                (folder / "results.tsv").write_text("\n".join(lines) + "\n")
                (logs / f"{kind}-validate.log").write_text(f"{kind} validation: 43 passed, 0 failed of 43\n")
            records = []
            for path in sorted((output / "artifacts").rglob("*")):
                if path.is_file():
                    records.append({"path": str(path.relative_to(output)), "size": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            (output / "artifact-inventory.json").write_text(json.dumps(records))
            with mock.patch.object(gate, "OUTPUT", output):
                self.assertEqual(gate.artifact_results(features)["clap"]["count"], 43)
                missing_log = logs / "nih-vst3-features/eq.log"
                missing_log.unlink()
                with self.assertRaisesRegex(ValueError, "NIH build logs differ"):
                    gate.artifact_results(features)
                missing_log.write_text("Built eq\n")
                results = logs / "clap-validators/results.tsv"
                original = results.read_text()
                results.write_text(original + original.splitlines()[1] + "\n")
                with self.assertRaisesRegex(ValueError, "incomplete or failing"):
                    gate.artifact_results(features)
                results.write_text(original)
                (clap / "sotf_eq.clap").write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "size or SHA256 differs"):
                    gate.artifact_results(features)
                (clap / "sotf_eq.clap").write_bytes(b"eq")
                original_bundle = vst3 / "SOTF Eq.vst3"
                renamed_bundle = vst3 / "SOTF Unlisted.vst3"
                original_bundle.rename(renamed_bundle)
                with self.assertRaisesRegex(ValueError, "exact NIH feature mapping"):
                    gate.artifact_results(features)

    def test_stop_before_launch_does_not_spawn(self) -> None:
        with mock.patch.object(gate, "STOP", True), mock.patch.object(gate.subprocess, "Popen") as spawn:
            with self.assertRaises(KeyboardInterrupt):
                gate.run_owned("not-started", [sys.executable, "-c", "pass"], {"commands": []}, {})
        spawn.assert_not_called()

    def test_zero_exit_leader_reaps_owned_descendant(self) -> None:
        command = (
            "import subprocess,sys; "
            "subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']); "
            "print('DESCENDANT READY',flush=True)"
        )
        gate.enable_subreaper()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "logs").mkdir()
            report: dict = {"commands": []}
            with mock.patch.object(gate, "OUTPUT", output), mock.patch.object(gate, "STOP", False):
                result = gate.run_owned("owned", [sys.executable, "-c", command], report, {})
            self.assertIn("DESCENDANT READY", (output / "logs/owned.log").read_text())
            self.assertEqual(result["exit_code"], 0)
            self.assertTrue(result["owned_group_cleanup"]["ok"])
            self.assertEqual(result["owned_group_cleanup"]["remaining"], [])

    def test_sigterm_after_both_ready_markers_stops_group_and_next_launch(self) -> None:
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
                    "signal-owned", [sys.executable, "-c", parent_code], report, {}
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
                self.assertTrue(
                    result["command"]["owned_group_cleanup"]["ok"],
                    result["command"]["owned_group_cleanup"],
                )
                self.assertEqual(result["command"]["owned_group_cleanup"]["remaining"], [])
                self.assertEqual(result["command"]["status"], "FAIL")
                with mock.patch.object(gate.subprocess, "Popen") as spawn:
                    with self.assertRaises(KeyboardInterrupt):
                        gate.run_owned("not-launched", [sys.executable, "-c", "pass"], report, {})
                    spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
