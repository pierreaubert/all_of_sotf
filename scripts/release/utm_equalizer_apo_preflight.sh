#!/usr/bin/env bash
# Probe the configured Equalizer APO VM without changing its installed software.
set -euo pipefail

if [[ $(uname -s) != Darwin ]]; then
    echo 'Equalizer APO UTM preflight requires macOS' >&2
    exit 1
fi

root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root"
output="$root/release-utm-apo-preflight-evidence-macos"
mkdir -p "$output"
cp scripts/release/sources.json "$output/sources.json"
git rev-parse HEAD >"$output/root-revision.txt"

vm=${ROOMEQ_EQUALIZER_APO_UTM_VM:-Win11 ARM AutoEQ}
benchmark=${ROOMEQ_EQUALIZER_APO_BENCHMARK:-C:\\Program Files\\EqualizerAPO\\Benchmark.exe}
if [[ $benchmark == *"'"* || $benchmark == *$'\n'* ]]; then
    echo 'Benchmark path cannot contain an apostrophe or newline' >&2
    exit 2
fi
if [[ -n ${ROOMEQ_EQUALIZER_APO_UTMCTL:-} ]]; then
    utmctl=$ROOMEQ_EQUALIZER_APO_UTMCTL
elif command -v utmctl >/dev/null 2>&1; then
    utmctl=$(command -v utmctl)
else
    utmctl=/Applications/UTM.app/Contents/MacOS/utmctl
fi
if [[ ! -x $utmctl ]]; then
    echo "utmctl is unavailable: $utmctl" >&2
    exit 1
fi

# subprocess.run kills and reaps a command that exceeds its deadline. Passing
# fixture bytes through stdin also avoids shell interpolation into utmctl.
bounded() {
    local seconds=$1
    shift
    python3 -c '
import subprocess, sys
seconds = int(sys.argv[1])
command = sys.argv[2:]
try:
    result = subprocess.run(command, input=sys.stdin.buffer.read(),
                            capture_output=True, timeout=seconds)
except subprocess.TimeoutExpired:
    raise SystemExit(f"timed out after {seconds}s: {command[0]}")
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
raise SystemExit(result.returncode)
' "$seconds" "$@"
}

job_id="roomeq-apo-qa-preflight-$(date +%s)-$$"
guest_dir="C:\\Windows\\Temp\\$job_id"
guest_file="$guest_dir\\sentinel.txt"
sentinel=$(mktemp /private/tmp/sotf-apo-sentinel.XXXXXXXX)
returned=$(mktemp /private/tmp/sotf-apo-returned.XXXXXXXX)
started_vm=0
start_attempted=0
guest_dir_created=0
cleanup() {
    local status=$?
    trap - EXIT INT TERM
    set +e
    if [[ $guest_dir_created == 1 ]]; then
        if ! bounded 20 "$utmctl" exec --hide "$vm" --cmd powershell.exe \
            -NoProfile -NonInteractive -Command \
            "if (Test-Path -LiteralPath '$guest_dir') { Remove-Item -LiteralPath '$guest_dir' -Recurse -Force -ErrorAction Stop }" \
            </dev/null >"$output/cleanup-guest.log" 2>&1; then
            echo 'Could not remove the private guest sentinel directory' >&2
            status=1
        fi
    fi
    if [[ ${initial_vm_status:-} == stopped && $start_attempted == 1 && $started_vm == 0 ]]; then
        observed_status=$(bounded 15 "$utmctl" status "$vm" </dev/null 2>&1)
        if [[ $observed_status == started ]]; then started_vm=1; fi
    fi
    if [[ $started_vm == 1 ]]; then
        if ! bounded 30 "$utmctl" stop --hide "$vm" </dev/null \
            >"$output/cleanup-vm.log" 2>&1; then
            echo 'Could not stop the VM started by this preflight' >&2
            status=1
        fi
    fi
    final_vm_status=$(bounded 15 "$utmctl" status "$vm" </dev/null 2>&1)
    printf 'final_vm_status=%s\n' "$final_vm_status" >>"$output/status.txt"
    if [[ $started_vm == 1 && $final_vm_status != stopped ]] ||
        [[ $started_vm == 0 && $final_vm_status != "${initial_vm_status:-}" ]]; then
        echo 'Configured VM did not retain its expected post-preflight state' >&2
        status=1
    fi
    rm -f "$sentinel" "$returned"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'vm=%s\nbenchmark=%s\n' "$vm" "$benchmark" >"$output/config.txt"
status=$(bounded 15 "$utmctl" status "$vm" </dev/null) || {
    echo "Configured UTM VM is unavailable: $vm" >&2
    exit 1
}
initial_vm_status=$status
printf 'initial_vm_status=%s\n' "$status" | tee "$output/status.txt"
case "$status" in
    started) ;;
    stopped)
        start_attempted=1
        if bounded 30 "$utmctl" start --hide "$vm" </dev/null \
            >"$output/start.log" 2>&1; then
            observed_status=$(bounded 15 "$utmctl" status "$vm" </dev/null)
            if [[ $observed_status != started ]]; then
                echo "UTM start returned success but VM state is $observed_status" >&2
                exit 1
            fi
            started_vm=1
        else
            observed_status=$(bounded 15 "$utmctl" status "$vm" </dev/null 2>&1) || observed_status=unknown
            if [[ $observed_status == started ]]; then started_vm=1; fi
            echo "UTM start did not complete; observed VM state: $observed_status" >&2
            exit 1
        fi
        ;;
    *) echo "Unsupported UTM VM state (left unchanged): $status" >&2; exit 1 ;;
