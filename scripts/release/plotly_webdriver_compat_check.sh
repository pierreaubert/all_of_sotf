#!/usr/bin/env bash
set -Eeuo pipefail
[ "${CI:-}" = true ] && [ "${DISPOSABLE:-}" = 1 ] || {
    echo 'Plotly compatibility qualification runs only in disposable CI' >&2
    exit 2
}

platform=${1:?macos or linux required}
output=${2:?evidence directory required}
fantoccini_rev=${3:?immutable Fantoccini commit required}
plotly_rev=${4:?immutable Plotly commit required}
downloader_rev=${5:?immutable downloader commit required}
case "$platform" in macos|linux) ;; *) echo "unsupported platform: $platform" >&2; exit 2 ;; esac
for rev in "$fantoccini_rev" "$plotly_rev" "$downloader_rev"; do
    [[ "$rev" =~ ^[0-9a-f]{40}$ ]] || { echo "fork revision must be a full SHA: $rev" >&2; exit 2; }
done
readonly reviewed_fantoccini_rev=bdf1972dd04e8abf5741c177f3b35a261a700ceb
readonly reviewed_plotly_rev=67230e5d154d2bb6110a0242db074b59cf2fdc89
readonly reviewed_downloader_rev=34b86a7fa685efb9888ab216d1fcd6b9febe24e1
[ "$fantoccini_rev" = "$reviewed_fantoccini_rev" ] &&
    [ "$plotly_rev" = "$reviewed_plotly_rev" ] &&
    [ "$downloader_rev" = "$reviewed_downloader_rev" ] || {
    echo 'fork revisions differ from the three reviewed immutable compatibility commits' >&2
    exit 2
}

readonly fantoccini_base=ed1d6944e100cf36f8a00c03c7a9a5f4424e71f3
readonly plotly_base=fd36405d3b0415c9cebea56111c56c0e3b18fe87
readonly downloader_base=472b2bcc2695cfcd0d5d508fd065c915fb1c7272
readonly fantoccini_url=https://github.com/pierreaubert/fantoccini.git
readonly plotly_url=https://github.com/pierreaubert/plotly.rs.git
readonly downloader_url=https://github.com/pierreaubert/webdriver-downloader.git
readonly fantoccini_branch=ci/plotly-http1-20261004
readonly plotly_branch=ci/plotly-static-reqwest13-20261004
readonly downloader_branch=ci/plotly-reqwest13-20261004
readonly linux_browser_sha=ff43322f335e436b2f4dcdfeeec5db032299e335a7e8c1c618b326e100ce8732
readonly linux_browser_bytes=196202491
readonly mac_browser_sha=b62e904b6571c5ff5108ed7812cf93ac6d1c4027f10ae47ac34d8e229ed88001
readonly mac_browser_bytes=191153086

archive_hash() {
    local directory=$1
    python3 - "$directory" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

root = Path(sys.argv[1])
digest = sha256()
for path in sorted(root.rglob("*")):
    if not path.is_file() or path.name == "Cargo.lock" or "target" in path.relative_to(root).parts:
        continue
    relative = path.relative_to(root).as_posix().encode()
    data = path.read_bytes()
    digest.update(len(relative).to_bytes(8, "big"))
    digest.update(relative)
    digest.update(len(data).to_bytes(8, "big"))
    digest.update(data)
print(digest.hexdigest())
PY
}

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

source_state() {
    python3 - "$output" "$platform" "$1" <<'PY'
import json
from pathlib import Path
import sys

from scripts.release.qa import ROOT, source_issues, source_state, workspace_map

output, platform, phase = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
state = source_state(ROOT, list(workspace_map()), platform)
(output / f"sources-{phase}.json").write_text(json.dumps(state, indent=2) + "\n")
before = json.loads((output / "sources-before.json").read_text()) if phase == "after" else state
issues = source_issues(before, state, require_clean=True)
manifest = json.loads((ROOT / "scripts/release/sources.json").read_text())["sources"]
for name, pinned in manifest.items():
    if state.get(name, {}).get("revision") != pinned["revision"]:
        issues.append(f"{name}: checkout differs from pinned sources.json revision")
(output / f"source-issues-{phase}.json").write_text(json.dumps(issues, indent=2) + "\n")
for issue in issues:
    print(f"SOURCE GUARD: {issue}", file=sys.stderr)
raise SystemExit(bool(issues))
PY
}

