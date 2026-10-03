#!/usr/bin/env bash
set -u

platform=${1:?platform required}
output="release-ui-evidence-$platform"
mkdir -p "$output"
cp scripts/release/sources.json "$output/sources.json" || exit 1
cp sotf/crates/sotf-dev-driver/suites/plugin_workflow_ui.toml "$output/plugin_workflow_ui.toml" || exit 1
{
    date -u
    uname -a
    printf 'DISPLAY=%s\n' "${DISPLAY:-}"
    printf 'WAYLAND_DISPLAY=%s\n' "${WAYLAND_DISPLAY:-}"
    python3 --version
    rustc --version
    cargo --version
    just --version
} >"$output/toolchain-display.txt" 2>&1
failed=0

run_check() {
    local name=$1 workspace=$2 required_test=$3
    shift 3
    local log="$output/$name.log"
    printf '[%s] %s\n' "$name" "$*"
    (cd "$workspace" && "$@") >"$log" 2>&1
    local status=$?
    if [ "$status" -eq 0 ] && [ "$required_test" = yes ] && ! grep -Eq 'test result: ok\. [1-9][0-9]* passed' "$log"; then
        printf 'No matching test executed\n' >>"$log"
        status=1
    fi
    printf '[%s] exit %s; log: %s\n' "$name" "$status" "$log"
    if [ "$status" -ne 0 ]; then
        tail -n 80 "$log"
        failed=1
    fi
    return "$status"
}

run_check toolkit-horizontal-accordion gpui-toolkit yes cargo test --locked -p gpui-ui-kit --test integration_tests horizontal_accordion_content_spans_header_width
run_check toolkit-side-accordion gpui-toolkit yes cargo test --locked -p gpui-ui-kit --test integration_tests side_accordion_places_tabs_on_both_sides_of_content
run_check toolkit-wizard-width gpui-toolkit yes cargo test --locked -p gpui-ui-kit --test integration_tests wizard_step_labels_follow_rendered_viewport_width
if run_check sotf-dev-driver-build sotf no just dev-driver-build-gpui; then
    run_check sotf-plugin-workflow-ui sotf no cargo run --locked -p sotf-dev-driver -- run-suite crates/sotf-dev-driver/suites/plugin_workflow_ui.toml -v
else
    printf 'NOT_RUN: sotf-dev-driver-build failed\n' | tee "$output/sotf-plugin-workflow-ui.log"
fi

git -C sotf status --porcelain -- Cargo.lock >"$output/sotf-lock-status.txt"
if [ -s "$output/sotf-lock-status.txt" ]; then
    printf 'SOTF Cargo.lock changed during UI QA\n' | tee -a "$output/sotf-lock-status.txt"
    failed=1
fi
git -C gpui-toolkit status --porcelain -- Cargo.lock >"$output/toolkit-lock-status.txt"
if [ -s "$output/toolkit-lock-status.txt" ]; then
    printf 'GPUI toolkit Cargo.lock changed during UI QA\n' | tee -a "$output/toolkit-lock-status.txt"
    failed=1
fi

exit "$failed"