esac

deadline=$((SECONDS + 120))
guest_ready=0
while (( SECONDS < deadline )); do
    probe=$(bounded 15 "$utmctl" exec --hide "$vm" --cmd \
        cmd.exe /d /c echo ROOMEQ_UTM_READY </dev/null 2>&1) || probe=
    if [[ $probe == *ROOMEQ_UTM_READY* ]]; then
        guest_ready=1
        break
    fi
    sleep 2
done
if [[ $guest_ready != 1 ]]; then
    echo 'UTM guest agent did not execute the bounded readiness probe' >&2
    exit 1
fi
echo 'guest_agent=ready' | tee -a "$output/status.txt"

benchmark_probe=$(bounded 20 "$utmctl" exec --hide "$vm" --cmd powershell.exe \
    -NoProfile -NonInteractive -Command \
    "if (Test-Path -LiteralPath '$benchmark' -PathType Leaf) { Write-Output 'ROOMEQ_APO_BENCHMARK_PRESENT' } else { exit 4 }" \
    </dev/null) || {
    echo "Equalizer APO Benchmark.exe is unavailable in $vm at $benchmark" >&2
    exit 1
}
if [[ $benchmark_probe != *ROOMEQ_APO_BENCHMARK_PRESENT* ]]; then
    echo 'Guest benchmark probe returned no success marker' >&2
    exit 1
fi
echo 'benchmark=present' | tee -a "$output/status.txt"

guest_dir_created=1
bounded 20 "$utmctl" exec --hide "$vm" --cmd powershell.exe \
    -NoProfile -NonInteractive -Command \
    "New-Item -ItemType Directory -Path '$guest_dir' -ErrorAction Stop | Out-Null" \
    </dev/null >"$output/create-guest-dir.log" 2>&1
printf 'SOTF_APO_PREFLIGHT_%s\n' "$job_id" >"$sentinel"
bounded 20 "$utmctl" file push "$vm" "$guest_file" <"$sentinel" \
    >"$output/push.log" 2>&1
bounded 20 "$utmctl" file pull "$vm" "$guest_file" </dev/null >"$returned"
if ! cmp -s "$sentinel" "$returned"; then
    echo 'UTM guest file push/pull changed the private sentinel bytes' >&2
    exit 1
fi
echo 'guest_file_roundtrip=pass' | tee -a "$output/status.txt"
