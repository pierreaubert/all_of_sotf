"""Regression coverage for aggregate gates that must never report false passes."""

from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import time

import pytest

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


def test_command_failure_stops_workspace_and_keeps_log(tmp_path, monkeypatch, capsys):
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
    assert "compile failure" in capsys.readouterr().out


def test_failure_tail_is_limited_to_last_eighty_lines(tmp_path, capsys):
    log = tmp_path / "failed.log"
    log.write_text("".join(f"line {number}\n" for number in range(100)))
    qa.print_failure_tail(log)
    output = capsys.readouterr().out
    assert "line 19\n" not in output
    assert "line 20\n" in output
    assert "line 99\n" in output


def test_successful_command_cannot_change_lockfile(tmp_path, monkeypatch):
    _, output = fake_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(qa, "commands_for", lambda *_: [
        (sys.executable, "-c", "from pathlib import Path; Path('Cargo.lock').write_text('changed')"),
    ])
    result = qa.run_workspace("sotf", "check", tmp_path, output, False)
    assert result["status"] == "FAIL"
    assert result["error"] == "sotf: Cargo.lock changed"


def test_macos_command_with_surviving_owned_group_cannot_pass(tmp_path, monkeypatch):
    _, output = fake_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(qa, "commands_for", lambda *_: [("cargo", "check")])

    class CompletedProcess:
        pid = 12345
        returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(qa.subprocess, "Popen", lambda *args, **kwargs: CompletedProcess())
    monkeypatch.setattr(qa, "clean_mac_command_group", lambda _process: {
        "ok": False,
        "survivors": [{"pid": "12346", "pgid": "12345", "state": "R"}],
        "errors": [],
    })
    result = qa.run_workspace("sotf", "check", tmp_path, output, False, "macos")
    assert result["status"] == "FAIL"
    assert result["commands"][0]["exit_code"] == 0
    assert result["commands"][0]["owned_group_cleanup"]["survivors"][0]["pid"] == "12346"
    assert result["error"] == "owned command group did not cleanly terminate"


