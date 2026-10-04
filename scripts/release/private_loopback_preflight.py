#!/usr/bin/env python3
"""Prove a disposable Linux container has a private twelve-channel PCM loopback."""

from __future__ import annotations

import json
import ctypes
import math
import os
from pathlib import Path
import pwd
import contextlib
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
from typing import Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.release.qa import ROOT, source_issues, source_state, workspace_map
from scripts.release.checkout_sources import read_manifest

# ALSA Pulse names channels 8..11 aux0..aux3. In the private 7.1.4 fixture,
# those four indices represent top-front-left/right and top-rear-left/right.
CHANNEL_POSITIONS = (
    "front-left", "front-right", "front-center", "lfe",
    "rear-left", "rear-right", "side-left", "side-right",
    "aux0", "aux1", "aux2", "aux3",
)
LOGICAL_714_POSITIONS = (
    "front-left", "front-right", "front-center", "lfe",
    "rear-left", "rear-right", "side-left", "side-right",
    "top-front-left", "top-front-right", "top-rear-left", "top-rear-right",
)


def channel_positions(value: str | None) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",")) if value else ()


def become_subreaper() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        error = ctypes.get_errno()
        raise OSError(error, "cannot become the private Linux child reaper")


def reap_adopted(process: subprocess.Popen[bytes], record: dict) -> None:
    # Popen owns the direct child and its original exit status.
    process.poll()
    if process.returncode is None:
        return
    try:
        candidates = members(process.pid)
    except Exception as exc:
        record.setdefault("inspection_errors", []).append(f"reap inventory: {exc}")
        return
    for member in candidates:
        pid = int(member["pid"])
        if pid == process.pid:
            continue
        try:
            reaped, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            continue
        if reaped:
            record.setdefault("reaped_descendants", []).append({"pid": reaped, "wait_status": status})


def members(pgid: int) -> list[dict[str, str | int]]:
    output = subprocess.run(
        ["ps", "-eo", "pid=,pgid=,stat="], text=True, capture_output=True,
        check=True, timeout=3,
    ).stdout
    result = []
    for line in output.splitlines():
        pid, group, state = line.split(maxsplit=2)
        if int(group) == pgid:
            result.append({"pid": int(pid), "state": state})
    return result


def write_active(output: Path, records: list[dict]) -> None:
    path = output / "owned-process-groups.json"
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(records, indent=2) + "\n")
    pending.replace(path)


def stop_group(process: subprocess.Popen[bytes], record: dict) -> bool:
    pgid = process.pid
    good = True
    for sig in (signal.SIGTERM, signal.SIGKILL):
        reap_adopted(process, record)
        try:
            before = members(pgid)
        except Exception as exc:
            record.setdefault("inspection_errors", []).append(str(exc))
            before = [{"pid": pgid, "state": "uninspectable"}]
            good = False
        if not before:
            break
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        for _ in range(30):
            reap_adopted(process, record)
            try:
                if not members(pgid):
                    break
            except Exception as exc:
                record.setdefault("inspection_errors", []).append(str(exc))
                good = False
                break
            time.sleep(0.1)
    reap_adopted(process, record)
    try:
        record["survivors"] = members(pgid)
    except Exception as exc:
        record.setdefault("inspection_errors", []).append(str(exc))
        record["survivors"] = [{"pid": pgid, "state": "uninspectable"}]
        good = False
    return good and not record["survivors"] and not record.get("inspection_errors")


def owned_command(argv: list[str], env: dict[str, str], log: Path,
                  commands: list[dict], active: list[dict],
                  on_started: Callable[[subprocess.Popen[bytes]], None] | None = None) -> dict:
    record: dict = {"argv": argv, "exit_code": None, "cleanup_ok": False}
    commands.append(record)
    process: subprocess.Popen[bytes] | None = None
    with log.open("wb") as stream:
        try:
            process = subprocess.Popen(
                argv, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
            )
            active_entry = {"argv": argv, "pgid": process.pid, "cleanup_ok": None}
            active.append(active_entry)
            write_active(log.parent, active)
            if on_started is not None:
                on_started(process)
            while process.poll() is None:
                print(f"private PCM command heartbeat: {argv[0]} pid={process.pid}", flush=True)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
            record["exit_code"] = process.returncode
        except KeyboardInterrupt:
            record["exit_code"] = 130
            record["interrupted"] = True
        except Exception as exc:
            record["error"] = str(exc)
            raise
        finally:
            if process is not None:
                record["cleanup_ok"] = stop_group(process, record)
                active_entry["cleanup_ok"] = record["cleanup_ok"]
                write_active(log.parent, active)
    return record


