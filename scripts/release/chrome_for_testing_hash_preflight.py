#!/usr/bin/env python3
"""Record the digest of one official Chrome for Testing archive on Gitea."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request


VERSION = "154.0.8037.92"
URL = (
    "https://storage.googleapis.com/chrome-for-testing-public/"
    f"{VERSION}/linux64/chrome-linux64.zip"
)
MAX_BYTES = 250 * 1024 * 1024


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: chrome_for_testing_hash_preflight.py OUTPUT_DIR", file=sys.stderr)
        return 2
    if not Path("/.dockerenv").exists() or os.geteuid() != 0:
        print("Chrome hash preflight requires a disposable root-owned Gitea container", file=sys.stderr)
        return 2
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    first = b""
    try:
        request = urllib.request.Request(URL, headers={"User-Agent": "sotf-release-qa/1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200 or response.geturl() != URL:
                raise RuntimeError("unexpected Chrome archive response or redirect")
            while chunk := response.read(1024 * 1024):
                if not first:
                    first = chunk[:4]
                total += len(chunk)
                if total > MAX_BYTES:
                    raise RuntimeError("Chrome archive exceeds 250 MiB limit")
                digest.update(chunk)
        if first != b"PK\x03\x04" or total < 10 * 1024 * 1024:
            raise RuntimeError("response is not a plausible Chrome ZIP archive")
        report = {"status": "HASH_RECORDED_ONLY", "version": VERSION, "url": URL,
                  "sha256": digest.hexdigest(), "bytes": total,
                  "executed": False, "extracted": False}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except Exception as error:
        (output / "error.txt").write_text(f"{type(error).__name__}: {error}\n")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
