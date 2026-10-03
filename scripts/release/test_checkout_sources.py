"""Contract tests for the pinned Gitea source checkout."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from checkout_sources import checkout, clone_env, git, read_manifest
from workspaces import workspace_names


class CheckoutSourcesTests(unittest.TestCase):
    def test_manifest_requires_every_workspace_and_full_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            data = {
                "schema": 1, "server": "http://gitea.example:3001", "owner": "pierre",
                "sources": {name: {"revision": "a" * 40} for name in workspace_names()},
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(set(read_manifest(path)[2]), set(workspace_names()))
            del data["sources"][workspace_names()[0]]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "match inventory"):
                read_manifest(path)
            data["sources"][workspace_names()[0]] = {"revision": "main"}
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "full lowercase Git SHA"):
                read_manifest(path)

    def test_checkout_rejects_a_mismatched_commit_and_removes_temporary_clone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revisions = {name: "a" * 40 for name in workspace_names()}
            with patch("checkout_sources.git", side_effect=["", "", "b" * 40]):
                with self.assertRaisesRegex(ValueError, "checked out"):
                    checkout(root, "http://gitea.example:3001", "pierre", revisions)
            self.assertEqual(list(root.iterdir()), [])

    def test_token_uses_basic_header_in_environment_only(self) -> None:
        with patch.dict("checkout_sources.os.environ", {"GITEA_TOKEN": "secret-token", "GITEA_USER": "reader"}):
            env = clone_env("http://gitea.example:3001", "pierre")
        self.assertNotIn("GITEA_TOKEN", env)
        self.assertNotIn("GITEA_USER", env)
        encoded = base64.b64encode(b"reader:secret-token").decode("ascii")
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], f"Authorization: Basic {encoded}")

    def test_git_failure_redacts_credentials_from_server_message(self) -> None:
        header = "Authorization: Basic c2VjcmV0"
        failed = subprocess.CompletedProcess(
            args=["git", "clone"], returncode=128, stdout="",
            stderr=f"remote: secret-token\nremote: {header}\nremote: denied\n",
        )
        with patch.dict("checkout_sources.os.environ", {"GITEA_TOKEN": "secret-token"}):
            with patch("checkout_sources.subprocess.run", return_value=failed):
                with self.assertRaises(RuntimeError) as raised:
                    git("clone", "https://gitea.example/pierre/sotf.git", env={"GIT_CONFIG_VALUE_0": header})
        message = str(raised.exception)
        self.assertIn("denied", message)
        self.assertNotIn("secret-token", message)
        self.assertNotIn(header, message)


if __name__ == "__main__":
    unittest.main()
