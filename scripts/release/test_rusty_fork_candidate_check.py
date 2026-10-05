"""Positive and negative test-inventory fixtures for the standalone fork gate."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.release import rusty_fork_candidate_check as gate


class InventoryTests(unittest.TestCase):
    def render(self, name: str, names: set[str], *, failed: int = 0, ignored: int = 0) -> str:
        lines = [f"running {len(names)} tests"]
        lines.extend(f"test {item}{' - should panic' if item in gate.SHOULD_PANIC else ''} ... ok"
                     for item in sorted(names))
        lines.append(f"test result: ok. {len(names)} passed; {failed} failed; {ignored} ignored; 0 measured; 0 filtered out")
        return "\n".join(lines) + "\n"

    def check(self, name: str, text: str) -> dict:
        with tempfile.TemporaryDirectory() as location:
            output = Path(location)
            (output / "logs").mkdir()
            (output / "logs" / f"{name}.log").write_text(text)
            with patch.object(gate, "OUTPUT", output):
                return gate.test_inventory(name)

    def test_default_and_no_default_exact_inventories(self) -> None:
        default = gate.EXPECTED_BASE | gate.TIMEOUT_TESTS
        self.assertEqual(len(self.check("default", self.render("default", default))["names"]), 14)
        self.assertEqual(len(self.check("no-default", self.render("no-default", gate.EXPECTED_BASE))["names"]), 12)
        self.assertEqual(len(self.check("error-source", self.render("error-source", {"error::tests::spawn_error_preserves_source_and_legacy_cause"}))["names"]), 1)

    def test_missing_or_extra_process_test_is_rejected(self) -> None:
        names = gate.EXPECTED_BASE | gate.TIMEOUT_TESTS
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            self.check("default", self.render("default", names - {"fork_test::test::aborting_child"}))
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            self.check("default", self.render("default", names | {"unexpected::test"}))

    def test_failed_or_ignored_test_is_rejected(self) -> None:
        names = gate.EXPECTED_BASE | gate.TIMEOUT_TESTS
        with self.assertRaisesRegex(ValueError, "summary differs"):
            self.check("default", self.render("default", names, failed=1))
        with self.assertRaisesRegex(ValueError, "summary differs"):
            self.check("default", self.render("default", names, ignored=1))

    def test_provenance_rejects_wrong_license_or_source_hash(self) -> None:
        valid = {
            "head": gate.FORK, "parent": gate.MANIFEST_CHILD,
            "grandparent": gate.OFFICIAL, "tree": gate.TREE,
            "changed_paths": ["Cargo.toml", "src/error.rs"],
            "official_manifest_blob": gate.OFFICIAL_MANIFEST_BLOB,
            "fork_manifest_blob": gate.FORK_MANIFEST_BLOB,
            "source_diff_sha256": gate.DIFF_SHA256,
            "license_apache": "16fe87b06e802f094b3fbb0894b137bca2b16ef1",
            "license_mit": "63ceeec5c6d0770d928e2e9aa34ec5783dedb6de",
            "worktree_entries": [],
        }
        gate.verify_initial_fork(valid)
        for field in ("license_apache", "license_mit", "source_diff_sha256", "tree", "head"):
            wrong = dict(valid, **{field: "0" * len(valid[field])})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                gate.verify_initial_fork(wrong)
        with self.assertRaisesRegex(ValueError, "worktree_entries"):
            gate.verify_initial_fork(dict(valid, worktree_entries=["?? altered.rs"]))

    def test_wrong_should_panic_marker_is_rejected(self) -> None:
        names = gate.EXPECTED_BASE | gate.TIMEOUT_TESTS
        text = self.render("default", names)
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            self.check("default", text.replace("test fork_test::test::timeout_fails - should panic ... ok",
                                               "test fork_test::test::timeout_fails ... ok"))

    def test_duplicate_or_failed_named_result_is_rejected(self) -> None:
        names = gate.EXPECTED_BASE | gate.TIMEOUT_TESTS
        text = self.render("default", names)
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            self.check("default", text + "test fork_test::test::trivial ... ok\n")
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            self.check("default", text.replace("test fork_test::test::trivial ... ok", "test fork_test::test::trivial ... FAILED"))


if __name__ == "__main__":
    unittest.main()