def test_macos_registration_failure_still_cleans_started_group(tmp_path, monkeypatch):
    _, output = fake_workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(qa, "commands_for", lambda *_: [("cargo", "check")])

    class StartedProcess:
        pid = 12345
        returncode = None

    monkeypatch.setattr(qa.subprocess, "Popen", lambda *args, **kwargs: StartedProcess())
    writes = 0

    def fail_registration(*_args):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("report disk unavailable")

    cleaned = []
    monkeypatch.setattr(qa, "write_report", fail_registration)
    monkeypatch.setattr(qa, "clean_mac_command_group", lambda process: (
        cleaned.append(process.pid) or {"ok": True, "survivors": [], "errors": []}
    ))
    result = qa.run_workspace("sotf", "check", tmp_path, output, False, "macos",
                              {"workspaces": []}, output / "report.json")
    assert cleaned == [12345]
    assert result["status"] == "FAIL"
    assert result["commands"][0]["owned_group_cleanup"]["ok"]
    assert result["commands"][0]["exit_code"] == 127


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS process-group cleanup contract")
def test_macos_group_cleanup_stops_descendant_after_leader_exits():
    leader = subprocess.Popen(
        [sys.executable, "-c", "import subprocess,sys,time; "
         "subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
         "time.sleep(0.2)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        leader.wait(timeout=5)
        assert qa.mac_group_members(leader.pid), "fixture must leave a same-group descendant"
    finally:
        cleaned = qa.clean_mac_command_group(leader)
    assert cleaned == {"ok": True, "survivors": [], "errors": []}


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS nested interruption contract")
def test_macos_interrupted_wrapper_cleans_registered_nested_group(tmp_path):
    workspace = tmp_path / "sotf"
    workspace.mkdir()
    (workspace / "Cargo.toml").write_text("[workspace]\n")
    (workspace / "Cargo.lock").write_text("unchanged")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    script = tmp_path / "wrapper.py"
    script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(Path(qa.__file__).parent)!r})\n"
        "import qa\n"
        "import signal\n"
        "signal.signal(signal.SIGTERM, qa.interrupted)\n"
        "qa.workspace_map = lambda: {'sotf': object()}\n"
        "qa.snapshot = lambda *args: {'revision':'abc123','dirty':False}\n"
        "qa.commands_for = lambda *_: [(sys.executable, '-c', "
        "'import subprocess,time,sys; subprocess.Popen([sys.executable, "
        "\"-c\", \"import time;time.sleep(60)\"]); time.sleep(60)')]\n"
        f"report = {{'workspaces': []}}\n"
        "try:\n"
        f"    qa.run_workspace('sotf', 'check', Path({str(tmp_path)!r}), "
        f"Path({str(evidence)!r}), False, 'macos', report, "
        f"Path({str(evidence / 'report.json')!r}))\n"
        "except qa.GateInterrupted:\n"
        f"    qa.write_report(Path({str(evidence / 'report.json')!r}), report)\n"
        "    raise SystemExit(130)\n"
    )
    wrapper = subprocess.Popen([sys.executable, str(script)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    nested_pgid = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            path = evidence / "report.json"
            if path.is_file():
                active = json.loads(path.read_text()).get("active_command", {})
                nested_pgid = active.get("owned_pgid")
                if nested_pgid and qa.mac_group_members(nested_pgid):
                    break
            time.sleep(0.05)
        assert nested_pgid, "nested process group was never registered"
        os.killpg(wrapper.pid, signal.SIGTERM)
        assert wrapper.wait(timeout=20) == 130
        interrupted_report = json.loads((evidence / "report.json").read_text())
        assert interrupted_report["active_command"]["owned_group_cleanup"]["ok"]
        assert not qa.mac_group_members(nested_pgid)
    finally:
        if wrapper.poll() is None:
            os.killpg(wrapper.pid, signal.SIGKILL)
            wrapper.wait(timeout=5)
        if nested_pgid and qa.mac_group_members(nested_pgid):
            os.killpg(nested_pgid, signal.SIGKILL)


def test_macos_group_inspection_failure_fails_closed(monkeypatch):
    class FinishedProcess:
        pid = 12345

        def poll(self):
            return 0

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(qa, "mac_group_members", lambda _pid: (_ for _ in ()).throw(OSError("ps failed")))
    monkeypatch.setattr(qa.os, "killpg", lambda *_: None)
    result = qa.clean_mac_command_group(FinishedProcess())
    assert result["ok"] is False
    assert any("ps failed" in error for error in result["errors"])


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


def test_nested_autoeq_lock_is_required_and_guarded(tmp_path, monkeypatch):
    workspace = tmp_path / "autoeq"
    nested = workspace / "crates" / "autoeq-gpui-examples"
    nested.mkdir(parents=True)
    (workspace / "Cargo.toml").write_text("[workspace]\n")
    (workspace / "Cargo.lock").write_text("root lock")
    (nested / "Cargo.lock").write_text("nested lock")
    monkeypatch.setattr(qa, "snapshot", lambda *args: {"revision": "abc", "dirty": False})
    before = qa.source_state(tmp_path, ["autoeq"], "linux")
    assert qa.source_issues(before, before, True) == []
    (nested / "Cargo.lock").write_text("changed nested lock")
    assert qa.source_issues(before, qa.source_state(tmp_path, ["autoeq"], "linux"), True) == [
        "autoeq: nested GPUI examples Cargo.lock changed"
    ]
    (nested / "Cargo.lock").unlink()
    assert qa.source_issues(qa.source_state(tmp_path, ["autoeq"], "linux"),
                            qa.source_state(tmp_path, ["autoeq"], "linux"), True) == [
        "autoeq: nested GPUI examples Cargo.lock missing"
    ]


def test_nested_demo_and_iamf_commands_are_required():
    demo = "crates/autoeq-gpui-examples/Cargo.toml"
    metadata = ("cargo", "metadata", "--locked", "--format-version", "1",
                "--all-features", "--manifest-path", demo)
    check = ("cargo", "check", "--locked", "--all-targets", "--all-features",
             "--manifest-path", demo)
    assert metadata in qa.commands_for("autoeq", "metadata", "linux")
    assert check in qa.commands_for("autoeq", "check", "macos")
    assert check in qa.commands_for("autoeq", "qa", "linux")
    iamf = ("cargo", "test", "--locked", "--all-features", "-p",
            "symphonia-iamf-core", "-p", "symphonia-format-iamf")
    assert iamf in qa.commands_for("symphonia-add-ons", "tests", "macos")
    assert iamf in qa.commands_for("symphonia-add-ons", "qa", "linux")


def test_nested_demo_metadata_requires_both_real_binary_targets(tmp_path):
    log = tmp_path / "demo.log"
    metadata = {"packages": [{"name": "autoeq-gpui-examples", "targets": [
        {"name": "d3rs-spinorama", "kind": ["bin"]},
        {"name": "px-spinorama", "kind": ["bin"]},
    ]}]}
    log.write_text("warning: cached index\n" + json.dumps(metadata) + "\n")
    assert qa.demo_metadata_issues(log) == []
    metadata["packages"][0]["targets"].pop()
    log.write_text(json.dumps(metadata) + "\n")
    assert qa.demo_metadata_issues(log) == ["nested AutoEQ demo binary missing: px-spinorama"]


def test_sotf_qa_covers_application_and_integration_suites():
    commands = qa.commands_for("sotf", "qa", "macos")
    for recipe in ("qa", "test-pr", "ntest", "itest", "dev-driver-full", "dev-driver-roomeq"):
        assert ("just", recipe) in commands


def test_daw_qa_covers_cross_format_plugin_comparison():
    for host in ("macos", "linux"):
        assert ("just", "qa-plugins-cross-format") in qa.commands_for("sotf-daw", "qa", host)


def test_linux_daw_qa_requires_feature_gated_sandbox_worker():
    sandbox = (
        "cargo", "test", "--locked", "-p", "sotf-host",
        "--features", "worker-test-backend,external-plugin-clap",
        "--test", "external_plugin_isolation", "--", "--nocapture",
    )
    assert sandbox in qa.commands_for("sotf-daw", "qa", "linux")
    assert sandbox not in qa.commands_for("sotf-daw", "qa", "macos")
    assert sandbox not in qa.commands_for("sotf-daw", "tests", "linux")


def test_successful_sandbox_test_with_kernel_skip_fails_qa(tmp_path, monkeypatch):
    workspace = tmp_path / "sotf-daw"
    workspace.mkdir()
    (workspace / "Cargo.toml").write_text("[workspace]\n")
    (workspace / "Cargo.lock").write_text("original lock")
    output = tmp_path / "evidence"
    output.mkdir()
    monkeypatch.setattr(qa, "snapshot", lambda *args: {"revision": "abc123", "dirty": False})
    sandbox = qa.commands_for("sotf-daw", "qa", "linux")[-1]
    monkeypatch.setattr(qa, "commands_for", lambda *_: [sandbox])

    class CompletedProcess:
        returncode = 0

        def wait(self):
            return 0

    def fake_popen(_command, cwd, stdout, stderr, start_new_session):
        assert cwd == workspace
        stdout.write("SKIP: kernel sandbox unavailable (backend LinuxLandlock)\n")
        stdout.flush()
        return CompletedProcess()

    monkeypatch.setattr(qa.subprocess, "Popen", fake_popen)
    result = qa.run_workspace("sotf-daw", "qa", tmp_path, output, False, "linux")
    assert result["status"] == "FAIL"
    assert result["commands"][0]["exit_code"] == 0
    assert result["error"] == "required Linux sandbox coverage skipped; later commands were not run"
    assert result["gates"][-1]["status"] == "FAIL"


def test_sandbox_skip_marker_is_scoped_to_linux_daw_qa(tmp_path):
    log = tmp_path / "sandbox.log"
    log.write_text("SKIP: kernel sandbox unavailable\n")
    sandbox = qa.commands_for("sotf-daw", "qa", "linux")[-1]
    assert qa.sandbox_coverage_skipped("sotf-daw", "qa", "linux", sandbox, log)
    assert not qa.sandbox_coverage_skipped("sotf-daw", "qa", "macos", sandbox, log)
    assert not qa.sandbox_coverage_skipped("sotf-daw", "tests", "linux", sandbox, log)


def test_toolkit_strict_gate_runs_only_on_macos():
    assert ("just", "qa-release-evidence") in qa.commands_for("gpui-toolkit", "qa", "macos")
    linux = qa.commands_for("gpui-toolkit", "qa", "linux")
    assert ("just", "qa") in linux
    assert ("just", "qa-release-evidence") not in linux


def test_darwin_host_uses_strict_macos_gate(monkeypatch):
    monkeypatch.setattr(qa.platform, "system", lambda: "Darwin")
    assert qa.host_platform() == "macos"
    assert ("just", "qa-release-evidence") in qa.commands_for("gpui-toolkit", "qa")