root_state() {
    python3 - "$output" "$1" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

output, phase = Path(sys.argv[1]), sys.argv[2]
root = Path.cwd()
pins = json.loads((root / "scripts/release/sources.json").read_text())["sources"]
revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).splitlines()
allowed = {f"?? {name}/" for name in pins}
issues = [line for line in status if line not in allowed]
state = {"revision": revision, "status": status, "issues": issues}
(output / f"root-{phase}.json").write_text(json.dumps(state, indent=2) + "\n")
if phase == "after":
    before = json.loads((output / "root-before.json").read_text())
    if revision != before["revision"] or status != before["status"]:
        issues.append("root revision or status changed during qualification")
if issues:
    print("root source guard failed: " + repr(issues), file=sys.stderr)
raise SystemExit(bool(issues))
PY
}

root_state before
source_state before
work=$(mktemp -d "${TMPDIR:-/tmp}/webdriver-candidate.XXXXXX")
fantoccini="$work/fantoccini"
plotly="$work/plotly"
downloader="$work/downloader"
clones=("$fantoccini" "$plotly" "$downloader")
active_supervisor=
stop_requested=0
finish() {
    status=$?
    trap - EXIT
    if [ -n "$active_supervisor" ]; then
        kill -TERM "$active_supervisor" 2>/dev/null || true
        for _ in {1..450}; do
            kill -0 "$active_supervisor" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL "$active_supervisor" 2>/dev/null || true
        wait "$active_supervisor" 2>/dev/null || true
        if kill -0 "$active_supervisor" 2>/dev/null; then
            echo 'owned command supervisor did not terminate' >&2
            status=1
        fi
    fi
    if [ -d "$work/plotly-smoke" ]; then
        if [ -f "$work/plotly-smoke/plot.png" ]; then
            cp "$work/plotly-smoke/plot.png" "$output/plot-at-exit.png" || status=1
        fi
        python3 - "$work/plotly-smoke/plot.png" "$work/private-home/bin/chromedriver" \
            "$output/smoke-progress.json" <<'PY' || status=1
import json
from pathlib import Path
import sys

image, driver, report = map(Path, sys.argv[1:])
report.write_text(json.dumps({
    "png_exists": image.is_file(),
    "png_bytes": image.stat().st_size if image.is_file() else None,
    "private_chromedriver_exists": driver.is_file(),
    "private_chromedriver_bytes": driver.stat().st_size if driver.is_file() else None,
}, indent=2) + "\n")
PY
    fi
    python3 - "$output" "$status" <<'PY' || status=1
import json
from pathlib import Path
import sys

output, exit_code = Path(sys.argv[1]), int(sys.argv[2])
commands = {}
for path in sorted(output.glob("*.status.json")):
    commands[path.name] = json.loads(path.read_text())
(output / "supervisor-report.json").write_text(json.dumps({
    "script_exit_before_reporting": exit_code,
    "commands": commands,
}, indent=2) + "\n")
PY
    for pair in "$fantoccini:$fantoccini_rev" "$plotly:$plotly_rev" "$downloader:$downloader_rev"; do
        path=${pair%:*}
        expected=${pair#*:}
        if [ -d "$path/.git" ] && {
            [ "$(git -C "$path" rev-parse HEAD)" != "$expected" ] ||
            [ -n "$(git -C "$path" status --porcelain)" ];
        }; then
            echo "fork revision or clean-state guard failed: $path" >&2
            status=1
        fi
    done
    for name in fantoccini plotly downloader; do
        if [ -f "$output/$name-Cargo.lock" ]; then
            cmp -s "$output/$name-Cargo.lock" "$work/$name-source/Cargo.lock" || {
                echo "$name generated fork lock changed during --locked qualification" >&2
                status=1
            }
        fi
        if [ -f "$output/$name-source-sha256.txt" ]; then
            actual_source_hash=$(archive_hash "$work/$name-source") || status=1
            [ "$actual_source_hash" = "$(cat "$output/$name-source-sha256.txt")" ] || {
                echo "$name archived source changed during compilation" >&2
                status=1
            }
        fi
    done
    if [ -f "$output/plotly-smoke-Cargo.lock" ]; then
        cmp -s "$output/plotly-smoke-Cargo.lock" "$work/plotly-smoke/Cargo.lock" || {
            echo 'Plotly PNG smoke lock changed during qualification' >&2
            status=1
        }
    fi
    source_state after || status=1
    root_state after || status=1
    rm -rf -- "$work" || status=1
    exit "$status"
}
trap finish EXIT
trap 'stop_requested=1; exit 130' INT
trap 'stop_requested=1; exit 143' TERM

cat >"$work/supervise.py" <<'PY'
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from scripts.release.librespot_candidate_check import clean_group, enable_subreaper

log_path, workdir, *command = sys.argv[1:]
status_path = Path(log_path).with_suffix(".status.json")
started = time.monotonic()
stop = False
status = {"child_exit_code": None, "cleanup_ok": None, "heartbeats": 0,
          "interrupted": False, "owned_pgid": None}

def interrupted(_signum, _frame):
    global stop
    stop = True

signal.signal(signal.SIGINT, interrupted)
signal.signal(signal.SIGTERM, interrupted)
enable_subreaper()
ready = os.environ.get("PLOTLY_SUPERVISOR_PRELAUNCH_READY")
if ready:
    # CI regression hook: hold before child launch so a real SIGTERM can prove
    # that no command starts after interruption.
    Path(ready).write_text("ready\n")
    until = time.monotonic() + 10
    while not stop and time.monotonic() < until:
        time.sleep(0.01)
    if not stop:
        raise RuntimeError("prelaunch signal regression did not interrupt supervisor")
if stop:
    status["interrupted"] = True
    status["prelaunch_stop"] = True
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    sys.exit(130)
with Path(log_path).open("wb") as log:
    if stop:
        status["interrupted"] = True
        status["prelaunch_stop"] = True
        status_path.write_text(json.dumps(status, indent=2) + "\n")
        sys.exit(130)
    child = subprocess.Popen(
        command, cwd=workdir, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )
    code = 130
    try:
        status["owned_pgid"] = child.pid
        status_path.write_text(json.dumps(status, indent=2) + "\n")
        while not stop:
            try:
                code = child.wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - started
                if elapsed >= (status["heartbeats"] + 1) * 30:
                    status["heartbeats"] += 1
                    status["elapsed_seconds"] = round(elapsed, 3)
                    status_path.write_text(json.dumps(status, indent=2) + "\n")
                    print(f"owned command heartbeat: {command[0]}", flush=True)
    finally:
        cleanup = clean_group(child)
        status["cleanup"] = cleanup
        status["cleanup_ok"] = cleanup["ok"]
        status["child_exit_code"] = child.poll()
        status["interrupted"] = stop
        status["elapsed_seconds"] = round(time.monotonic() - started, 3)
        status_path.write_text(json.dumps(status, indent=2) + "\n")
    if not cleanup["ok"]:
        log.write(b"owned process group cleanup failed\n")
        code = 1
    elif stop:
        code = 130
    sys.exit(code if code >= 0 else 128 - code)
PY

run_owned() {
    local log=$1
    local cwd=$2
    shift 2
    [ "$stop_requested" -eq 0 ] || { echo 'stop requested; no new command launched' >&2; return 130; }
    PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" python3 "$work/supervise.py" "$log" "$cwd" "$@" &
    active_supervisor=$!
    local status=0
    wait "$active_supervisor" || status=$?
    active_supervisor=
    if [ "$status" -ne 0 ]; then
        echo "owned command failed ($status); full log: $log" >&2
        tail -n 80 "$log" >&2
    fi
    return "$status"
}

cat >"$work/prelaunch_regression.py" <<'PY'
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

supervisor, private = Path(sys.argv[1]), Path(sys.argv[2])
ready = private / "prelaunch-ready"
marker = private / "unexpected-child-launch"
log = private / "prelaunch-child.log"
environment = os.environ.copy()
environment["PLOTLY_SUPERVISOR_PRELAUNCH_READY"] = str(ready)
process = subprocess.Popen(
    [sys.executable, str(supervisor), str(log), str(private),
     sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('launched')"],
    env=environment,
)
deadline = time.monotonic() + 5
while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
    time.sleep(0.01)
assert ready.exists(), "supervisor did not reach prelaunch signal point"
process.send_signal(signal.SIGTERM)
assert process.wait(timeout=10) == 130, "prelaunch SIGTERM did not stop supervisor"
assert not marker.exists(), "command launched after SIGTERM"
report = json.loads(log.with_suffix(".status.json").read_text())
assert report["prelaunch_stop"] and report["owned_pgid"] is None
print("supervisor_prelaunch_signal_prevents_child_launch: PASS")
PY
run_owned "$output/supervisor-prelaunch-regression.log" "$PWD" \
    python3 "$work/prelaunch_regression.py" "$work/supervise.py" "$work"
grep -Fx 'supervisor_prelaunch_signal_prevents_child_launch: PASS' \
    "$output/supervisor-prelaunch-regression.log" >/dev/null || {
    echo 'supervisor prelaunch signal regression was not observed' >&2
    exit 1
}

clone_guard() {
    local name=$1 url=$2 branch=$3 rev=$4 base=$5 repo=$6
    run_owned "$output/$name-clone.log" "$PWD" git clone --branch "$branch" --single-branch "$url" "$repo"
    [ "$(git -C "$repo" rev-parse HEAD)" = "$rev" ] || {
        echo "$name revision differs" >&2; exit 1;
    }
    [ "$(git -C "$repo" rev-parse HEAD^)" = "$base" ] || {
        echo "$name is not a direct child of reviewed official/qualified base" >&2; exit 1;
    }
    if [ "$name" = fantoccini ]; then
        [ "$(git -C "$repo" rev-parse HEAD^^)" = e12d66dc87df7dd010d913a7e7de9ff0afdd770b ] &&
        [ "$(git -C "$repo" rev-parse HEAD^^^)" = ed1d6944e100cf36f8a00c03c7a9a5f4424e71f3 ] || {
            echo 'Fantoccini reviewed ancestry differs' >&2; exit 1;
        }
    fi
    git -C "$repo" status --porcelain >"$output/$name-status.txt"
    [ ! -s "$output/$name-status.txt" ] || { echo "$name checkout is dirty" >&2; exit 1; }
    case "$name" in
        fantoccini) expected=$'Cargo.toml\nexamples/basic.rs\nexamples/wait.rs\nsrc/wd.rs' ;;
        plotly) expected=plotly_static/Cargo.toml ;;
        downloader) expected=webdriver-downloader/Cargo.toml ;;
    esac
    local provenance_base=$base
    if [ "$name" = fantoccini ]; then
        provenance_base=ed1d6944e100cf36f8a00c03c7a9a5f4424e71f3
    fi
    changed=$(git -C "$repo" diff --name-only "$provenance_base" "$rev")
    [ "$changed" = "$expected" ] || {
        echo "$name changed paths differ from the reviewed fork patch: $changed" >&2
        exit 1
    }
    git -C "$repo" diff --binary "$provenance_base" "$rev" >"$output/$name.patch"
    case "$name" in
        fantoccini) reviewed_sha=7d997c0841880b2cfa0e4c25fd9e6b98034ba4687b6d622f20e1050ca53568ec ;;
        plotly) reviewed_sha=11786074b33724e836a554358379bf50d55cc10e20eb9460ed9f72d78ba5c079 ;;
        downloader) reviewed_sha=87cf1cda21e811e20ad086c65c48aa91b1a0f467005c87ee031bb722da4d916e ;;
    esac
    actual_sha=$(python3 - "$output/$name.patch" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

print(sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
    [ "$actual_sha" = "$reviewed_sha" ] || {
        echo "$name full fork patch hash differs: $actual_sha" >&2
        exit 1
    }
    printf '%s\n' "$rev" >"$output/$name-revision.txt"
}
clone_guard fantoccini "$fantoccini_url" "$fantoccini_branch" "$fantoccini_rev" 590017cc99258f69c7c0081de19e9488c200565f "$fantoccini"
clone_guard plotly "$plotly_url" "$plotly_branch" "$plotly_rev" "$plotly_base" "$plotly"
clone_guard downloader "$downloader_url" "$downloader_branch" "$downloader_rev" "$downloader_base" "$downloader"

python3 - "$fantoccini/Cargo.toml" "$plotly/plotly_static/Cargo.toml" \
    "$downloader/webdriver-downloader/Cargo.toml" <<'PY'
from pathlib import Path
import sys
import tomllib

fantoccini, plotly, downloader = (tomllib.loads(Path(path).read_text()) for path in sys.argv[1:])
assert fantoccini["dependencies"]["webdriver"] == {
    "version": "0.54", "default-features": False,
}
assert fantoccini["features"]["default"] == ["native-tls"]
assert fantoccini["features"]["rustls-tls"] == ["hyper-rustls"]
reqwest = plotly["dependencies"]["reqwest"]
assert reqwest == {"version": "0.13", "default-features": False,
                   "features": ["blocking", "native-tls", "charset", "http2", "system-proxy"]}
assert downloader["dependencies"]["reqwest"] == {
    "version": "0.13", "default-features": False,
}
assert downloader["features"]["default"] == ["native-tls"]
assert downloader["features"]["native-tls"] == ["fantoccini/native-tls", "reqwest/native-tls"]
assert downloader["features"]["rustls-tls"] == ["fantoccini/rustls-tls", "reqwest/rustls"]
print("All three reviewed dependency and TLS-feature declarations are intact")
PY

archive_fork() {
    local name=$1 repo=$2 rev=$3
    local target="$work/$name-source"
    mkdir -p "$target"
    run_owned "$output/$name-archive.log" "$repo" git archive "$rev" -o "$work/$name.tar"
    run_owned "$output/$name-extract.log" "$target" tar -xf "$work/$name.tar"
    if [ "$name" = downloader ]; then
        cat >>"$target/Cargo.toml" <<EOF

[patch.crates-io]
fantoccini = { path = "$work/fantoccini-source" }
EOF
    elif [ "$name" = plotly ]; then
        cat >>"$target/Cargo.toml" <<EOF

[patch.crates-io]
fantoccini = { path = "$work/fantoccini-source" }
webdriver-downloader = { path = "$work/downloader-source/webdriver-downloader" }
EOF
    fi
    archive_hash "$target" >"$output/$name-source-sha256.txt"
    run_owned "$output/$name-resolve.log" "$target" cargo generate-lockfile
    cp "$target/Cargo.lock" "$output/$name-Cargo.lock"
}
archive_fork fantoccini "$fantoccini" "$fantoccini_rev"
archive_fork downloader "$downloader" "$downloader_rev"
archive_fork plotly "$plotly" "$plotly_rev"

run_check() {
    local name=$1 cwd=$2
    shift 2
    echo "[$name] $*"
    run_owned "$output/$name.log" "$cwd" "$@"
}
run_check fantoccini-native-check "$work/fantoccini-source" cargo check --locked --all-targets --no-default-features --features native-tls
run_check fantoccini-rustls-check "$work/fantoccini-source" cargo check --locked --all-targets --no-default-features --features rustls-tls
run_check fantoccini-combined-check "$work/fantoccini-source" cargo check --locked --all-targets --no-default-features --features native-tls,rustls-tls
run_check fantoccini-no-default-check "$work/fantoccini-source" cargo check --locked --all-targets --no-default-features
run_check fantoccini-native-timeout-tests "$work/fantoccini-source" cargo test --locked --lib wd::timeout_parameter_tests --no-default-features --features native-tls
run_check fantoccini-rustls-timeout-tests "$work/fantoccini-source" cargo test --locked --lib wd::timeout_parameter_tests --no-default-features --features rustls-tls
python3 - "$output/fantoccini-native-timeout-tests.log" "$output/fantoccini-rustls-timeout-tests.log" <<'PY'
import re
import sys
from pathlib import Path

names = {
    "explicit_script_null_remains_distinct_from_omission",
    "omitted_timeouts_remain_omitted",
    "zero_and_positive_timeouts_keep_their_values",
}
for path in map(Path, sys.argv[1:]):
    output = path.read_text(errors="replace")
    passed = set(re.findall(r"^test wd::timeout_parameter_tests::(\w+) \.\.\. ok$", output, re.M))
    assert passed == names, f"{path}: timeout tests differ: {passed}"
    assert re.search(r"test result: ok\. 3 passed; 0 failed; 0 ignored;", output), path
PY
run_check plotly-chromedriver-check "$work/plotly-source" cargo check --locked -p plotly_static --all-targets --features chromedriver
run_check plotly-geckodriver-check "$work/plotly-source" cargo check --locked -p plotly_static --all-targets --features geckodriver
run_check downloader-native-tests "$work/downloader-source" cargo test --locked -p webdriver-downloader --lib traits:: --no-default-features --features native-tls
run_check downloader-native-check "$work/downloader-source" cargo check --locked -p webdriver-downloader --all-targets --no-default-features --features native-tls
run_check downloader-rustls-tests "$work/downloader-source" cargo test --locked -p webdriver-downloader --lib traits:: --no-default-features --features rustls-tls
run_check downloader-rustls-check "$work/downloader-source" cargo check --locked -p webdriver-downloader --all-targets --no-default-features --features rustls-tls
for name in test_extract_zip_finds_nested_driver test_extract_zip_rejects_missing_driver test_extract_tarball_success test_extract_tarball_executable_not_found; do
    grep -E "^test .*${name} \.\.\. ok$" "$output/downloader-native-tests.log" >/dev/null || {
        echo "required native-TLS downloader test did not pass: $name" >&2; exit 1;
    }
done
for name in test_extract_zip_finds_nested_driver test_extract_zip_rejects_missing_driver; do
    grep -E "^test .*${name} \.\.\. ok$" "$output/downloader-rustls-tests.log" >/dev/null || {
        echo "required Rustls downloader test did not pass: $name" >&2; exit 1;
    }
done

tls="$work/private-tls"
mkdir -p "$tls"
cat >"$tls/ca.cnf" <<'EOF'
[req]
prompt = no
distinguished_name = subject
x509_extensions = ca_extensions
[subject]
CN = Plotly QA private root
[ca_extensions]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
EOF
cat >"$tls/server.cnf" <<'EOF'
[req]
prompt = no
distinguished_name = subject
req_extensions = server_extensions
[subject]
CN = localhost
[server_extensions]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:localhost
EOF
umask 077
run_owned "$output/private-ca.log" "$tls" openssl req -x509 -newkey rsa:2048 \
    -nodes -days 1 -keyout "$tls/ca.key" -out "$tls/ca.crt" -config "$tls/ca.cnf"
run_owned "$output/private-server-csr.log" "$tls" openssl req -new -newkey rsa:2048 \
    -nodes -keyout "$tls/server.key" -out "$tls/server.csr" -config "$tls/server.cnf"
run_owned "$output/private-server-sign.log" "$tls" openssl x509 -req \
    -in "$tls/server.csr" -CA "$tls/ca.crt" -CAkey "$tls/ca.key" \
    -CAcreateserial -days 1 -out "$tls/server.crt" \
    -extfile "$tls/server.cnf" -extensions server_extensions
run_owned "$output/private-server-verify.log" "$tls" openssl verify \
    -CAfile "$tls/ca.crt" "$tls/server.crt"
grep -F 'server.crt: OK' "$output/private-server-verify.log" >/dev/null || {
    echo 'private CA did not verify its localhost server certificate' >&2; exit 1;
}

protocol="$work/protocol"
mkdir -p "$protocol/src"
cp scripts/release/plotly_webdriver_protocol.rs "$protocol/src/lib.rs"
cat >"$protocol/Cargo.toml" <<EOF
[package]
name = "plotly-webdriver-protocol-qa"
version = "0.0.0"
edition = "2021"

[features]
native-tls = ["fantoccini/native-tls"]
rustls-tls = ["fantoccini/rustls-tls"]

[dependencies]
fantoccini = { path = "$work/fantoccini-source", default-features = false }
reqwest = { version = "0.13", default-features = false, features = ["blocking", "native-tls", "rustls"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
EOF
run_owned "$output/protocol-resolve.log" "$protocol" cargo generate-lockfile
cp "$protocol/Cargo.lock" "$output/protocol-Cargo.lock"
protocol_env=(env PLOTLY_TLS_SERVER="$PWD/scripts/release/plotly_tls_server.py"
    PLOTLY_TLS_CERT="$tls/server.crt" PLOTLY_TLS_KEY="$tls/server.key"
    PLOTLY_TLS_CA="$tls/ca.crt")
for mode in native-tls rustls-tls; do
    run_check "protocol-$mode" "$protocol" "${protocol_env[@]}" cargo test --locked \
        --lib --no-default-features --features "$mode" -- --nocapture --test-threads=1
done
run_check protocol-both "$protocol" "${protocol_env[@]}" cargo test --locked \
    --lib --no-default-features --features native-tls,rustls-tls -- --nocapture --test-threads=1
python3 - "$output" <<'PY'
from pathlib import Path
import re
import sys

output = Path(sys.argv[1])
expected = {
    "protocol-native-tls.log": {"webdriver_protocol_native", "private_ca_tls_native"},
    "protocol-rustls-tls.log": {"webdriver_protocol_rustls", "private_ca_tls_rustls"},
    "protocol-both.log": {"webdriver_protocol_native", "webdriver_protocol_rustls",
                          "private_ca_tls_native", "private_ca_tls_rustls"},
}
for name, tests in expected.items():
    text = (output / name).read_text()
    passed = set(re.findall(r"^test (\S+) \.\.\. ok$", text, re.MULTILINE))
    assert passed == tests, (name, passed, tests)
    assert re.search(rf"test result: ok\. {len(tests)} passed; 0 failed; 0 ignored;", text), name
print("Positive WebDriver protocol and private TLS inventories passed in all three feature modes")
PY
cmp -s "$output/protocol-Cargo.lock" "$protocol/Cargo.lock" || {
    echo 'protocol fixture lock changed under --locked tests' >&2; exit 1;
}

if [ "$platform" = linux ] || [ "$platform" = macos ]; then
    if [ "$platform" = linux ]; then
        browser_url=https://storage.googleapis.com/chrome-for-testing-public/154.0.8037.92/linux64/chrome-linux64.zip
        browser_sha=$linux_browser_sha
        browser_bytes=$linux_browser_bytes
        browser_zip=chrome-linux64.zip
        browser_binary='chrome-linux64/chrome'
    else
        [ "$(uname -m)" = arm64 ] || { echo 'macOS Chrome archive requires an ARM64 runner' >&2; exit 1; }
        browser_url=https://storage.googleapis.com/chrome-for-testing-public/154.0.8037.92/mac-arm64/chrome-mac-arm64.zip
        browser_sha=$mac_browser_sha
        browser_bytes=$mac_browser_bytes
        browser_zip=chrome-mac-arm64.zip
        browser_binary='chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'
    fi
    printf '%s\n' "$browser_url" >"$output/browser-url.txt"
    printf '%s\n' "$browser_sha" >"$output/browser-sha256.txt"
    run_owned "$output/browser-download.log" "$work" curl --fail --location --silent \
        --show-error --retry 3 --max-time 600 "$browser_url" --output "$work/$browser_zip"
    python3 - "$work/$browser_zip" "$browser_sha" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

actual = sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
assert actual == sys.argv[2], f"Chrome archive differs from reviewed SHA-256: {actual}"
PY
    actual_browser_bytes=$(python3 - "$work/$browser_zip" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).stat().st_size)
PY
)
    [ "$actual_browser_bytes" = "$browser_bytes" ] || {
        echo "Chrome for Testing archive length differs: $actual_browser_bytes" >&2
        exit 1
    }
    mkdir -p "$work/browser"
    run_owned "$output/browser-extract.log" "$work" unzip -q "$work/$browser_zip" -d "$work/browser"
    BROWSER_PATH="$work/browser/$browser_binary"
    [ -x "$BROWSER_PATH" ] || { echo 'Chrome for Testing executable is missing' >&2; exit 1; }
    private_home="$work/private-home"
    mkdir -p "$private_home/bin" "$work/tmp"
    WEBDRIVER_INSTALL_PATH="$private_home/bin"
    smoke_env=(env -u WEBDRIVER_PATH
        HOME="$private_home" TMPDIR="$work/tmp"
        CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}" RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
        XDG_CACHE_HOME="$private_home/.cache"
        XDG_CONFIG_HOME="$private_home/.config"
        XDG_DATA_HOME="$private_home/.local/share"
        BROWSER_PATH="$BROWSER_PATH"
        WEBDRIVER_INSTALL_PATH="$WEBDRIVER_INSTALL_PATH")
    run_owned "$output/browser-version.txt" "$work" "${smoke_env[@]}" "$BROWSER_PATH" --version
    grep -F '154.0.8037.92' "$output/browser-version.txt" >/dev/null || {
        echo 'Chrome for Testing executable has the wrong version' >&2
        exit 1
    }
    [ ! -e "$WEBDRIVER_INSTALL_PATH/chromedriver" ] || {
        echo 'private driver install path was not empty' >&2
        exit 1
    }
    smoke="$work/plotly-smoke"
    mkdir -p "$smoke/src"
    cat >"$smoke/Cargo.toml" <<EOF
