#!/usr/bin/env bash
#
# Linux release gate (linux-20261104.md Phase 6.3): run against the
# artifacts that will actually ship, after the pinned ubuntu:24.04
# builders produced them:
#
#   1. CPU/glibc floor gate over every dist/ artifact
#      (scripts/check-linux-artifact.sh: x86-64-v2, no SSE4a,
#      GLIBC_ <= 2.39).
#   2. .deb control sanity + clean-container install simulation
#      (`apt-get -s install`) on Ubuntu 24.04 (supported floor) and
#      Debian trixie (best-effort tier).
#   3. AppImage execution smoke under Xvfb: `--version` must print,
#      and a GUI launch must stay alive (timeout kill = pass) with
#      no crash output. The AppImage keeps host ALSA/PipeWire
#      libraries, so the host needs libpipewire-0.3-0 (client
#      library only).
#   4. `just dev-driver-smoke` on this Linux host, provisioning a
#      no-sudo PipeWire header sysroot when pkg-config cannot find
#      libpipewire-0.3.
#
# Usage:
#   scripts/release/linux_release_gate.sh [--skip-containers]
#                                         [--skip-appimage]
#                                         [--skip-dev-driver]
#
# Dist directories default to sotf/dist and sotf-systemwide/dist
# relative to the aggregate root; override with SOTF_DIST_DIRS
# (colon-separated).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKIP_CONTAINERS=false
SKIP_APPIMAGE=false
SKIP_DEV_DRIVER=false
for arg in "$@"; do
    case "$arg" in
        --skip-containers) SKIP_CONTAINERS=true ;;
        --skip-appimage) SKIP_APPIMAGE=true ;;
        --skip-dev-driver) SKIP_DEV_DRIVER=true ;;
        *)
            echo "unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

log() { printf '\n== %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

IFS=':' read -r -a DIST_DIRS <<< "${SOTF_DIST_DIRS:-$ROOT/sotf/dist:$ROOT/sotf-systemwide/dist}"
ARTIFACTS=()
for dir in "${DIST_DIRS[@]}"; do
    [ -d "$dir" ] || continue
    while IFS= read -r -d '' file; do
        ARTIFACTS+=("$file")
    done < <(find "$dir" -maxdepth 2 -type f \
        \( -name '*.AppImage' -o -name '*.deb' -o -name '*.tar.gz' \) -print0)
done
[ "${#ARTIFACTS[@]}" -gt 0 ] || fail "no .AppImage/.deb/.tar.gz artifacts under: ${DIST_DIRS[*]}"

log "1/4 CPU/glibc floor gate (${#ARTIFACTS[@]} artifacts)"
"$ROOT/scripts/check-linux-artifact.sh" "${ARTIFACTS[@]}" \
    || fail "check-linux-artifact.sh rejected an artifact"

DEBS=()
APPIMAGES=()
for file in "${ARTIFACTS[@]}"; do
    case "$file" in
        *.deb) DEBS+=("$file") ;;
        *.AppImage) APPIMAGES+=("$file") ;;
    esac
done

if [ "$SKIP_CONTAINERS" = false ]; then
    log "2/4 .deb install simulation (ubuntu:24.04 + debian:trixie)"
    [ "${#DEBS[@]}" -gt 0 ] || fail "no .deb artifacts to install-check"
    for deb in "${DEBS[@]}"; do
        dpkg-deb --info "$deb" >/dev/null || fail "dpkg-deb --info failed: $deb"
        deb_dir="$(dirname "$deb")"
        deb_base="$(basename "$deb")"
        for image in ubuntu:24.04 debian:trixie; do
            echo "-- $image: $deb_base"
            docker run --rm -v "$deb_dir:/artifacts:ro" "$image" \
                bash -c "apt-get update -qq >/dev/null 2>&1 && apt-get -s install -y '/artifacts/$deb_base' >/dev/null" \
                || fail "apt install simulation failed for $deb_base on $image"
        done
    done
