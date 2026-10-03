#!/usr/bin/python3
"""Exercise SotF's Linux accessibility adapter through a real AT-SPI bus."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from gi.repository import GLib
import pyatspi


def descendants(node, limit: int = 3000):
    pending = [node]
    visited = 0
    while pending:
        current = pending.pop()
        yield current
        visited += 1
        if visited >= limit:
            raise RuntimeError("AT-SPI tree exceeded 3000 nodes")
        pending.extend(reversed(list(current)))


def description(node) -> dict[str, str | bool]:
    return {
        "name": node.name or "",
        "role": node.getRoleName(),
        "showing": node.getState().contains(pyatspi.STATE_SHOWING),
    }


def find_sotf(desktop, pid: int):
    for app in desktop:
        if app.get_process_id() == pid:
            return app
    return None


def main() -> int:
    if not all(os.environ.get(name) for name in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR")):
        raise RuntimeError("AT-SPI smoke needs Xvfb, private D-Bus, and XDG_RUNTIME_DIR")

    output = Path(os.environ.get("SOTF_ATSPI_OUTPUT", "../release-ui-evidence-linux/atspi"))
    output.mkdir(parents=True, exist_ok=True)
    binary = Path("target/debug/sotf-desktop").resolve()
    if not binary.is_file():
        raise RuntimeError(f"locked desktop build is missing: {binary}")

    with tempfile.TemporaryDirectory(prefix="sotf-atspi-") as isolated:
        qa_dir = Path(isolated) / "qa"
        qa_dir.mkdir()
        env = os.environ.copy()
        env["SOTF_QA_DIR"] = str(qa_dir)
        status_changes = []
        for property_name in ("IsEnabled", "ScreenReaderEnabled"):
            call = subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--print-reply",
                    "--dest=org.a11y.Bus",
                    "/org/a11y/bus",
                    "org.freedesktop.DBus.Properties.Set",
                    "string:org.a11y.Status",
                    f"string:{property_name}",
                    "variant:boolean:true",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            readback = subprocess.run(
                [
                    "dbus-send",
                    "--session",
                    "--print-reply",
                    "--dest=org.a11y.Bus",
                    "/org/a11y/bus",
                    "org.freedesktop.DBus.Properties.Get",
                    "string:org.a11y.Status",
                    f"string:{property_name}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            if re.search(r"\bboolean\s+true\b", readback.stdout) is None:
                raise RuntimeError(f"private AT-SPI {property_name} did not read back true")
            status_changes.append(
                {"property": property_name, "set_reply": call.stdout.strip(), "readback": readback.stdout.strip()}
            )
        with (output / "desktop.stdout.log").open("w") as stdout, (
            output / "desktop.stderr.log"
        ).open("w") as stderr:
            process = subprocess.Popen(
                [str(binary), "--qa", str(qa_dir), "--size", "900x700"],
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
            events: list[dict[str, str | int]] = []
            result: dict[str, object] = {
                "app_pid": process.pid,
                "accessibility_status": status_changes,
                "action_invoked": False,
                "focus_requested": False,
            }
            started = time.monotonic()
            registry = pyatspi.Registry

            def on_event(event):
                if len(events) < 1000:
                    source_pid = event.source.getApplication().get_process_id()
                    events.append(
                        {
                            "type": event.type,
                            "source": getattr(event.source, "name", "") or "",
                            "source_pid": source_pid,
                            "detail1": event.detail1,
                        }
                    )

            def tick():
                if process.poll() is not None:
                    result["error"] = f"desktop exited with {process.returncode}"
                    registry.stop()
                    return False
                if time.monotonic() - started > 30:
                    result["error"] = "AT-SPI tree/action/focus event timed out after 30s"
                    registry.stop()
                    return False
                try:
                    desktop = registry.getDesktop(0)
                    app = find_sotf(desktop, process.pid)
                    if app is None:
                        result["desktop_apps"] = [
                            {"name": child.name, "pid": child.get_process_id()} for child in desktop
                        ]
                        return True
                    nodes = list(descendants(app))
                    tree = [description(node) for node in nodes]
                    if not result["action_invoked"]:
                        studio = next(
                            (
                                node
                                for node in nodes
                                if node.getRole() == pyatspi.ROLE_PUSH_BUTTON
                                and (node.name or "") == "Studio"
                            ),
                            None,
                        )
                        if studio is None:
                            return True
                        result["tree_before"] = tree
                        if any(
                            (node.name or "") == "Studio"
                            and node.getRole() == pyatspi.ROLE_COMBO_BOX
                            and node.getState().contains(pyatspi.STATE_SHOWING)
                            for node in nodes
                        ):
                            raise RuntimeError("Studio rack was already present before AT-SPI action")
                        component = studio.queryComponent()
                        result["focus_requested"] = bool(component.grabFocus())
                        action = studio.queryAction()
                        result["declared_actions"] = [
                            action.getName(index) for index in range(action.nActions)
                        ]
                        if action.nActions < 1 or not action.doAction(0):
                            raise RuntimeError("Studio AT-SPI button has no working Action")
                        result["action_invoked"] = True
                        return True
                    result["tree_after"] = tree
                    studio_picker_visible = any(
                        (node.name or "") == "Studio"
                        and node.getRole() == pyatspi.ROLE_COMBO_BOX
                        and node.getState().contains(pyatspi.STATE_SHOWING)
                        for node in nodes
                    )
                    rack_content_visible = any(
                        (node.name or "") in (
                            "Add a plugin to get started",
                            "Bypass plugin",
                            "Plugin configuration",
                        )
                        and node.getState().contains(pyatspi.STATE_SHOWING)
                        for node in nodes
                    )
                    result["studio_rack_visible"] = studio_picker_visible and rack_content_visible
                    result["focus_event_seen"] = any(
                        event["type"] == "object:state-changed:focused"
                        and event["source"] == "Studio"
                        and event["source_pid"] == process.pid
                        and event["detail1"] == 1
                        for event in events
                    )
                    if result["studio_rack_visible"] and result["focus_event_seen"]:
                        registry.stop()
                        return False
                except Exception as error:
                    result["error"] = repr(error)
                    registry.stop()
                    return False
                return True

            try:
                registry.registerEventListener(
                    on_event, "object:state-changed:focused", "object:children-changed"
                )
                GLib.timeout_add(100, tick)
                registry.start()
            finally:
                try:
                    registry.deregisterEventListener(
                        on_event, "object:state-changed:focused", "object:children-changed"
                    )
                except Exception as error:
                    result["listener_cleanup_error"] = repr(error)
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                result["events"] = events
                (output / "report.json").write_text(json.dumps(result, indent=2) + "\n")

    if result.get("error") or not all(
        result.get(key)
        for key in ("action_invoked", "focus_requested", "studio_rack_visible", "focus_event_seen")
    ):
        print(f"AT-SPI smoke failed: {result.get('error', 'missing tree/action/focus evidence')}")
        return 1
    print("AT-SPI smoke passed: real SotF tree, Studio action, rack transition, focus event")
    return 0


if __name__ == "__main__":
    sys.exit(main())
