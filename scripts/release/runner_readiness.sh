#!/usr/bin/env bash
# Read-only prerequisites for aggregate full QA. Run on the actual CI worker.
set -uo pipefail

platform=${1:?pass macos or linux}
failed=0
date -u '+probe_utc=%Y-%m-%dT%H:%M:%SZ'
hostname
uname -a
probe() {
    printf '\n== %s ==\n' "$1"
    shift
    "$@" || { printf 'FAILED: %s\n' "$*" >&2; failed=1; }
}

validator=${ROOMEQ_CAMILLADSP_BIN:-camilladsp}
probe camilladsp-location command -v "$validator"
if command -v "$validator" >/dev/null 2>&1; then
    probe camilladsp-version "$validator" --version
fi

case "$platform" in
    linux)
        probe docker-daemon docker info --format '{{.ServerVersion}} {{.OSType}}/{{.Architecture}}'
        image=${AUTOEQ_PIPEWIRE_BASE_IMAGE:-math-audio-base-linux-arm64:latest}
        probe pipewire-base-image docker image inspect "$image" --format '{{.Id}} {{.Os}}/{{.Architecture}}'
        probe landlock-and-seccomp python3 - <<'PY'
import ctypes
import os
import platform
from pathlib import Path

machine = platform.machine()
if machine not in {"x86_64", "aarch64"}:
    raise SystemExit(f"unsupported sandbox architecture: {machine}")
libc = ctypes.CDLL(None, use_errno=True)
abi = libc.syscall(444, None, 0, 1)  # landlock_create_ruleset, VERSION query
if abi < 0:
    code = ctypes.get_errno()
    raise SystemExit(f"Landlock ABI query failed: {os.strerror(code)} ({code})")
print(f"Landlock ABI: {abi}")
if abi < 4:
    raise SystemExit("Landlock ABI 4+ required for network denial")
actions = Path("/proc/sys/kernel/seccomp/actions_avail").read_text().strip()
print(f"seccomp actions: {actions}")
if "errno" not in actions.split():
    raise SystemExit("seccomp errno action unavailable")
PY
        ;;
    macos)
        if [[ -n ${ROOMEQ_EQUALIZER_APO_UTMCTL:-} ]]; then
            utmctl=$ROOMEQ_EQUALIZER_APO_UTMCTL
        elif command -v utmctl >/dev/null 2>&1; then
            utmctl=$(command -v utmctl)
        else
            utmctl=/Applications/UTM.app/Contents/MacOS/utmctl
        fi
        probe utm-vm-status "$utmctl" status "${ROOMEQ_EQUALIZER_APO_UTM_VM:-Win11 ARM AutoEQ}"
        # Stat only: neither reads contents nor changes the worker's state.
        state=${SOTF_SYSTEMWIDE_STATE_PATH:-$HOME/Library/Application Support/org.spinorama.sotf/systemwide-state.json}
        for path in "$state" "$(dirname "$state")/output-profiles.json"; do
            if [[ -e $path ]]; then
                probe installed-systemwide-path stat -f '%N %z bytes mtime_epoch=%m owner=%Su' "$path"
            else
                printf 'absent: %s\n' "$path"
            fi
        done
        ;;
    *) printf 'unsupported platform: %s\n' "$platform" >&2; exit 2 ;;
esac
exit "$failed"
