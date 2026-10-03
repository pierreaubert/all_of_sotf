#!/usr/bin/env python3
"""Download and verify the immutable macOS plugin artifact from Gitea run 469."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import urllib.request
import zipfile


RUN_ID = 469
ARTIFACT = "release-artifact-macos-plugins"
BASE = "http://192.168.1.32:3001"
SOURCES_SHA256 = "3822970099871516b1a998e1346b8973c334d607b98ded05abd7d7bad04d86a4"
INVENTORY_SHA256 = "0f59c2df5eea5ad01a789aa1b5b91d45348dcc0b3347d61affb0880bf2374748"
ROOT = Path("prior-plugin-artifact")
EVIDENCE = ROOT / "release-artifact-evidence-plugins-macos"
MAX_DOWNLOAD = 2_000_000_000
MAX_EXTRACTED = 3_000_000_000


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def safe_member(info: zipfile.ZipInfo) -> Path:
    name = PurePosixPath(info.filename)
    if name.is_absolute() or not name.parts or any(part in ("", ".", "..") for part in name.parts):
        raise ValueError(f"unsafe artifact member: {info.filename!r}")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise ValueError(f"artifact symlink is not allowed: {info.filename!r}")
    return ROOT.joinpath(*name.parts)


def main() -> None:
    token = os.environ.get("GITEA_TOKEN", "")
    if not token:
        raise ValueError("GITEA_TOKEN is required")
    if shutil.disk_usage(Path.cwd()).free < 4_000_000_000:
        raise ValueError("at least 4 GB free space is required for baseline plugin artifact validation")
    ROOT.mkdir(exist_ok=False)
    url = f"{BASE}/pierre/all_of_sotf/actions/runs/{RUN_ID}/artifacts/{ARTIFACT}"
    auth = base64.b64encode(f"pierre:{token}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    archive_path = ROOT / f"{ARTIFACT}.zip"
    total = 0
    with urllib.request.urlopen(request, timeout=300) as response, archive_path.open("wb") as target:
        if response.status != 200:
            raise ValueError(f"artifact download returned HTTP {response.status}")
        for block in iter(lambda: response.read(1024 * 1024), b""):
            total += len(block)
            if total > MAX_DOWNLOAD:
                raise ValueError("artifact download exceeds 2 GB limit")
            target.write(block)
    print(f"Downloaded Gitea run {RUN_ID} artifact: {total} bytes", flush=True)

    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > 2048 or sum(info.file_size for info in infos) > MAX_EXTRACTED:
            raise ValueError("artifact archive exceeds entry or extracted-size limit")
        for info in infos:
            destination = safe_member(info)
            if destination == ROOT / "checkout-sources.log":
                continue
            if not destination.is_relative_to(EVIDENCE):
                raise ValueError(f"unexpected artifact path: {info.filename!r}")
            archive.extract(info, ROOT)
    archive_path.unlink()

    sources = EVIDENCE / "sources.json"
    inventory_path = EVIDENCE / "artifact-inventory.json"
    if digest(sources) != SOURCES_SHA256 or digest(inventory_path) != INVENTORY_SHA256:
        raise ValueError("run 469 source manifest or artifact inventory hash changed")
    manifest = json.loads(sources.read_text())
    before = json.loads((EVIDENCE / "source-before.json").read_text())
    after = json.loads((EVIDENCE / "source-after.json").read_text())
    if before != after:
        raise ValueError("run 469 source or lock state changed during build")
    for name, expected in manifest["sources"].items():
        observed = before.get(name)
        if not observed or observed["revision"] != expected["revision"] or observed["tracked_status"]:
            raise ValueError(f"run 469 source state mismatch: {name}")

    inventory = json.loads(inventory_path.read_text())
    expected_files: set[str] = set()
    for item in inventory:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:3] != ("artifacts", "sotf-daw", "dist"):
            raise ValueError(f"invalid inventory path: {item['path']!r}")
        file = EVIDENCE.joinpath(*relative.parts)
        if not file.is_file() or file.stat().st_size != item["size"] or digest(file) != item["sha256"]:
            raise ValueError(f"inventory hash/size mismatch: {file}")
        expected_files.add(relative.as_posix())
    actual_files = {path.relative_to(EVIDENCE).as_posix() for path in (EVIDENCE / "artifacts").rglob("*") if path.is_file()}
    if actual_files != expected_files:
        raise ValueError("artifact files differ from pinned inventory")
    clap = list((EVIDENCE / "artifacts/sotf-daw/dist/clap").glob("*.clap"))
    vst3 = list((EVIDENCE / "artifacts/sotf-daw/dist/vst3").glob("*.vst3"))
    if len(clap) != 43 or len(vst3) != 43 or len(inventory) != 129:
        raise ValueError(f"expected 43 CLAP, 43 VST3, 129 files; got {len(clap)}, {len(vst3)}, {len(inventory)}")
    # ZipFile.extract does not restore executable mode. Hashes above validate bytes first.
    for plugin in clap:
        plugin.chmod(0o755)
    for plugin in vst3:
        binaries = list((plugin / "Contents/MacOS").iterdir())
        if len(binaries) != 1 or not binaries[0].is_file():
            raise ValueError(f"unexpected VST3 executable layout: {plugin}")
        binaries[0].chmod(0o755)
    report = {
        "provenance": "Gitea run 469, root 6cbb69cb3302d099e1788033f0fe5a7dc1507813",
        "qualification": "baseline artifact validation diagnostic only",
        "sources_sha256": SOURCES_SHA256,
        "inventory_sha256": INVENTORY_SHA256,
        "files_verified": len(inventory),
        "clap_plugins": len(clap),
        "vst3_plugins": len(vst3),
    }
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
