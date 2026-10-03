#!/usr/bin/env bash
set -u

output=${1:?evidence directory required}
mkdir -p "$output"
cp scripts/release/sources.json "$output/sources.json"
{
    date -u
    uname -a
    python3 --version
    rustc --version
    cargo --version
} >"$output/toolchain.txt" 2>&1
failed=0

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

run_check math-crossover-reset math-audio cargo test -p math-iir-fir --lib --locked
run_check daw-band-split-tests sotf-daw cargo test -p sotf-plugin-band-split --lib --locked
run_check daw-band-split-check sotf-daw cargo check -p sotf-plugin-band-split --all-targets --locked
run_check daw-nalgebra-consumer-tests sotf-daw cargo test -p sotf-plugin-ambisonics -p sotf-plugin-beamformer --lib --locked
run_check daw-nalgebra-consumer-check sotf-daw cargo check -p sotf-plugin-ambisonics -p sotf-plugin-beamformer --all-targets --locked

exit "$failed"
