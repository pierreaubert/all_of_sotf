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
from checkout_sources import (checkout, clone_env, git, gitlink_revision,
                              preflight_root, prepare_destinations, read_manifest,
                              root_layout_status)
from workspaces import source_names


class CheckoutSourcesTests(unittest.TestCase):
    def test_manifest_requires_every_workspace_and_full_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            data = {
                "schema": 1, "server": "http://gitea.example:3001", "owner": "pierre",
                "sources": {name: {"revision": "a" * 40} for name in source_names()},
            }
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(set(read_manifest(path)[2]), set(source_names()))
            del data["sources"][source_names()[0]]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "match inventory"):
                read_manifest(path)
            data["sources"][source_names()[0]] = {"revision": "main"}
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "full lowercase Git SHA"):
                read_manifest(path)

    def test_checkout_rejects_a_mismatched_commit_and_removes_temporary_clone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            revisions = {name: "a" * 40 for name in source_names()}
            for name, revision in revisions.items():
                subprocess.run(["git", "-C", str(root), "update-index", "--add", "--cacheinfo",
                                f"160000,{revision},{name}"], check=True)
                (root / name).mkdir()
            subprocess.run(["git", "-C", str(root), "-c", "user.name=CI", "-c",
                            "user.email=ci@example.invalid", "commit", "-qm", "fixture"], check=True)
            with patch("checkout_sources.git", side_effect=["", "", "", "b" * 40]):
                with self.assertRaisesRegex(ValueError, "checked out"):
                    checkout(root, "http://gitea.example:3001", "pierre", revisions)
            self.assertFalse(any(root.glob(".autoeq-*")))

    def test_preflight_accepts_only_absent_pinned_gitlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            revisions = {name: "a" * 40 for name in source_names()}
            for name, revision in revisions.items():
                subprocess.run(["git", "-C", str(root), "update-index", "--add", "--cacheinfo",
                                f"160000,{revision},{name}"], check=True)
                (root / name).mkdir()
            subprocess.run(["git", "-C", str(root), "-c", "user.name=CI", "-c",
                            "user.email=ci@example.invalid", "commit", "-qm", "fixture"], check=True)
            preflight_root(root, revisions)
            (root / source_names()[0]).rmdir()
            preflight_root(root, revisions)
            (root / "unexpected.txt").write_text("dirty")
            with self.assertRaisesRegex(ValueError, "dirty"):
                preflight_root(root, revisions)

    def test_preflight_accepts_clean_legacy_root_before_clone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            revisions = {name: "a" * 40 for name in source_names()}
            preflight_root(root, revisions)
            (root / "unexpected.txt").write_text("dirty")
            with self.assertRaisesRegex(ValueError, "dirty"):
                preflight_root(root, revisions)

    def test_matching_gitlink_allows_only_empty_checkout_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            name = source_names()[0]
            revision = "a" * 40
            subprocess.run(["git", "-C", str(root), "update-index", "--add", "--cacheinfo",
                            f"160000,{revision},{name}"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=CI", "-c",
                            "user.email=ci@example.invalid", "commit", "-qm", "fixture"], check=True)
            self.assertEqual(gitlink_revision(root, name), revision)
            (root / name).mkdir()
            prepare_destinations(root, {item: revision for item in source_names()})
            self.assertFalse((root / name).exists())
            self.assertEqual(subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain"], text=True),
                f" D {name}\n")

    def test_gitlink_pin_and_nonempty_placeholder_fail_before_any_removal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            first, second = source_names()[:2]
            revision = "a" * 40
            for name in (first, second):
                subprocess.run(["git", "-C", str(root), "update-index", "--add", "--cacheinfo",
                                f"160000,{revision},{name}"], check=True)
                (root / name).mkdir()
            (root / second / "user.txt").write_text("preserve me")
            with self.assertRaisesRegex(ValueError, "already exists"):
                prepare_destinations(root, {item: revision for item in source_names()})
            self.assertTrue((root / first).is_dir())
            self.assertTrue((root / second / "user.txt").is_file())
            (root / second / "user.txt").unlink()
            with self.assertRaisesRegex(ValueError, "differs from source manifest"):
                prepare_destinations(root, {item: "b" * 40 for item in source_names()})
            self.assertTrue((root / first).is_dir())

    def test_regular_index_entry_and_symlink_destination_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            first, second = source_names()[:2]
            (root / first).write_text("tracked file")
            subprocess.run(["git", "-C", str(root), "add", first], check=True)
            with self.assertRaisesRegex(ValueError, "not a stage-zero gitlink"):
                gitlink_revision(root, first)
            subprocess.run(["git", "-C", str(root), "rm", "--cached", "-q", first], check=True)
            (root / first).unlink()
            (root / second).symlink_to(root / ".git", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlink"):
                prepare_destinations(root, {item: "a" * 40 for item in source_names()})

    def test_root_layout_rejects_extra_status_and_mismatched_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            name = source_names()[0]
            revision = "a" * 40
            subprocess.run(["git", "-C", str(root), "update-index", "--add", "--cacheinfo",
                            f"160000,{revision},{name}"], check=True)
            subprocess.run(["git", "-C", str(root), "-c", "user.name=CI", "-c",
                            "user.email=ci@example.invalid", "commit", "-qm", "fixture"], check=True)
            self.assertEqual(root_layout_status(root, {name: revision})["missing"], [])
            self.assertIn("gitlink pin mismatch",
                          root_layout_status(root, {name: "b" * 40})["missing"][0])
            (root / "unexpected.txt").write_text("not allowed")
            self.assertIn("?? unexpected.txt", root_layout_status(root, {name: revision})["unexpected"])

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
