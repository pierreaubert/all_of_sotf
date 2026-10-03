"""Regression coverage for aggregate gates that must never report false passes."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import qa


def fake_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "sotf"
    workspace.mkdir()
    (workspace / "Cargo.toml").write_text("[workspace]\n")
    (workspace / "Cargo.lock").write_text("original lock")
    output = tmp_path / "evidence"
    output.mkdir()
    monkeypatch.setattr(qa, "workspace_map", lambda: {"sotf": object()})
    monkeypatch.setattr(qa, "snapshot", lambda *args: {"revision": "abc123", "dirty": False})
    return workspace, output


def test_missing_workspace_is_failure(tmp_path):
    result = qa.run_workspace("sotf", "metadata", tmp_path, tmp_path, False)
    assert result["status"] == "FAIL"
    assert "missing workspace" in result["error"]


def test_command_failure_stops_workspace_and_keeps_log(tmp_path, monkeypatch):
    _, output = fake_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(qa, "commands_for", lambda *_: [
        (sys.executable, "-c", "print('compile failure'); raise SystemExit(7)"),
        (sys.executable, "-c", "raise AssertionError('must not run')"),
    ])
    result = qa.run_workspace("sotf", "check", tmp_path, output, False)
    assert result["status"] == "FAIL"
    assert len(result["commands"]) == 1
    assert result["commands"][0]["exit_code"] == 7
    assert "compile failure" in Path(result["commands"][0]["log"]).read_text()


def test_successful_command_cannot_change_lockfile(tmp_path, monkeypatch):
    _, output = fake_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(qa, "commands_for", lambda *_: [
        (sys.executable, "-c", "from pathlib import Path; Path('Cargo.lock').write_text('changed')"),
    ])
    result = qa.run_workspace("sotf", "check", tmp_path, output, False)
    assert result["status"] == "FAIL"
    assert result["error"] == "sotf: Cargo.lock changed"


def test_clean_release_requirement_rejects_dirty_sources(tmp_path, monkeypatch):
    _, output = fake_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(qa, "snapshot", lambda *_: {"revision": "abc123", "dirty": True})
    result = qa.run_workspace("sotf", "qa", tmp_path, output, True)
    assert result["status"] == "FAIL"
    assert result["commands"] == []


def test_sibling_change_fails_aggregate_source_guard():
    before = {"sotf": {"revision": "a", "dirty": False, "lock_sha256": "1"},
              "sotf-daw": {"revision": "b", "dirty": False, "lock_sha256": "2"}}
    after = {"sotf": before["sotf"],
             "sotf-daw": {"revision": "b", "dirty": False, "lock_sha256": "3"}}
    assert qa.source_issues(before, after, True) == ["sotf-daw: Cargo.lock changed"]


def test_sotf_qa_covers_application_and_integration_suites():
    commands = qa.commands_for("sotf", "qa", "macos")
    for recipe in ("qa", "test-pr", "ntest", "itest", "dev-driver-full", "dev-driver-roomeq"):
        assert ("just", recipe) in commands


def test_toolkit_strict_gate_runs_only_on_macos():
    assert ("just", "qa-release-evidence") in qa.commands_for("gpui-toolkit", "qa", "macos")
    linux = qa.commands_for("gpui-toolkit", "qa", "linux")
    assert ("just", "qa") in linux
    assert ("just", "qa-release-evidence") not in linux


def test_darwin_host_uses_strict_macos_gate(monkeypatch):
    monkeypatch.setattr(qa.platform, "system", lambda: "Darwin")
    assert qa.host_platform() == "macos"
    assert ("just", "qa-release-evidence") in qa.commands_for("gpui-toolkit", "qa")
