#!/usr/bin/env bash
# Inspect the actual private X display before the unchanged strict plugin checks.
set -euo pipefail

evidence=${SOTF_ARTIFACT_EVIDENCE_DIR:?job-local evidence directory required}
[[ $evidence == /* ]] || { echo 'evidence directory must be absolute' >&2; exit 2; }
test -n "${DISPLAY:-}"
mkdir -p "$evidence/glx"
printf 'DISPLAY=%s\n' "$DISPLAY" > "$evidence/glx/display.txt"
xdpyinfo -ext GLX > "$evidence/glx/xdpyinfo-glx.txt" 2>&1
glxinfo -B > "$evidence/glx/renderer.txt" 2>&1
glxinfo -t > "$evidence/glx/fbconfigs.txt" 2>&1
grep -Fq 'OpenGL renderer string:' "$evidence/glx/renderer.txt"
grep -Eq 'GLXFBConfigs|GLX FBConfigs' "$evidence/glx/fbconfigs.txt"
printf 'GLX renderer and framebuffer inventory retained for %s\n' "$DISPLAY"

# The same Xvfb and DBus session now runs the original 43-plugin strict checks,
# including pluginval's unmodified Convolution Editor case.
exec bash scripts/release/artifact_check.sh plugins linux
