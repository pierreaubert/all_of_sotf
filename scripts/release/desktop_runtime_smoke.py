#!/usr/bin/env python3
"""Launch and inspect the staged production desktop without touching user state."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def command(args: list[str], timeout: int = 10) -> str:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"{args[0]} exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout.strip()


def atspi(pid: int) -> str:
    # Use the distribution Python which owns the installed PyGObject bindings.
    import pyatspi

    desktop = pyatspi.Registry.getDesktop(0)
    for app in desktop:
        if app.get_process_id() != pid:
            continue
        windows = [node for node in app if node.getState().contains(pyatspi.STATE_SHOWING)]
        if not any((node.name or "") == "SotF" for node in windows):
            break
        return json.dumps({
            "pid": pid, "application": app.name,
            "windows": [{"name": node.name, "role": node.getRoleName()} for node in windows],
        })
    raise RuntimeError(f"no showing AT-SPI window owned by PID {pid}")


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--atspi":
        print(atspi(int(sys.argv[2])))
        return 0
    if len(sys.argv) != 5:
        raise SystemExit("usage: desktop_runtime_smoke.py macos|linux STAGED BUILT EVIDENCE")
    platform, staged_arg, built_arg, evidence_arg = sys.argv[1:]
    if platform not in ("macos", "linux"):
        raise RuntimeError(f"unsupported desktop smoke platform: {platform}")
    staged, built, evidence = map(Path, (staged_arg, built_arg, evidence_arg))
    staged = staged.resolve(strict=True)
    built = built.resolve(strict=True)
    evidence = evidence.resolve(strict=True)
    output = evidence / "desktop-runtime"
    output.mkdir(parents=True, exist_ok=True)
    source_hash = digest(built)
    staged_hash = digest(staged)
    if source_hash != staged_hash:
        raise RuntimeError("staged desktop bytes differ from freshly built binary")
    report: dict[str, object] = {"built_sha256": source_hash, "staged_sha256": staged_hash}
    process: subprocess.Popen[bytes] | None = None

    def interrupted(signum: int, _frame: object) -> None:
        raise InterruptedError(f"desktop smoke interrupted by signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    with tempfile.TemporaryDirectory(prefix="sotf-desktop-release-") as temporary:
        private = Path(temporary)
        paths = {name: private / name.lower() for name in (
            "HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "TMPDIR"
        )}
        for path in paths.values():
            path.mkdir(mode=0o700)
        state = private / "sotf-qa"
        state.mkdir(mode=0o700)
        env = os.environ.copy()
        env.update({key: str(value) for key, value in paths.items()})
        env["CFFIXED_USER_HOME"] = str(paths["HOME"])
        if platform == "linux":
            for key in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
                if not env.get(key):
                    raise RuntimeError(f"private display prerequisite missing: {key}")
            # The private session bus is created by the disposable Gitea lane.
            for property_name in ("IsEnabled", "ScreenReaderEnabled"):
                command([
                    "dbus-send", "--session", "--print-reply", "--dest=org.a11y.Bus",
                    "/org/a11y/bus", "org.freedesktop.DBus.Properties.Set",
                    "string:org.a11y.Status", f"string:{property_name}", "variant:boolean:true",
                ], timeout=5)
        else:
            helper = private / "desktop-window"
            source = Path(__file__).with_name("desktop_runtime_macos_window.swift")
            command(["swiftc", str(source), "-o", str(helper)], timeout=60)
            preflight = command([str(helper), "prereq"])
            (output / "tcc-preflight.txt").write_text(preflight + "\n")
            if "accessibility_preflight=true" not in preflight or "screen_capture_preflight=true" not in preflight:
                raise RuntimeError("macOS Accessibility and Screen Capture grants are required on the CI runner")
            runner = command(["id", "-un"])
            console = command(["stat", "-f", "%Su", "/dev/console"])
            if runner != console:
                raise RuntimeError(f"runner {runner} does not own active GUI console {console}")
            command(["launchctl", "print", f"gui/{os.getuid()}"], timeout=5)
        try:
            with (output / "desktop.stdout.log").open("wb") as stdout, (output / "desktop.stderr.log").open("wb") as stderr:
                process = subprocess.Popen(
                    [str(staged), "--qa", str(state), "--size", "1280x800"],
                    env=env, stdout=stdout, stderr=stderr, start_new_session=True,
                )
                report["pid"] = process.pid
                report["binary"] = str(staged)
                deadline = time.monotonic() + 75
                last_error = "window has not appeared"
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError(f"production desktop exited early with status {process.returncode}")
                    try:
                        if platform == "linux":
                            windows = command([
                                "xdotool", "search", "--all", "--onlyvisible", "--pid",
                                str(process.pid), "--name", "^SotF$",
                            ], timeout=5).splitlines()
                            if len(windows) != 1:
                                raise RuntimeError(f"expected one PID-owned SotF window, found {windows}")
                            window = windows[0]
                            accessibility = command([
                                "/usr/bin/python3", str(Path(__file__)), "--atspi", str(process.pid)
                            ], timeout=5)
                            report["accessibility"] = json.loads(accessibility)
                            screenshot = output / "desktop.png"
                            command(["import", "-window", window, "-silent", f"PNG:{screenshot}"], timeout=10)
                            dimensions = command([
                                "identify", "-format", "%w %h %[fx:mean] %[fx:standard_deviation]",
                                str(screenshot),
                            ], timeout=5).split()
                            width, height = map(int, dimensions[:2])
                            mean, deviation = map(float, dimensions[2:])
                            if width < 600 or height < 400 or not (0.02 < mean < 0.98 and deviation > 0.005):
                                raise RuntimeError(f"unpainted or undersized desktop screenshot: {dimensions}")
                            report.update({"window_id": window, "pixels": [width, height], "mean": mean, "deviation": deviation})
                        else:
                            window = command([str(helper), "desktop-window", str(process.pid)])
                            accessibility = command([str(helper), "desktop-ax", str(process.pid)])
                            report["accessibility"] = json.loads(accessibility)
                            screenshot = output / "desktop.png"
                            command(["screencapture", "-x", "-o", "-l", window, str(screenshot)], timeout=10)
                            stats = command([str(helper), "stats", str(screenshot)])
                            report.update({"window_id": window, "screenshot_stats": stats})
                        if process.poll() is not None:
                            raise RuntimeError(f"production desktop exited during capture with status {process.returncode}")
                        break
                    except (RuntimeError, subprocess.SubprocessError, ValueError) as error:
                        last_error = str(error)
                        time.sleep(0.5)
                else:
                    raise RuntimeError(f"desktop window/accessibility/paint timed out: {last_error}")
                report["result"] = "passed"
        except BaseException as error:
            report["error"] = repr(error)
            raise
        finally:
            # Coalesce repeated cancellation while the owned process group exits.
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=5)
                # Descendants can outlive the desktop PID; close the owned group.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                report["cleanup_exit_status"] = process.returncode
            for path in (state / "sotf_crash.log", staged.with_name("sotf_crash.log")):
                if path.exists():
                    (output / "crash.log").write_bytes(path.read_bytes())
            report["staged_sha256_after"] = digest(staged)
            if report["staged_sha256_after"] != staged_hash:
                report["error"] = "staged desktop binary changed during runtime smoke"
            (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if digest(staged) != staged_hash:
        raise RuntimeError("staged desktop binary changed during runtime smoke")
    print(f"Production desktop painted and exposed accessibility: PID {report['pid']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"production desktop smoke failed: {error}", file=sys.stderr)
        sys.exit(1)
