#!/usr/bin/env bash
set -u

output=${1:?evidence directory required}
mkdir -p "$output" || exit 1
cp scripts/release/sources.json "$output/sources.json" || exit 1
for tool in rustc cargo swift just; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "$tool is required for the isolated systemwide lab" | tee "$output/prerequisite-error.log" >&2
        exit 1
    fi
done
{
    date -u
    uname -a
    rustc --version
    cargo --version
    swift --version
    just --version
} >"$output/toolchain.txt" 2>&1

before=$(git -C sotf-systemwide hash-object Cargo.lock) || exit 1
revision_before=$(git -C sotf-systemwide rev-parse HEAD) || exit 1
(cd sotf-systemwide && just systemwide-lab) >"$output/systemwide-lab.log" 2>&1
status=$?
after=$(git -C sotf-systemwide hash-object Cargo.lock) || exit 1
revision_after=$(git -C sotf-systemwide rev-parse HEAD) || exit 1
printf 'lock_before=%s\nlock_after=%s\nrevision_before=%s\nrevision_after=%s\nexit_code=%s\n' "$before" "$after" "$revision_before" "$revision_after" "$status" >"$output/report.txt"
printf '[systemwide-lab] exit %s; log: %s\n' "$status" "$output/systemwide-lab.log"
if [ "$status" -ne 0 ]; then
    tail -n 80 "$output/systemwide-lab.log"
fi
if [ "$before" != "$after" ]; then
    echo 'systemwide-lab changed Cargo.lock' >&2
    exit 1
fi
if [ "$revision_before" != "$revision_after" ]; then
    echo 'systemwide-lab changed the checked-out source revision' >&2
    exit 1
fi
exit "$status"
