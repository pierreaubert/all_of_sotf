#!/usr/bin/env bash
set -u

platform=${1:?macos or linux required}
output=${2:?evidence directory required}
if [ "$platform" != macos ] && [ "$platform" != linux ]; then
    printf 'unsupported platform: %s\n' "$platform" >&2
    exit 2
fi
mkdir -p "$output"
cp scripts/release/sources.json "$output/sources.json"
{
    date -u
    uname -a
    python3 --version
    rustc --version
    cargo --version
    just --version
} >"$output/toolchain.txt" 2>&1
failed=0

source_state() {
    python3 - "$output/source-before.json" "$output/source-after.json" "$1" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path.cwd()
before_path, after_path = map(pathlib.Path, sys.argv[1:3])
mode = sys.argv[3]
sources = json.loads((root / "scripts/release/sources.json").read_text())["sources"]
state = {}
for name, entry in sources.items():
    path = root / name
    revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    tracked = subprocess.check_output(["git", "-C", str(path), "diff", "--name-only", "HEAD"], text=True).splitlines()
    state[name] = {
        "revision": revision,
        "tracked_status": tracked,
        "lock_sha256": hashlib.sha256((path / "Cargo.lock").read_bytes()).hexdigest(),
    }
    if mode == "before" and (revision != entry["revision"] or tracked):
        raise SystemExit(f"{name}: source differs from clean pinned revision")
destination = before_path if mode == "before" else after_path
destination.write_text(json.dumps(state, indent=2) + "\n")
if mode == "after" and state != json.loads(before_path.read_text()):
    raise SystemExit("Pinned source revision, tracked status, or Cargo.lock changed")
PY
}

source_state before || exit 1

run_check() {
    local name=$1 workspace=$2
    shift 2
    local log="$output/$name.log"
    printf '[%s] %s\n' "$name" "$*"
    (cd "$workspace" && "$@") >"$log" 2>&1
    local status=$?
    printf '[%s] exit %s; log: %s\n' "$name" "$status" "$log"
    if [ "$status" -ne 0 ]; then
        tail -n 80 "$log"
        failed=1
    elif [ "$name" = daw-engine-lab-tests ] || [ "$name" = systemwide-ipc-lab-tests ]; then
        if ! grep -Eq '^running [1-9][0-9]* tests?$' "$log"; then
            printf '[%s] no filtered tests executed\n' "$name" >&2
            failed=1
        fi
    fi
}

run_check daw-engine-lab-tests sotf-daw cargo test -p sotf-engine --lib --locked lab_tests
run_check daw-engine-all-targets sotf-daw cargo check -p sotf-engine --all-targets --locked
run_check systemwide-ipc-lab-tests sotf-systemwide cargo test -p sotf-daemon --test ipc_line_tests --locked systemwide_lab_
if [ "$platform" = macos ]; then
    run_check systemwide-isolated-lab sotf-systemwide just systemwide-lab
fi

source_state after || failed=1
exit "$failed"
