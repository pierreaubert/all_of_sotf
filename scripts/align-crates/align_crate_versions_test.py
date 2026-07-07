"""Regression tests for scripts/align_crate_versions.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from align_crate_versions import (
    DEFAULT_RISKY_PACKAGES,
    build_change_map,
    compatibility_key,
    collect_sotf_duplicates,
    collect_versions,
    find_conflicts,
    load_allowlist,
    normalize_version,
    package_info,
    pick_target,
    save_allowlist,
)


def test_normalize_version():
    assert str(normalize_version("=21.0.0")) == "21.0.0"
    assert str(normalize_version(">=0.4")) == "0.4"
    assert str(normalize_version("^1.2.3")) == "1.2.3"


def test_compatibility_key_matches_cargo_semver_groups():
    assert compatibility_key("1.2.3") == (1, None)
    assert compatibility_key("1.9.0") == (1, None)
    assert compatibility_key("0.4.1") == (0, 4)
    assert compatibility_key("0.5.0") == (0, 5)


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


def test_change_map_skips_risky_packages(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "autoeq").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\ncpal = "0.15.2"\ngpui = "0.1.0"\n'
    )
    (tmp_path / "autoeq" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\ncpal = "0.16.0"\ngpui = "0.2.0"\n'
    )
    conflicts, _skipped = find_conflicts(collect_versions(tmp_path))
    assert build_change_map(conflicts, risky_packages=DEFAULT_RISKY_PACKAGES) == {}


def test_change_map_aligns_only_semver_compatible_groups_by_default(tmp_path):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "autoeq").mkdir()
    (tmp_path / "math-audio").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "1.0.69"\n'
    )
    (tmp_path / "autoeq" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "2.0.17"\n'
    )
    (tmp_path / "math-audio" / "Cargo.toml").write_text(
        '[workspace]\n[workspace.dependencies]\nthiserror = "2.0.18"\n'
    )

    conflicts, _skipped = find_conflicts(collect_versions(tmp_path))
    changes = build_change_map(conflicts, risky_packages=set())

    assert changes == {
        tmp_path / "autoeq" / "Cargo.toml": {
            "workspace.dependencies": {"thiserror": "2.0.18"}
        }
    }


def _metadata_result(metadata: dict):
    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(metadata)

    return Result()


def test_collect_sotf_duplicates_from_metadata(tmp_path, monkeypatch):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text("[workspace]\nmembers = []\n")

    metadata = {
        "workspace_members": [],
        "packages": [
            {"name": "bitflags", "version": "1.3.2", "id": "bitflags 1.3.2"},
            {"name": "bitflags", "version": "2.13.0", "id": "bitflags 2.13.0"},
            {"name": "serde", "version": "1.0.210", "id": "serde 1.0.210"},
        ],
    }

    monkeypatch.setattr(
        "align_crate_versions.subprocess.run",
        lambda *args, **kwargs: _metadata_result(metadata),
    )
    duplicates, members = collect_sotf_duplicates(tmp_path)
    assert members == set()
    assert duplicates == {"bitflags": {"1.3.2", "2.13.0"}}


def test_workspace_members_are_excluded_from_duplicates(tmp_path, monkeypatch):
    (tmp_path / "sotf").mkdir()
    (tmp_path / "sotf" / "Cargo.toml").write_text("[workspace]\nmembers = []\n")

    metadata = {
        "workspace_members": ["sotf-engine 1.0.0 (path+file:///x)"],
        "packages": [
            {"name": "sotf-engine", "version": "1.0.29", "id": "sotf-engine 1.0.29"},
            {"name": "sotf-engine", "version": "1.0.30", "id": "sotf-engine 1.0.30"},
        ],
    }

    monkeypatch.setattr(
        "align_crate_versions.subprocess.run",
        lambda *args, **kwargs: _metadata_result(metadata),
    )
    duplicates, members = collect_sotf_duplicates(tmp_path)
    assert "sotf-engine" in members
    assert "sotf-engine" not in duplicates


def test_allowlist_roundtrip(tmp_path):
    path = tmp_path / "allowlist.toml"
    save_allowlist(path, {"bitflags": {"1.3.2", "2.13.0"}})
    loaded = load_allowlist(path)
    assert loaded == {"bitflags": {"1.3.2", "2.13.0"}}
