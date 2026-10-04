#!/usr/bin/env python3
"""Materialize the exact sibling revisions recorded for an aggregate release run.

The manifest is committed with the aggregate workflow.  Every child checkout is
detached at its recorded commit, so a moving branch cannot change QA inputs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from workspaces import workspace_names

REVISION = re.compile(r"[0-9a-f]{40}\Z")
OWNER = re.compile(r"[A-Za-z0-9_.-]+\Z")


def read_manifest(path: Path) -> tuple[str, str, dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ValueError("source manifest schema must be 1")
    server = data.get("server")
    owner = data.get("owner")
    if not isinstance(server, str) or not isinstance(owner, str):
        raise ValueError("manifest requires server and owner strings")
    parsed = urlsplit(server)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("manifest server must be an HTTP(S) origin without credentials")
    if parsed.path.strip("/") or parsed.query or parsed.fragment:
        raise ValueError("manifest server must not include a path, query, or fragment")
    if not OWNER.fullmatch(owner):
        raise ValueError("invalid manifest owner")
    sources = data.get("sources")
    names = set(workspace_names())
    if not isinstance(sources, dict) or set(sources) != names:
        raise ValueError(f"manifest sources must match inventory: {sorted(names)}")
    revisions: dict[str, str] = {}
    for name, entry in sources.items():
        if not isinstance(entry, dict) or set(entry) != {"revision"}:
            raise ValueError(f"{name}: expected only a revision field")
        revision = entry["revision"]
        if not isinstance(revision, str) or not REVISION.fullmatch(revision):
            raise ValueError(f"{name}: revision must be a full lowercase Git SHA")
        revisions[name] = revision
    return server.rstrip("/"), owner, revisions


def git(*args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args], check=False, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env,
    )
    if result.returncode:
        stderr = result.stderr.strip()
        # Git may echo a server message; do not let it expose the credential.
        secrets = [os.environ.get("GITEA_TOKEN", "")]
        if env:
            secrets.append(env.get("GIT_CONFIG_VALUE_0", ""))
        for secret in secrets:
            if secret:
                stderr = stderr.replace(secret, "[redacted]")
        tail = "\n".join(stderr.splitlines()[-5:])
        raise RuntimeError(f"git {args[0]} exited {result.returncode}: {tail}")
    # Preserve the two-column porcelain prefix: a leading space means an
    # unstaged change and is significant for gitlink preflight checks.
    return result.stdout.rstrip("\n")


def gitlink_revision(root: Path, name: str) -> str | None:
    """Return a tracked sibling gitlink SHA, rejecting other indexed content."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "--", name],
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(f"{name}: could not inspect root Git index")
    if not result.stdout:
        return None
    lines = result.stdout.splitlines()
    if len(lines) != 1:
        raise ValueError(f"{name}: expected one sibling gitlink in root index")
    metadata, separator, path = lines[0].partition("\t")
    fields = metadata.split()
    if not separator or path != name or len(fields) != 3 or fields[0] != "160000" or fields[2] != "0":
        raise ValueError(f"{name}: root index entry is not a stage-zero gitlink")
    if not REVISION.fullmatch(fields[1]):
        raise ValueError(f"{name}: invalid root gitlink revision")
    return fields[1]


def root_layout_status(root: Path, revisions: dict[str, str]) -> dict:
    """Require exact sibling gitlinks or the legacy untracked-clone layout."""
    lines = set(git("-C", str(root), "status", "--porcelain", "--untracked-files=normal").splitlines())
    allowed_untracked = set()
    tracked_gitlinks = []
    missing = []
    for name, revision in revisions.items():
        indexed = gitlink_revision(root, name)
        if indexed is None:
            entry = f"?? {name}/"
            allowed_untracked.add(entry)
            if entry not in lines:
                missing.append(name)
        elif indexed == revision:
            tracked_gitlinks.append(name)
        else:
            missing.append(f"{name}: root gitlink pin mismatch")
    return {"allowed_siblings": sorted(lines & allowed_untracked),
            "tracked_gitlinks": sorted(tracked_gitlinks), "missing": sorted(missing),
            "unexpected": sorted(lines - allowed_untracked)}


