#!/usr/bin/env bash
set -u

output=${1:?evidence directory required}
mkdir -p "$output"
output=$(cd "$output" && pwd)
cp scripts/release/sources.json "$output/sources.json"
{
    date -u
    uname -a
    python3 --version
    rustc --version
    cargo --version
} >"$output/toolchain.txt" 2>&1
failed=0

python3 - "$output" <<'PY'
import json
from pathlib import Path
import sys

from scripts.release.qa import ROOT, source_issues, source_state, workspace_map

output = Path(sys.argv[1])
before = source_state(ROOT, list(workspace_map()), "linux" if sys.platform == "linux" else "macos")
(output / "sources-before.json").write_text(json.dumps(before, indent=2) + "\n")
issues = source_issues(before, before, require_clean=True)
for issue in issues:
    print(f"SOURCE GUARD: {issue}")
raise SystemExit(bool(issues))
PY
if [ "$?" -ne 0 ]; then exit 1; fi

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
    fi
}

require_passed_test() {
    local check=$1 test_name=$2
    local log="$output/$check.log"
    if ! grep -E "^test .*${test_name} \\.\\.\\. ok$" "$log" >/dev/null; then
        printf '[%s] required test did not run and pass: %s\n' "$check" "$test_name"
        failed=1
    fi
}

run_check math-crossover-reset math-audio cargo test -p math-iir-fir --lib --locked
require_passed_test math-crossover-reset aupreset_payload_preserves_band_values
for crossover in lr4_crossover lr8_crossover; do
    require_passed_test math-crossover-reset \
        "$crossover::reset_tests::exact_reset_replays_fresh_filters_and_preserves_storage"
    require_passed_test math-crossover-reset \
        "$crossover::reset_tests::multiband_reset_replays_fresh_filters_and_preserves_storage"
done
run_check autoeq-report-base64 autoeq cargo test -p autoeq-report-wasm --lib --locked b64_round_trip
require_passed_test autoeq-report-base64 b64_round_trip
run_check autoeq-demo-metadata autoeq cargo metadata --locked --format-version 1 --all-features \
    --manifest-path crates/autoeq-gpui-examples/Cargo.toml
python3 - "$output/autoeq-demo-metadata.log" <<'PY'
from pathlib import Path
import sys

from scripts.release.qa import demo_metadata_issues

issues = demo_metadata_issues(Path(sys.argv[1]))
for issue in issues:
    print(f"AUTOEQ DEMO TARGET GUARD: {issue}")
raise SystemExit(bool(issues))
PY
if [ "$?" -ne 0 ]; then failed=1; fi
run_check autoeq-demo-check autoeq cargo check --locked --all-targets --all-features \
    --manifest-path crates/autoeq-gpui-examples/Cargo.toml
run_check iamf-core-and-format symphonia-add-ons cargo test --locked --all-features \
    -p symphonia-iamf-core -p symphonia-format-iamf
require_passed_test iamf-core-and-format parse_obu_header_with_trimming
require_passed_test iamf-core-and-format rejects_trun_bad_version
run_check toolkit-util-tests gpui-toolkit cargo test --locked -p gpui-toolkit-util -p gpui-toolkit-gpui-util
run_check daw-band-split-tests sotf-daw cargo test -p sotf-plugin-band-split --lib --locked
run_check daw-band-split-check sotf-daw cargo check -p sotf-plugin-band-split --all-targets --locked
run_check daw-nalgebra-consumer-tests sotf-daw cargo test -p sotf-plugin-ambisonics -p sotf-plugin-beamformer --lib --locked
run_check daw-nalgebra-consumer-check sotf-daw cargo check -p sotf-plugin-ambisonics -p sotf-plugin-beamformer --all-targets --locked
run_check daw-nnnoiseless-tests sotf-daw cargo test -p nnnoiseless --locked
run_check daw-denoiser-tests sotf-daw cargo test -p plugins-denoiser --locked
run_check daw-nih-derive-tests sotf-daw cargo test -p plugins-nih --test derive_params --test derive_persist --locked
run_check daw-room-eq-graph-tests sotf-daw cargo test -p sotf-room-eq-graph --locked
run_check daw-midi-tests sotf-daw cargo test -p sotf-midi --locked
if [ "${RELEASE_PLATFORM:-}" = linux ]; then
    run_check daw-nih-standalone-check sotf-daw bash ../scripts/release/nih_standalone_check.sh "$output"
else
    run_check daw-nih-standalone-check sotf-daw cargo check -p plugins-nih --features nih_plug/standalone --locked
fi
run_check sotf-spotify-tests sotf cargo test -p sotf-service-spotify --locked
run_check sotf-player-tests sotf cargo test -p sotf-player --lib --locked
require_passed_test sotf-player-tests snapshot_hash_detects_modified_graph
require_passed_test sotf-player-tests saved_media_segment_verifies_content_identity_before_reload
run_check sotf-capture-frontend sotf cargo test -p sotf-player --test capture_frontend --locked
require_passed_test sotf-capture-frontend capture_frontend_workflow_processes_and_imports_golden_session
run_check sotf-tls-fingerprint sotf cargo test -p sotf-tls --lib --locked test_fingerprint_format
require_passed_test sotf-tls-fingerprint test_fingerprint_format
run_check daw-aae-digest sotf-daw cargo test -p sotf-plugin-aae --lib --locked
require_passed_test daw-aae-digest manifest_digest_is_stable
if [ "$(uname -s)" = Darwin ]; then
    run_check daw-hal-encryption sotf-daw cargo test -p driver-hal --lib --locked encryption::tests::
    require_passed_test daw-hal-encryption test_encrypt_decrypt_roundtrip
    require_passed_test daw-hal-encryption test_fingerprint_consistency
else
    echo 'driver-hal encryption tests are macOS-only (cfg(target_os = "macos")); macOS focused gate is required' \
        | tee "$output/daw-hal-encryption-not-applicable-linux.txt"
fi
run_check sotf-musicbrainz-loopback-tests sotf cargo test --locked -p sotf-player --lib metadata::musicbrainz::tests:: -- --ignored --nocapture
run_check sotf-eq-chart-tests sotf cargo test -p sotf-gpui --test eq_chart_tests --locked
run_check sotf-room-eq-config-integration sotf cargo test -p sotf-gpui --test room_eq_config_tests --locked
require_passed_test sotf-room-eq-config-integration test_channel_ordering_2_0
run_check sotf-room-eq-plot-integration sotf cargo test -p sotf-gpui --test room_eq_plot_tests --locked
require_passed_test sotf-room-eq-plot-integration room_eq_report_uses_dsp_output_curves_without_recomputing

python3 - "$output" <<'PY'
import json
from pathlib import Path
import sys

from scripts.release.qa import ROOT, source_issues, source_state, workspace_map

output = Path(sys.argv[1])
before = json.loads((output / "sources-before.json").read_text())
after = source_state(ROOT, list(workspace_map()), "linux" if sys.platform == "linux" else "macos")
(output / "sources-after.json").write_text(json.dumps(after, indent=2) + "\n")
issues = source_issues(before, after, require_clean=True)
(output / "source-issues.json").write_text(json.dumps(issues, indent=2) + "\n")
for issue in issues:
    print(f"SOURCE GUARD: {issue}")
raise SystemExit(bool(issues))
PY
if [ "$?" -ne 0 ]; then failed=1; fi

exit "$failed"