def private_environment(root: Path) -> tuple[dict[str, str], Path, Path]:
    user = pwd.getpwnam("sotfqa")
    os.chown(root, user.pw_uid, user.pw_gid)
    for name in ("home", "runtime"):
        directory = root / name
        directory.mkdir(mode=0o700)
        os.chown(directory, user.pw_uid, user.pw_gid)
    runtime = root / "runtime"
    socket = runtime / "pulse-native"
    config = root / "asound.conf"
    config.write_text(
        'pcm.!default { type pulse hint { show on description "SOTF Private 12ch Loopback" } }\n'
        "ctl.!default { type pulse }\n"
    )
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PULSE_", "PIPEWIRE_", "JACK_")) or key in ("DISPLAY", "WAYLAND_DISPLAY"):
            env.pop(key)
    env.update(
        {
            "HOME": str(root / "home"),
            "XDG_RUNTIME_DIR": str(runtime),
            "PULSE_SERVER": "unix:" + str(socket),
            "ALSA_CONFIG_PATH": str(config),
        }
    )
    return env, socket, config


def tone_and_capture(env: dict[str, str], output: Path,
                     commands: list[dict], active: list[dict], server_map: str) -> dict:
    rate, channels = 48_000, 12
    frequencies = [180 + 80 * channel for channel in range(channels)]
    tone = output / "tone.raw"
    tone.write_bytes(
        b"".join(
            struct.pack("<" + "h" * channels, *(
                int(9_000 * math.sin(2 * math.pi * frequency * i / rate))
                for frequency in frequencies
            ))
            for i in range(rate * 3)
        )
    )
    capture = output / "capture.raw"
    client_map: str | None = None
    def record_client_map(playback: subprocess.Popen[bytes]) -> None:
        nonlocal client_map
        attempt = 0
        while playback.poll() is None and client_map is None:
            attempt += 1
            log = output / f"pulse-client-map-{attempt}.log"
            probe = owned_command(["pactl", "list", "sink-inputs"], env, log, commands, active)
            if probe["exit_code"] != 0 or not probe["cleanup_ok"]:
                raise RuntimeError("private sink-input channel-map probe failed")
            for line in log.read_text(errors="replace").splitlines():
                if line.strip().startswith("Channel Map:"):
                    client_map = line.split(":", 1)[1].strip()
                    break
            if client_map is None:
                time.sleep(0.05)
    recorder: subprocess.Popen[bytes] | None = None
    record: dict = {"argv": ["arecord", "private default 12ch"], "exit_code": None,
                    "cleanup_ok": False}
    commands.append(record)
    with (output / "arecord.log").open("wb") as stream:
        try:
            recorder = subprocess.Popen(
                ["arecord", "-D", "default", "-t", "raw", "-f", "S16_LE", "-c", "12", "-r", "48000", "-d", "4", str(capture)],
                env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
            )
            active.append({"argv": record["argv"], "pgid": recorder.pid, "cleanup_ok": None})
            write_active(output, active)
            # The recorder's duration is intrinsic to arecord, not a runner deadline.
            time.sleep(0.35)
            owned_command(
                ["aplay", "-D", "default", "-t", "raw", "-f", "S16_LE", "-c", "12", "-r", "48000", str(tone)],
                env, output / "aplay.log", commands, active, on_started=record_client_map,
            )
            while recorder.poll() is None:
                print(f"private PCM recorder heartbeat: pid={recorder.pid}", flush=True)
                try:
                    recorder.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
            record["exit_code"] = recorder.returncode
        except KeyboardInterrupt:
            record["exit_code"] = 130
            record["interrupted"] = True
        except Exception as exc:
            record["error"] = str(exc)
            raise
        finally:
            if recorder is not None:
                record["cleanup_ok"] = stop_group(recorder, record)
                # The aplay record may have been appended after the recorder.
                next(item for item in active if item["pgid"] == recorder.pid)["cleanup_ok"] = record["cleanup_ok"]
                write_active(output, active)
    data = capture.read_bytes() if capture.exists() else b""
    frame_count = len(data) // (channels * 2)
    frames = list(struct.iter_unpack("<" + "h" * channels, data[:frame_count * channels * 2]))
    window = rate // 2
    step = rate // 10
    candidates = range(0, max(0, frame_count - window) + 1, step)
    start = max(candidates, key=lambda offset: sum(
        abs(value) for frame in frames[offset:offset + window] for value in frame
    )) if frame_count >= window else 0
    selected = frames[start:start + window]
    amplitudes: list[list[float]] = []
    for channel in range(channels):
        row = []
        for frequency in frequencies:
            cosine = sum(frame[channel] * math.cos(2 * math.pi * frequency * i / rate)
                         for i, frame in enumerate(selected))
            sine = sum(frame[channel] * math.sin(2 * math.pi * frequency * i / rate)
                       for i, frame in enumerate(selected))
            row.append(2 * math.hypot(cosine, sine) / len(selected) if selected else 0.0)
        amplitudes.append(row)
    channel_proof = []
    for channel, row in enumerate(amplitudes):
        matched = row[channel]
        wrong = max(value for other, value in enumerate(row) if other != channel)
        channel_proof.append({"channel": channel, "frequency_hz": frequencies[channel],
                              "matched_amplitude": round(matched, 3),
                              "largest_wrong_frequency_amplitude": round(wrong, 3),
                              "pass": matched >= 500 and wrong <= matched * 0.15})
    server_positions = channel_positions(server_map)
    client_positions = channel_positions(client_map)
    return {"frames": frame_count, "capture_window_start": start,
            "server_channel_map": server_map, "client_channel_map": client_map,
            "expected_private_channel_map": list(CHANNEL_POSITIONS),
            "logical_714_index_positions": list(LOGICAL_714_POSITIONS),
            "server_map_matches_expected": server_positions == CHANNEL_POSITIONS,
            "client_map_matches_expected": client_positions == CHANNEL_POSITIONS,
            "channel_proof": channel_proof,
            "all_twelve_channels_proved": server_positions == CHANNEL_POSITIONS
            and client_positions == CHANNEL_POSITIONS and frame_count >= rate * 2
            and all(item["pass"] for item in channel_proof)}