[package]
name = "webdriver-plotly-smoke"
version = "0.0.0"
edition = "2021"

[dependencies]
anyhow = "1"
plotly_static = { path = "$work/plotly-source/plotly_static", features = ["chromedriver", "webdriver_download"] }
serde_json = "1"

[patch.crates-io]
webdriver-downloader = { path = "$work/downloader-source/webdriver-downloader" }
fantoccini = { path = "$work/fantoccini-source" }
EOF
    cat >"$smoke/src/main.rs" <<'EOF'
use plotly_static::{ImageFormat, StaticExporterBuilder};
use serde_json::json;
use std::path::Path;

fn main() -> anyhow::Result<()> {
    let plot = json!({
        "data": [{"type": "scatter", "x": [1, 2, 3], "y": [2, 4, 3]}],
        "layout": {"title": "WebDriver candidate smoke"}
    });
    let mut exporter = StaticExporterBuilder::default()
        .webdriver_browser_caps(vec![
            "--headless".to_string(),
            "--no-sandbox".to_string(),
            "--disable-dev-shm-usage".to_string(),
        ])
        .build()?;
    exporter.write_fig(Path::new("plot"), &plot, ImageFormat::PNG, 320, 240, 1.0)
        .map_err(|error| anyhow::anyhow!("{error}"))?;
    Ok(())
}
EOF
    run_owned "$output/plotly-resolve.log" "$smoke" "${smoke_env[@]}" cargo generate-lockfile
    cp "$smoke/Cargo.lock" "$output/plotly-smoke-Cargo.lock"
    python3 - "$output/plotly-smoke-Cargo.lock" <<'PY'