def clone_env(server: str, owner: str) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    token = env.pop("GITEA_TOKEN", "")
    if token:
        # Keep the token out of argv, the manifest, and command logs.
        username = env.pop("GITEA_USER", owner)
        credential = base64.b64encode(f"{username}:{token}".encode()).decode("ascii")
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = f"http.{server}/.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {credential}"
    return env


def prepare_destinations(root: Path, revisions: dict[str, str]) -> None:
    """Allow only absent sibling paths or empty directories for exact gitlinks."""
    empty_gitlink_directories = []
    for name in workspace_names():
        destination = root / name
        indexed = gitlink_revision(root, name)
        if indexed is not None and indexed != revisions[name]:
            raise ValueError(f"{name}: root gitlink differs from source manifest")
        if destination.is_symlink():
            raise ValueError(f"checkout destination is a symlink: {destination}")
        if destination.exists():
            if indexed is None or not destination.is_dir() or any(destination.iterdir()):
                raise ValueError(f"checkout destination already exists: {destination}")
            empty_gitlink_directories.append(destination)
    for destination in empty_gitlink_directories:
        destination.rmdir()


def preflight_root(root: Path, revisions: dict[str, str]) -> None:
    # Git reports an absent tracked gitlink as " D name". It also reports that
    # status after we remove checkout's empty placeholder directory below.
    # Accept only that exact pre-clone absence for a pinned gitlink.
    preflight = root_layout_status(root, revisions)
    allowed_absent = {
        f" D {name}" for name in revisions
        if gitlink_revision(root, name) == revisions[name]
        and not (root / name).exists()
    }
    legacy_absent = {
        name for name in revisions
        if gitlink_revision(root, name) is None
        and not (root / name).exists()
        and not (root / name).is_symlink()
    }
    if set(preflight["missing"]) - legacy_absent or set(preflight["unexpected"]) - allowed_absent:
        raise ValueError("root checkout is dirty before sibling materialization")


def checkout(root: Path, server: str, owner: str, revisions: dict[str, str]) -> None:
    preflight_root(root, revisions)
    prepare_destinations(root, revisions)
    env = clone_env(server, owner)
    for name in workspace_names():
        revision = revisions[name]
        destination = root / name
        temporary = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=root))
        shutil.rmtree(temporary)
        url = f"{server}/{owner}/{name}.git"
        print(f"[{name}] cloning {url} at {revision}", flush=True)
        try:
            git("clone", "--no-checkout", url, str(temporary), env=env)
            git("-C", str(temporary), "checkout", "--detach", revision, env=env)
            actual = git("-C", str(temporary), "rev-parse", "HEAD", env=env)
            if actual != revision:
                raise ValueError(f"{name}: checked out {actual}, expected {revision}")
            if git("-C", str(temporary), "status", "--porcelain", env=env):
                raise ValueError(f"{name}: checkout is dirty")
            temporary.rename(destination)
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
    layout = root_layout_status(root, revisions)
    if layout["missing"] or layout["unexpected"]:
        raise ValueError(f"root checkout has missing or unexpected paths: {layout}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "scripts" / "release" / "sources.json")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    server, owner, revisions = read_manifest(args.manifest)
    event_server = os.environ.get("GITHUB_SERVER_URL")
    if event_server and event_server.rstrip("/") != server:
        raise ValueError(f"manifest server {server} differs from Gitea event server {event_server}")
    root = args.root.resolve()
    if not root.is_dir():
        raise ValueError(f"checkout root does not exist: {root}")
    checkout(root, server, owner, revisions)
    print(f"checked out {len(revisions)} pinned source repositories", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as error:
        print(f"source checkout failed: {error}", file=sys.stderr)
        raise SystemExit(1)
