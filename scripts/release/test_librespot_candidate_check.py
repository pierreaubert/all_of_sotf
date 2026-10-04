"""Supervision regressions for the offline Librespot candidate lane."""
import json
import signal
import subprocess
import sys

import pytest

from scripts.release import librespot_candidate_check as lane


def test_resolved_playback_features_refuse_rodio(tmp_path):
    revision = "a" * 40
    names = ("core", "playback", "metadata", "protocol")
    packages = [
        {"id": name, "name": f"librespot-{name}",
         "source": f"git+{lane.FORK}?rev={revision}#{revision}"}
        for name in names
    ]
    nodes = [
        {"id": name, "features": ["native-tls"] if name != "protocol" else []}
        for name in names
    ]
    log = tmp_path / "metadata.log"
    log.write_text(json.dumps({"packages": packages, "resolve": {"nodes": nodes}}) + "\n")
    assert lane.spotify_resolved_features(log, revision)["librespot-playback"] == ["native-tls"]
    nodes[1]["features"].append("rodio-backend")
    log.write_text(json.dumps({"packages": packages, "resolve": {"nodes": nodes}}) + "\n")
    with pytest.raises(ValueError, match="unexpected backend"):
        lane.spotify_resolved_features(log, revision)
    nodes[1]["features"] = ["native-tls", "alsa-backend"]
    log.write_text(json.dumps({"packages": packages, "resolve": {"nodes": nodes}}) + "\n")
    with pytest.raises(ValueError, match="unexpected backend"):
        lane.spotify_resolved_features(log, revision)
    nodes[1]["features"] = ["native-tls"]
    packages[1]["source"] = f"git+{lane.FORK}?rev={revision}#{'b' * 40}"
    log.write_text(json.dumps({"packages": packages, "resolve": {"nodes": nodes}}) + "\n")
    with pytest.raises(ValueError, match="unexpected resolved source"):
        lane.spotify_resolved_features(log, revision)


def test_root_guard_only_permits_manifest_named_siblings(monkeypatch):
    monkeypatch.setattr(
        lane.subprocess, "check_output",
        lambda *_args, **_kwargs: "?? sotf/\n?? unknown/\n M scripts/release/qa.py\n",
    )
    status = lane.root_checkout_status({"sotf": "a", "autoeq": "b"})
    assert status["allowed_sibling_checkouts"] == ["?? sotf/"]
    assert status["missing_sibling_checkouts"] == ["?? autoeq/"]
    assert status["unexpected_root_paths"] == [" M scripts/release/qa.py", "?? unknown/"]


def test_registration_failure_cleans_started_group(tmp_path, monkeypatch):
    output = tmp_path / "evidence"
    output.mkdir()
    started = []

    class Child:
        pid = 12345

    monkeypatch.setattr(lane.subprocess, "Popen", lambda *args, **kwargs: Child())
    saves = 0

    def fail_registration(*_):
        nonlocal saves
        saves += 1
        if saves == 2:
            raise OSError("report unavailable")

    monkeypatch.setattr(lane, "save", fail_registration)
    monkeypatch.setattr(lane, "clean_group", lambda child: (
        started.append(child.pid) or {"ok": True, "remaining": [], "errors": []}
    ))
    with pytest.raises(OSError, match="report unavailable"):
        lane.run("registration", ["cargo", "check"], tmp_path, output,
                 {"commands": []})
    assert started == [12345]
    assert saves == 2


def test_inspection_error_still_signals_owned_group_and_fails(monkeypatch):
    class Child:
        pid = 12345

        def poll(self):
            return 0

        def wait(self, timeout):
            return 0

    inspections = 0

    def inspect(_pgid):
        nonlocal inspections
        inspections += 1
        if inspections == 1:
            raise OSError("ps unavailable")
        return []

    signalled = []
    monkeypatch.setattr(lane, "members", inspect)
    monkeypatch.setattr(lane.os, "killpg", lambda pgid, signum: signalled.append((pgid, signum)))
    outcome = lane.clean_group(Child())
    assert signalled == [(12345, signal.SIGTERM)]
    assert outcome["ok"] is False
    assert any("ps unavailable" in error for error in outcome["errors"])


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux private subreaper contract")
def test_leader_exit_does_not_leave_owned_descendant():
    lane.enable_subreaper()
    leader = subprocess.Popen(
        [sys.executable, "-c", "import subprocess,sys,time; "
         "subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
         "time.sleep(0.2)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        leader.wait(timeout=5)
        assert lane.members(leader.pid), "fixture must leave a same-group descendant"
    finally:
        outcome = lane.clean_group(leader)
    assert outcome == {"ok": True, "remaining": [], "errors": []}
