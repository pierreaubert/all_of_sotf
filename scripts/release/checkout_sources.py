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
    return result.stdout.strip()


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


def checkout(root: Path, server: str, owner: str, revisions: dict[str, str]) -> None:
    for name in workspace_names():
        destination = root / name
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"checkout destination already exists: {destination}")
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
