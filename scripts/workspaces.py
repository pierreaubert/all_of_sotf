#!/usr/bin/env python3
"""Read the shared inventory used by workspace checks and release tooling."""

import json
from pathlib import Path


INVENTORY = Path(__file__).resolve().parent / "quality-matrix" / "repos.json"


def workspace_names() -> list[str]:
    """Return the Rust workspace paths in stable inventory order."""
    entries = json.loads(INVENTORY.read_text(encoding="utf-8"))["repositories"]
    names = [entry["path"] for entry in entries if entry["primary_language"] == "Rust"]
    if len(names) != len(set(names)):
        raise ValueError("duplicate workspace paths in repository inventory")
    for name in names:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError(f"workspace must be a direct child directory: {name!r}")
    return names


if __name__ == "__main__":
    print("\n".join(workspace_names()))
