"""Fail-closed fixtures for Cosmic's original standalone test and LFS inventory."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.release import cosmic_standalone_check as gate


class CosmicEvidenceTests(unittest.TestCase):
    def fixture(self, name: str, count: int, *, omit: str = "", ignored: int = 0) -> str:
        needed = gate.REQUIRED_LAYOUT | ({"editor_line_endings_preserved"} if name == "all-feature-tests" else set())
        names = sorted(needed - {omit})
        names += [f"original_test_{n}" for n in range(count - len(names))]
        lines = [f"test {test} ... ok" for test in names]
        # One library and nine integration test binaries in the published source.
        distribution = [4, 7, 7 if name == "all-feature-tests" else 0, 14, 1, 8, 4, 1, 2, 1]
        lines += [f"test result: ok. {n} passed; 0 failed; {ignored if i == 0 else 0} ignored; 0 measured; 0 filtered out"
                  for i, n in enumerate(distribution)]
        return "\n".join(lines) + "\n"

    def parse(self, name: str, transcript: str) -> dict:
        with tempfile.TemporaryDirectory() as location:
            path = Path(location)
            (path / "logs").mkdir()
            (path / "logs" / f"{name}.log").write_text(transcript)
            with patch.object(gate, "OUTPUT", path):
                return gate.upstream_tests(name)

    def test_default_and_all_feature_positive_counts(self) -> None:
        self.assertEqual(self.parse("default-tests", self.fixture("default-tests", 42))["passed"], 42)
        self.assertEqual(self.parse("all-feature-tests", self.fixture("all-feature-tests", 49))["passed"], 49)

    def test_missing_layout_test_or_ignored_test_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            self.parse("default-tests", self.fixture("default-tests", 42, omit="wrap_word_fallback"))
        with self.assertRaisesRegex(ValueError, "ignored"):
            self.parse("default-tests", self.fixture("default-tests", 42, ignored=1))

    def test_extra_summary_or_failed_test_rejected(self) -> None:
        text = self.fixture("default-tests", 42)
        with self.assertRaisesRegex(ValueError, "summaries"):
            self.parse("default-tests", text + "test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n")
        with self.assertRaisesRegex(ValueError, "inventory incomplete"):
            self.parse("default-tests", text.replace("test stable_wrap ... ok", "test stable_wrap ... FAILED"))

    def test_fork_provenance_rejects_license_or_source_change(self) -> None:
        valid = {
            "head": gate.FORK, "parent": gate.MANIFEST_CHILD,
            "grandparent": gate.OFFICIAL, "tree": gate.TREE,
            "changed_paths": ["Cargo.toml", "src/shape.rs"],
            "official_manifest_blob": gate.OFFICIAL_MANIFEST_BLOB,
            "fork_manifest_blob": gate.FORK_MANIFEST_BLOB,
            "official_shape_blob": gate.OFFICIAL_SHAPE_BLOB,
            "fork_shape_blob": gate.FORK_SHAPE_BLOB,
            "license_apache": "6f756351aae24b479e6a9418c1f08a8b7a991076",
            "license_mit": "db6aab15cf8c6a1f348650f0c6fa4df60d026a89",
            "worktree_entries": [],
        }
        gate.verify_initial_fork(valid)
        for field in ("head", "parent", "grandparent", "tree", "official_manifest_blob",
                      "fork_manifest_blob", "official_shape_blob", "fork_shape_blob",
                      "license_apache", "license_mit"):
            changed = dict(valid, **{field: "0" * len(valid[field])})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                gate.verify_initial_fork(changed)
        with self.assertRaisesRegex(ValueError, "worktree_entries"):
            gate.verify_initial_fork(dict(valid, worktree_entries=["?? modified.rs"]))
        with self.assertRaisesRegex(ValueError, "changed_paths"):
            gate.verify_initial_fork(dict(valid, changed_paths=["Cargo.toml", "src/shape.rs", "src/other.rs"]))

    def test_lfs_pointer_rejected_as_payload(self) -> None:
        pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"0" * 64 + b"\nsize 999\n"
        self.assertIsNotNone(gate.LFS_POINTER.fullmatch(pointer))
        with tempfile.TemporaryDirectory() as location:
            repo = Path(location)
            names = [f"fonts/font{n}.ttf" for n in range(7)] + [f"tests/images/image{n}.png" for n in range(27)]
            for name in names:
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(pointer)
            with patch.object(gate, "git", return_value="\n".join(names)), \
                 patch.object(gate.subprocess, "check_output", return_value=pointer):
                with self.assertRaisesRegex(ValueError, "payload is missing or differs"):
                    gate.verified_lfs_assets(repo)


if __name__ == "__main__":
    unittest.main()