from pathlib import Path
import sys
import tomllib

packages = tomllib.loads(Path(sys.argv[1]).read_text())["package"]
for name, version in (("plotly_static", "0.1.0"), ("fantoccini", "0.22.1"),
                      ("webdriver-downloader", "0.16.4")):
    selected = [p for p in packages if p["name"] == name]
    assert len(selected) == 1 and selected[0]["version"] == version, (name, selected)
    assert "source" not in selected[0], f"{name} did not select the immutable archive patch"
for name, prefix in (("reqwest", "0.13."), ("http", "1.")):
    selected = [p["version"] for p in packages if p["name"] == name]
    assert selected and all(v.startswith(prefix) for v in selected), (name, selected)
webdriver = [p["version"] for p in packages if p["name"] == "webdriver"]
assert len(webdriver) == 1 and webdriver[0].startswith("0.54."), webdriver
print("Plotly smoke lock selects all three immutable source archives, HTTP1 and Reqwest0.13")
PY
    echo "[plotly-export] $platform build and render PNG with automatic driver download"
    if run_owned "$output/plotly-export.log" "$smoke" "${smoke_env[@]}" cargo run --locked; then
        echo '[plotly-export] passed'
    else
        status=$?
        exit "$status"
    fi
    [ -x "$WEBDRIVER_INSTALL_PATH/chromedriver" ] || {
        echo 'automatic download did not install an executable private ChromeDriver' >&2
        exit 1
    }
    python3 - "$smoke/plot.png" <<'PY'
from pathlib import Path
import struct
import sys

image = Path(sys.argv[1]).read_bytes()
assert image[:8] == b"\x89PNG\r\n\x1a\n", "export did not produce PNG bytes"
assert struct.unpack(">II", image[16:24]) == (320, 240), "export dimensions differ"
assert len(image) > 100, "exported PNG is unexpectedly short"
print(f"Rendered PNG: {len(image)} bytes, 320x240")
PY
    cp "$smoke/plot.png" "$output/plot.png"
    cmp -s "$output/plotly-smoke-Cargo.lock" "$smoke/Cargo.lock" || {
        echo 'Plotly PNG smoke lock changed under --locked rendering' >&2
        exit 1
    }
    run_owned "$output/chromedriver-version.txt" "$work" \
        "${smoke_env[@]}" "$WEBDRIVER_INSTALL_PATH/chromedriver" --version
    grep -F '154.0.8037.92' "$output/chromedriver-version.txt" >/dev/null || {
        echo 'automatically downloaded ChromeDriver has the wrong version' >&2
        exit 1
    }
fi