else
    log "2/4 .deb install simulation skipped"
fi

if [ "$SKIP_APPIMAGE" = false ]; then
    log "3/4 AppImage execution smoke (Xvfb)"
    [ "${#APPIMAGES[@]}" -gt 0 ] || fail "no .AppImage artifacts to smoke-test"
    command -v xvfb-run >/dev/null || fail "xvfb-run is required for the AppImage smoke"
    for app in "${APPIMAGES[@]}"; do
        qa_dir="$(mktemp -d)"
        # Isolate runtime state: the daemon AppImage would otherwise
        # bind the host's real daemon socket during the smoke.
        export SOTF_SYSTEMWIDE_RUNTIME_DIR="$qa_dir/runtime"
        export XDG_CONFIG_HOME="$qa_dir/config"
        mkdir -p "$SOTF_SYSTEMWIDE_RUNTIME_DIR" "$XDG_CONFIG_HOME"
        echo "-- $app --version"
        set +e
        version_out="$(timeout 10 xvfb-run -a "$app" --appimage-extract-and-run --version 2>&1)"
        version_status=$?
        set -e
        case "$version_status" in
            0)
                [ -n "$version_out" ] || fail "AppImage --version printed nothing: $app"
                echo "   $version_out"
                ;;
            124)
                # Long-running program without a version flag (the
                # daemon): staying alive is the pass signal here,
                # the launch check below covers crash detection.
                echo "   (no --version flag; still running at timeout — ok)"
                ;;
            *)
                fail "AppImage --version failed (exit $version_status): $app"
                ;;
        esac
        echo "-- $app launch (8s alive check)"
        set +e
        timeout 8 xvfb-run -a "$app" --appimage-extract-and-run --qa "$qa_dir" \
            > "$qa_dir/appimage-smoke.log" 2>&1
        launch_status=$?
        set -e
        case "$launch_status" in
            124) echo "   GUI stayed alive until timeout (pass)" ;;
            0) fail "AppImage GUI exited immediately: $app (log: $qa_dir/appimage-smoke.log)" ;;
            *) fail "AppImage GUI crashed (exit $launch_status): $app (log: $qa_dir/appimage-smoke.log)" ;;
        esac
        if grep -qiE "panicked at|segmentation fault|illegal instruction" "$qa_dir/appimage-smoke.log"; then
            fail "AppImage GUI log contains a crash: $app (log: $qa_dir/appimage-smoke.log)"
        fi
        rm -rf "$qa_dir"
    done
else
    log "3/4 AppImage execution smoke skipped"
fi

if [ "$SKIP_DEV_DRIVER" = false ]; then
    log "4/4 dev-driver smoke on Linux"
    if ! pkg-config --exists libpipewire-0.3 2>/dev/null; then
        sysroot="$ROOT/sotf/tmp/pipewire-dev/root"
        if [ ! -f "$sysroot/usr/lib/x86_64-linux-gnu/pkgconfig/libpipewire-0.3.pc" ]; then
            echo "-- provisioning PipeWire header sysroot (no sudo)"
            mkdir -p "$ROOT/sotf/tmp/pipewire-dev/debs" "$sysroot"
            (cd "$ROOT/sotf/tmp/pipewire-dev/debs" \
                && apt-get download libpipewire-0.3-dev libspa-0.2-dev >/dev/null 2>&1) \
                || fail "could not download PipeWire dev packages for the sysroot"
            for pkg in "$ROOT"/sotf/tmp/pipewire-dev/debs/*.deb; do
                dpkg-deb -x "$pkg" "$sysroot"
            done
        fi
        export PKG_CONFIG_SYSROOT_DIR="$sysroot"
        export PKG_CONFIG_PATH="$sysroot/usr/lib/x86_64-linux-gnu/pkgconfig"
    fi
    (cd "$ROOT/sotf" && just dev-driver-smoke) || fail "dev-driver-smoke failed"
else
    log "4/4 dev-driver smoke skipped"
fi

log "Linux release gate: all stages passed"
