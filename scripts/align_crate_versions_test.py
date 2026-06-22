"""Regression tests for scripts/align_crate_versions.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from align_crate_versions import (
    collect_versions,
    find_conflicts,
    normalize_version,
    package_info,
    pick_target,
)


def test_normalize_version():
    assert str(normalize_version("=21.0.0")) == "21.0.0"
    assert str(normalize_version(">=0.4")) == "0.4"
    assert str(normalize_version("^1.2.3")) == "1.2.3"


def test_package_info_string():
    assert package_info("serde", "1.0") == ("serde", "1.0", "crates.io")


def test_package_info_table():
    assert package_info("serde", {"version": "1.0"}) == ("serde", "1.0", "crates.io")


def test_package_info_renamed():
    assert package_info("myserde", {"package": "serde", "version": "1.0"}) == (
        "serde",
        "1.0",
        "crates.io",
    )


def test_package_info_path_dependency_ignored():
    assert package_info("foo", {"path": "crates/foo", "version": "0.1.0"}) is None


def test_package_info_workspace_dependency_ignored():
    assert package_info("foo", {"workspace": True}) is None


def test_package_info_git_with_version_tracked():
    assert package_info(
        "foo", {"git": "https://example.com/foo", "version": "0.2.0"}
    ) == ("foo", "0.2.0", "git:https://example.com/foo")


def test_pick_target_prefers_highest_semver(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "autoeq").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "2.0.17"\n'
    )
    (tmp_path / "autoeq" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "2.0"\n'
    )
    by_package = collect_versions(tmp_path)
    conflicts, skipped = find_conflicts(by_package)
    assert "thiserror" in conflicts
    assert pick_target(conflicts["thiserror"]) == "2.0.17"
    assert not skipped


def test_path_dependencies_are_ignored(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nmy-internal = { path = "crates/my-internal", version = "0.1.0" }\n'
    )
    by_package = collect_versions(tmp_path)
    assert "my-internal" not in by_package


def test_git_dependencies_with_version_are_tracked(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "autoeq").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nfoo = { git = "https://example.com/foo", version = "0.2.0" }\n'
    )
    (tmp_path / "autoeq" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nfoo = { git = "https://example.com/foo", version = "0.1.0" }\n'
    )
    by_package = collect_versions(tmp_path)
    conflicts, skipped = find_conflicts(by_package)
    assert "foo" in conflicts
    assert pick_target(conflicts["foo"]) == "0.2.0"
    assert not skipped


def test_worktrees_and_3rdparties_are_ignored(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "sotf" / ".worktrees").mkdir()
    (tmp_path / "sotf" / "crates" / "3rdparties" / "foo").mkdir(parents=True)
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "2.0.17"\n'
    )
    (tmp_path / "sotf" / ".worktrees" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "1.0.0"\n'
    )
    (tmp_path / "sotf" / "crates" / "3rdparties" / "foo" / "Cargo.toml").write_text(
        '[package]\nname = "foo"\nversion = "0.1.0"\n[dependencies]\nthiserror = "1.0.0"\n'
    )
    by_package = collect_versions(tmp_path)
    assert by_package["thiserror"] == [
        (tmp_path / "sotf" / "Cargo.toml", "workspace.dependencies", "2.0.17", "crates.io")
    ]


def test_mixed_sources_are_skipped(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "autoeq").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nfoo = { git = "https://example.com/foo", version = "0.2.0" }\n'
    )
    (tmp_path / "autoeq" / "Cargo.toml").write_text(
        '[package]\nname = "autoeq"\nversion = "0.1.0"\n[dependencies]\nfoo = "0.1.0"\n'
    )
    by_package = collect_versions(tmp_path)
    conflicts, skipped = find_conflicts(by_package)
    assert "foo" not in conflicts
    assert "foo" in skipped