def root_checkout_status(pins: dict[str, str]) -> dict[str, list[str]]:
    lines = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, text=True,
    ).splitlines()
    allowed = {f"?? {name}/" for name in pins}
    present = set(lines)
    return {"allowed_sibling_checkouts": sorted(present & allowed),
            "missing_sibling_checkouts": sorted(allowed - present),
            "unexpected_root_paths": sorted(present - allowed)}


def main() -> int:
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report: dict = {"status": "FAIL", "commands": [], "issues": [],
                    "scope": "private disposable twelve-channel PCM preflight only"}
    before: dict = {}
    root_before: str | None = None
    root_status_before: dict | None = None
    manifest = ROOT / "scripts/release/sources.json"
    pulse: subprocess.Popen[bytes] | None = None
    temporary: str | None = None
    active: list[dict] = []
    def interrupt(signum: int, _frame: object) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        raise KeyboardInterrupt(f"preflight interrupted by signal {signum}")
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        (output / "sources.json").write_bytes(manifest.read_bytes())
        _, _, pins = read_manifest(manifest)
        root_before = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                              cwd=ROOT, text=True).strip()
        root_status_before = root_checkout_status(pins)
        report["root_revision"] = root_before
        report["root_status_before"] = root_status_before
        before = source_state(ROOT, list(workspace_map()), "linux")
        (output / "sources-before.json").write_text(json.dumps(before, indent=2) + "\n")
        report["issues"].extend(source_issues(before, before, require_clean=True))
        for name, revision in pins.items():
            if before.get(name, {}).get("revision") != revision:
                report["issues"].append(f"{name}: checkout differs from immutable source pin")
        if root_status_before["missing_sibling_checkouts"] or root_status_before["unexpected_root_paths"]:
            report["issues"].append("root checkout has missing siblings or unexpected paths")
        if not Path("/.dockerenv").exists() or os.geteuid() != 0 or Path("/dev/snd").exists():
            raise RuntimeError("requires a disposable root-owned container without /dev/snd")
        if any(os.environ.get(k) for k in ("PULSE_SERVER", "PIPEWIRE_REMOTE", "JACK_DEFAULT_SERVER")):
            raise RuntimeError("runner forwarded a host audio server endpoint")
        if report["issues"]:
            raise RuntimeError("source checkout failed strict preflight")
        become_subreaper()
        with contextlib.nullcontext(tempfile.mkdtemp(prefix="sotf-private-loopback-")) as temporary:
            root = Path(temporary)
            env, socket, _ = private_environment(root)
            user = pwd.getpwnam("sotfqa")
            startup = root / "default.pa"
            startup.write_text(
                f"load-module module-native-protocol-unix socket={socket} auth-anonymous=1\n"
                "load-module module-null-sink sink_name=sotf_qa channels=12 rate=48000 "
                "channel_map=front-left,front-right,front-center,lfe,rear-left,rear-right,"
                "side-left,side-right,aux0,aux1,aux2,aux3\n"
                "set-default-sink sotf_qa\nset-default-source sotf_qa.monitor\n"
            )
            os.chown(startup, user.pw_uid, user.pw_gid)
            with (output / "pulseaudio.log").open("wb") as log:
                pulse = subprocess.Popen(
                    ["runuser", "-u", "sotfqa", "--", "pulseaudio", "-n", "--daemonize=no",
                     "--exit-idle-time=-1", "--file=" + str(startup)],
                    env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                )
                active.append({"argv": ["runuser", "private pulseaudio"],
                               "pgid": pulse.pid, "cleanup_ok": None})
                write_active(output, active)
                next_heartbeat = 0.0
                while not socket.exists():
                    if pulse.poll() is not None:
                        report["pulse_exit_code"] = pulse.returncode
                        raise RuntimeError("private PulseAudio exited before socket readiness")
                    if time.monotonic() >= next_heartbeat:
                        print(f"private PulseAudio readiness heartbeat: pid={pulse.pid}", flush=True)
                        next_heartbeat = time.monotonic() + 30
                    time.sleep(1)
                for label, argv in (
                    ("pulse-info", ["pactl", "info"]),
                    ("pulse-sinks", ["pactl", "list", "sinks"]),
                    ("pulse-sources", ["pactl", "list", "sources"]),
                    ("alsa-pcms", ["aplay", "-L"]),
                ):
                    command = owned_command(argv, env, output / (label + ".log"),
                                            report["commands"], active)
                    if command["exit_code"] != 0 or not command["cleanup_ok"]:
                        raise RuntimeError(label + " failed")
                sink_text = (output / "pulse-sinks.log").read_text()
                source_text = (output / "pulse-sources.log").read_text()
                if "sotf_qa" not in sink_text or "12ch" not in sink_text or "sotf_qa.monitor" not in source_text:
                    raise RuntimeError("private 12-channel sink and monitor were not advertised")
                server_maps = [line.split(":", 1)[1].strip() for line in sink_text.splitlines()
                               if line.strip().startswith("Channel Map:")]
                if len(server_maps) != 1:
                    raise RuntimeError("private sink channel map was not uniquely reported")
                proof = tone_and_capture(env, output, report["commands"], active, server_maps[0])
                report["pcm_proof"] = proof
                if any(c["exit_code"] != 0 or not c["cleanup_ok"] for c in report["commands"]) or not proof["all_twelve_channels_proved"]:
                    raise RuntimeError("private twelve-channel PCM loopback failed channel-specific proof")
                report["suggested_AEQ_E2E_DEVICE"] = "default"
    except (Exception, KeyboardInterrupt) as exc:
        report["issues"].append(str(exc))
    finally:
        # Preserve a terminal report even when setup, cleanup, or source snapshots fail.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if pulse is not None:
            cleanup: dict = {}
            try:
                report["pulse_cleanup_ok"] = stop_group(pulse, cleanup)
            except Exception as exc:
                report["pulse_cleanup_ok"] = False
                report["issues"].append(f"PulseAudio cleanup failed: {exc}")
            if active:
                active[0]["cleanup_ok"] = report["pulse_cleanup_ok"]
                try:
                    write_active(output, active)
                except Exception as exc:
                    report["issues"].append(f"owned group evidence write failed: {exc}")
            report["pulse_cleanup"] = cleanup
        if temporary is not None:
            try:
                shutil.rmtree(temporary)
            except Exception as exc:
                report["issues"].append(f"private directory cleanup failed: {exc}")
        try:
            after = source_state(ROOT, list(workspace_map()), "linux")
            (output / "sources-after.json").write_text(json.dumps(after, indent=2) + "\n")
            if before:
                report["issues"].extend(source_issues(before, after, require_clean=True))
            _, _, pins = read_manifest(manifest)
            report["root_status_after"] = root_checkout_status(pins)
            if root_status_before is not None and report["root_status_after"] != root_status_before:
                report["issues"].append("root checkout status changed")
            if root_before is not None and subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip() != root_before:
                report["issues"].append("root revision changed")
            if manifest.read_bytes() != (output / "sources.json").read_bytes():
                report["issues"].append("source manifest changed")
        except Exception as exc:
            report["issues"].append(f"final source guard failed: {exc}")
        if not report["issues"] and report.get("pulse_cleanup_ok") and report.get("pcm_proof", {}).get("all_twelve_channels_proved"):
            report["status"] = "PRIVATE_LOOPBACK_PROVED"
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["status"] == "PRIVATE_LOOPBACK_PROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
