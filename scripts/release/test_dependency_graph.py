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
    nested = tmp_path / "autoeq" / "crates" / "autoeq-gpui-examples"
    nested.mkdir(parents=True)
    (nested / "Cargo.lock").write_text('version = 3\n[[package]]\nname = "serde"\nversion = "1.0.0"\nsource = "registry+crates.io"\n')
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


def test_nested_autoeq_demo_lock_is_required_and_audited(tmp_path):
    root = fixture_root(tmp_path)
    lock = root / "autoeq" / "crates" / "autoeq-gpui-examples" / "Cargo.lock"
    lock.write_text(
        'version = 3\n'
        '[[package]]\nname = "wgpu"\nversion = "29.0.3"\n'
        '[[package]]\nname = "wgpu"\nversion = "29.0.4"\n'
    )
    findings = graph.audit(root)["findings"]
    assert any(item["code"] == "multiple_versions" and
               item["workspace"] == "autoeq-gpui-examples" for item in findings)
    lock.unlink()
    assert any(item["code"] == "missing_lockfile" and
               item["workspace"] == "autoeq-gpui-examples" for item in graph.audit(root)["findings"])


def test_aggregate_lock_union_finds_cross_workspace_versions_and_sources(tmp_path):
    root = fixture_root(tmp_path)
    (root / "sotf" / "Cargo.lock").write_text(
        'version = 3\n[[package]]\nname = "example"\nversion = "1.0.0"\n'
        'source = "registry+crates.io"\n'
    )
    nested = root / "autoeq" / "crates" / "autoeq-gpui-examples" / "Cargo.lock"
    nested.write_text(
        'version = 3\n[[package]]\nname = "example"\nversion = "1.0.0"\n'
        'source = "git+https://example.invalid/example#abc"\n'
        '[[package]]\nname = "another"\nversion = "2.0.0"\n'
    )
    (root / "math-audio" / "Cargo.lock").write_text(
        'version = 3\n[[package]]\nname = "example"\nversion = "2.0.0"\n'
        'source = "registry+crates.io"\n'
    )
    findings = graph.audit(root)["findings"]
    mixed = [item for item in findings if item["code"] == "aggregate_mixed_sources"
             and item["package"] == "example"]
    versions = [item for item in findings if item["code"] == "aggregate_multiple_versions"
                and item["package"] == "example"]
    assert len(mixed) == len(versions) == 1
    assert versions[0]["versions"] == ["1.0.0", "2.0.0"]
    assert {item["workspace"] for item in mixed[0]["locations"]} == {
        "sotf", "autoeq-gpui-examples"
    }


def test_duplicate_vendor_across_workspaces_fails(tmp_path):
    root = fixture_root(tmp_path)
    for owner in ("sotf", "sotf-daw"):
        directory = root / owner / "crates" / "3rdparties" / "fork"
        directory.mkdir(parents=True)
        (directory / "Cargo.toml").write_text('[package]\nname = "fork"\nversion = "1.0.0"\n')
    assert "duplicate_vendor" in codes(graph.audit(root))


def test_shared_vendor_repository_is_audited_without_a_root_workspace(tmp_path):
    root = fixture_root(tmp_path)
    vendor = root / "sotf-3rdparties" / "rubato"
    vendor.mkdir(parents=True)
    (vendor / "Cargo.toml").write_text('[package]\nname = "rubato"\nversion = "5.0.0"\n')
    (root / "sotf-daw" / "Cargo.toml").write_text(
        '[package]\nname = "sotf-daw"\nversion = "0.1.0"\n'
        '[dependencies]\nrubato = { path = "../sotf-3rdparties/rubato" }\n'
    )
    report = graph.audit(root)
    assert report["summary"]["errors"] == 0
    assert report["vendored_repositories"] == ["sotf-3rdparties"]
    assert any(copy["owner"] == "sotf-3rdparties"
               for item in report["vendors"] for copy in item["copies"])
    duplicate = root / "math-audio" / "crates" / "3rdparties" / "rubato"
    duplicate.mkdir(parents=True)
    (duplicate / "Cargo.toml").write_text('[package]\nname = "rubato"\nversion = "5.0.0"\n')
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
