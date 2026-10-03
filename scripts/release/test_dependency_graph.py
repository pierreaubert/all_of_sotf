"""Static regression cases for the dependency graph audit."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import dependency_graph as graph


def fixture_root(tmp_path: Path):
    for name in graph.LAYERS:
        workspace = tmp_path / name
        workspace.mkdir()
        (workspace / "Cargo.toml").write_text(f'[package]\nname = "{name}"\nversion = "0.1.0"\n')
        (workspace / "Cargo.lock").write_text('version = 3\n[[package]]\nname = "serde"\nversion = "1.0.0"\nsource = "registry+crates.io"\n')
    return tmp_path


def codes(report):
    return [item["code"] for item in report["findings"]]


def test_allowed_downward_path_and_independent_lock_repetition(tmp_path):
    root = fixture_root(tmp_path)
    (root / "sotf" / "Cargo.toml").write_text(
        '[package]\nname = "sotf"\nversion = "0.1.0"\n'
        '[dependencies]\ndaw = { package = "sotf-daw", path = "../sotf-daw" }\n'
    )
    assert graph.audit(root)["summary"]["errors"] == 0


def test_upward_target_and_patch_edges_fail(tmp_path):
    root = fixture_root(tmp_path)
    (root / "autoeq" / "Cargo.toml").write_text(
        '[package]\nname = "autoeq"\nversion = "0.1.0"\n'
        '[target.\'cfg(unix)\'.build-dependencies]\n'
        'forbidden = { package = "sotf", git = "https://github.com/pierreaubert/sotf" }\n'
        '[patch.crates-io]\nforbidden2 = { package = "sotf-systemwide", path = "../sotf-systemwide" }\n'
    )
    assert codes(graph.audit(root)).count("upward_dependency") == 2


def test_workspace_inheritance_and_same_layer_report(tmp_path):
    root = fixture_root(tmp_path)
    (root / "sotf" / "Cargo.toml").write_text(
        '[workspace.dependencies]\npeer = { package = "sotf-systemwide", path = "../sotf-systemwide" }\n'
    )
    member = root / "sotf" / "crates" / "member"
    member.mkdir(parents=True)
    (member / "Cargo.toml").write_text('[package]\nname = "member"\nversion = "0.1.0"\n[dev-dependencies]\npeer = { workspace = true }\n')
    findings = graph.audit(root)["findings"]
    assert any(item["code"] == "same_layer_dependency" and item["severity"] == "report" for item in findings)


def test_same_version_mixed_sources_and_multiple_versions_are_distinct_errors(tmp_path):
    root = fixture_root(tmp_path)
    (root / "sotf" / "Cargo.lock").write_text(
        'version = 3\n'
        '[[package]]\nname = "sofa-reader"\nversion = "0.2.0"\nsource = "registry+crates.io"\n'
        '[[package]]\nname = "sofa-reader"\nversion = "0.2.0"\nsource = "git+https://example/sofa-reader#123"\n'
        '[[package]]\nname = "rubato"\nversion = "1.0.1"\nsource = "registry+crates.io"\n'
        '[[package]]\nname = "rubato"\nversion = "5.0.0"\n'
    )
    assert "mixed_sources" in codes(graph.audit(root))
    assert "multiple_versions" in codes(graph.audit(root))


def test_duplicate_vendor_across_workspaces_fails(tmp_path):
    root = fixture_root(tmp_path)
    for owner in ("sotf", "sotf-daw"):
        directory = root / owner / "crates" / "3rdparties" / "fork"
        directory.mkdir(parents=True)
        (directory / "Cargo.toml").write_text('[package]\nname = "fork"\nversion = "1.0.0"\n')
    assert "duplicate_vendor" in codes(graph.audit(root))


def test_target_dependency_and_same_layer_cycle(tmp_path):
    root = fixture_root(tmp_path)
    (root / "sotf" / "Cargo.toml").write_text(
        '[package]\nname = "sotf"\nversion = "0.1.0"\n'
        '[target.\'cfg(unix)\'.dependencies]\npeer = { path = "../sotf-systemwide" }\n'
    )
    (root / "sotf-systemwide" / "Cargo.toml").write_text(
        '[package]\nname = "sotf-systemwide"\nversion = "0.1.0"\n'
        '[build-dependencies]\npeer = { path = "../sotf" }\n'
    )
    assert "repository_cycle" in codes(graph.audit(root))


def test_patch_is_source_override_not_cycle_edge(tmp_path):
    root = fixture_root(tmp_path)
    (root / "sotf" / "Cargo.toml").write_text(
        '[package]\nname = "sotf"\nversion = "0.1.0"\n'
        '[patch.crates-io]\npeer = { path = "../sotf-systemwide" }\n'
    )
    (root / "sotf-systemwide" / "Cargo.toml").write_text(
        '[package]\nname = "sotf-systemwide"\nversion = "0.1.0"\n'
        '[dependencies]\npeer = { path = "../sotf" }\n'
    )
    assert "repository_cycle" not in codes(graph.audit(root))


def test_nested_workspace_inheritance_uses_nearest_root(tmp_path):
    root = fixture_root(tmp_path)
    nested = root / "sotf" / "crates" / "3rdparties" / "fork"
    nested.mkdir(parents=True)
    (nested / "Cargo.toml").write_text(
        '[workspace.dependencies]\npeer = { path = "../../../../math-audio" }\n'
    )
    member = nested / "member"
    member.mkdir()
    (member / "Cargo.toml").write_text(
        '[package]\nname = "fork-member"\nversion = "0.1.0"\n'
        '[dependencies]\npeer = { workspace = true }\n'
    )
    assert "unresolved_workspace_dependency" not in codes(graph.audit(root))
