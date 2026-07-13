import tempfile
import unittest
from pathlib import Path
from unittest import mock

import version_snapshot


class VersionSnapshotTests(unittest.TestCase):
    def test_snapshot_contains_version_and_platform_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            with mock.patch.object(version_snapshot, "git_value", return_value="value"), \
                 mock.patch.object(version_snapshot, "git_dirty", return_value=False), \
                 mock.patch.object(version_snapshot, "command_version", return_value="tool 1.0"):
                result = version_snapshot.snapshot(workspace, "linux")
        self.assertEqual(result["platform_label"], "linux")
        self.assertEqual(result["revision"], "value")
        self.assertFalse(result["dirty"])
        self.assertIn("architecture", result)
        self.assertEqual(result["cargo"], "tool 1.0")
        self.assertEqual(result["cargo_nextest"], "tool 1.0")

    def test_missing_command_is_recorded_as_none(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(
                version_snapshot.command_version(["definitely-not-a-command"], Path(directory))
            )


if __name__ == "__main__":
    unittest.main()
