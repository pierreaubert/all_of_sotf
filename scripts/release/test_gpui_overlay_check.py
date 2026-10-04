"""Check that shader ABI evidence belongs to the current Cargo build."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest

from scripts.release import gpui_overlay_check
from scripts.release.gpui_overlay_check import scene_header


def prove_signal_cleanup(module: object, signum: int) -> None:
    (module.ROOT / "target").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=module.ROOT / "target") as directory:
        output = Path(directory)
        ready, graceful, later = (output / name for name in ("ready", "graceful", "later"))
        child_code = (
            "import pathlib,signal,time; "
            f"ready=pathlib.Path({str(ready)!r}); graceful=pathlib.Path({str(graceful)!r}); "
            "signal.signal(signal.SIGTERM, lambda *_: (graceful.write_text('term'), exit(0))); "
            "ready.write_text('ready');\n"
            "while True: time.sleep(0.1)"
        )
        previous = signal.getsignal(signum)
        module.STOP_REQUESTED = False
        signal.signal(signum, module.interrupted)
        def request_stop() -> None:
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            os.kill(os.getpid(), signum)
        trigger = threading.Thread(target=request_stop, daemon=True)
        try:
            trigger.start()
            result = module.run("owned-signal", [sys.executable, "-c", child_code], output, output)
            trigger.join(timeout=12)
            assert result["exit_code"] == 130 and result["interrupted"]
            assert result["cleanup_ok"] and not result["survivors"]
            assert graceful.read_text() == "term"
            try:
                module.run("later", [sys.executable, "-c", f"open({str(later)!r}, 'w').close()"], output, output)
            except KeyboardInterrupt:
                pass
            else:
                raise AssertionError("later command ran after interruption")
            assert not later.exists()
        finally:
            signal.signal(signum, previous)
            module.STOP_REQUESTED = False


class SceneHeaderTests(unittest.TestCase):
    def test_sigint_cleans_owned_child_and_blocks_next_command(self) -> None:
        prove_signal_cleanup(gpui_overlay_check, signal.SIGINT)

    def test_sigterm_cleans_owned_child_and_blocks_next_command(self) -> None:
        prove_signal_cleanup(gpui_overlay_check, signal.SIGTERM)

    def test_current_build_output_selected_with_stale_header_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            current = target / "current" / "out"
            stale = target / "stale" / "out"
            output = root / "evidence"
            for path in (current, stale, output):
                path.mkdir(parents=True)
            valid = "typedef uint32_t PaddedBool32;\nPaddedBool32 wavy;\nPaddedBool32 grayscale;\n"
            (current / "scene.h").write_text(valid)
            (stale / "scene.h").write_text(valid)
            log = root / "cargo.log"
            log.write_text(json.dumps({
                "reason": "build-script-executed",
                "package_id": "path+file:///toolkit/gpui_macos#gpui-toolkit-gpui-macos@0.1.0",
                "out_dir": str(current),
            }) + "\n")
            self.assertEqual(scene_header(output, log, target), str((current / "scene.h").resolve()))
            self.assertEqual((output / "scene.h").read_text(), valid)

    def test_target_alias_resolves_without_accepting_another_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            current = target / "current" / "out"
            other = root / "other" / "out"
            output = root / "evidence"
            for path in (current, other, output):
                path.mkdir(parents=True)
            alias = root / "target-alias"
            alias.symlink_to(target, target_is_directory=True)
            valid = "typedef uint32_t PaddedBool32;\nPaddedBool32 wavy;\nPaddedBool32 grayscale;\n"
            (current / "scene.h").write_text(valid)
            (other / "scene.h").write_text(valid)
            log = root / "cargo.log"
            def record(path: Path) -> None:
                log.write_text(json.dumps({
                    "reason": "build-script-executed",
                    "package_id": "path+file:///toolkit/gpui_macos#gpui-toolkit-gpui-macos@0.1.0",
                    "out_dir": str(path),
                }) + "\n")
            record(current)
            self.assertEqual(scene_header(output, log, alias), str((current / "scene.h").resolve()))
            record(other)
            with self.assertRaisesRegex(RuntimeError, "current GPUI macOS build-script output"):
                scene_header(output, log, alias)

    def test_stale_header_without_current_build_event_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "target" / "stale" / "out"
            stale.mkdir(parents=True)
            (stale / "scene.h").write_text(
                "typedef uint32_t PaddedBool32;\nPaddedBool32 wavy;\nPaddedBool32 grayscale;\n"
            )
            output = root / "evidence"
            output.mkdir()
            log = root / "cargo.log"
            log.write_text("")
            with self.assertRaisesRegex(RuntimeError, "current GPUI macOS build-script output"):
                scene_header(output, log, root / "target")


if __name__ == "__main__":
    unittest.main()
