#!/usr/bin/env bash
# Fetch pinned Linux validators into this Gitea job's evidence directory.
set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
evidence=${SOTF_PLUGIN_VALIDATOR_EVIDENCE_DIR:-"$root/release-artifact-evidence-plugins-linux/validators"}
[[ $evidence == /* ]] || { echo 'validator evidence path must be absolute' >&2; exit 2; }
mkdir -p "$evidence/downloads" "$evidence/bin"

[[ $(uname -s) == Linux ]] || { echo 'Linux plugin validators require a Linux host' >&2; exit 1; }
host_arch=$(uname -m)
case "$host_arch" in
    x86_64|amd64) host_arch=x86_64 ;;
    aarch64|arm64) host_arch=aarch64 ;;
    *) printf 'Unsupported Linux validator architecture: %s\n' "$host_arch" >&2; exit 1 ;;
esac

validate_native_binary() {
    local name=$1 binary=$2 expected=$3 description lower
    [[ -x $binary ]] || { printf '%s validator is not executable: %s\n' "$name" "$binary" >&2; return 1; }
    description=$(file -b "$binary") || return 1
    lower=$(printf '%s' "$description" | tr '[:upper:]' '[:lower:]')
    if [[ $expected == aarch64 ]]; then
        [[ $lower == *elf* && ( $lower == *aarch64* || $lower == *arm64* ) ]] || {
            printf '%s is not an ARM64 ELF binary: %s\n' "$name" "$description" >&2; return 1;
        }
    else
        [[ $lower == *elf* && ( $lower == *x86-64* || $lower == *x86_64* ) ]] || {
            printf '%s is not an x86_64 ELF binary: %s\n' "$name" "$description" >&2; return 1;
        }
    fi
}

stage_local_validator() {
    local name=$1 variable=$2 candidate destination description
    candidate=${!variable:-}
    if [[ -z $candidate ]]; then candidate=$(command -v "$name" || true); fi
    if [[ -z $candidate || ! -x $candidate ]]; then
        printf 'ARM64 %s is unavailable. Provide a locally installed native validator on PATH or set %s to an existing ARM64 executable; no x86_64 fallback or download is used.\n' \
            "$name" "$variable" >&2
        return 1
    fi
    validate_native_binary "$name" "$candidate" "$host_arch" || return 1
    destination="$evidence/bin/$name"
    cp "$candidate" "$destination"
    chmod 755 "$destination"
    description=$(file -b "$destination")
    printf '%s\tlocal\t%s\t%s\n' "$name" "$candidate" "$description" >>"$evidence/provenance.tsv"
}

if [[ $host_arch == aarch64 ]]; then
    # ARM validator availability varies by runner. Accept only existing native binaries;
    # never substitute the pinned x86_64 archives on an ARM host.
    : >"$evidence/provenance.tsv"
    stage_local_validator pluginval SOTF_PLUGINVAL_PATH
    stage_local_validator clap-validator SOTF_CLAP_VALIDATOR_PATH
else

pluginval_url=https://github.com/Tracktion/pluginval/releases/download/v1.0.4/pluginval_Linux.zip
pluginval_sha=c01c49d8063965c4c2dea8324468336768f5c9139e0b1caebde14c2400b55352
clap_url=https://github.com/free-audio/clap-validator/releases/download/0.4.1/clap-validator-0.4.1-127-g152b982-ubuntu-22.04.zip
clap_sha=49edadcfb407ea0dd946ce418300e853fbd2660fa4b0d00e4f19ff8eef24ad90

fetch() {
    local name=$1 url=$2 sha=$3
    curl --fail --location --show-error --silent --retry 3 --connect-timeout 15 --max-time 180 \
        --output "$evidence/downloads/$name.zip" "$url"
    printf '%s  %s\n' "$sha" "$evidence/downloads/$name.zip" | sha256sum --check
    printf '%s\t%s\t%s\n' "$name" "$url" "$sha" >>"$evidence/provenance.tsv"
}

fetch pluginval "$pluginval_url" "$pluginval_sha"
fetch clap-validator "$clap_url" "$clap_sha"

unzip -p "$evidence/downloads/pluginval.zip" pluginval >"$evidence/bin/pluginval"
chmod 755 "$evidence/bin/pluginval"
unzip -q "$evidence/downloads/clap-validator.zip" -d "$evidence/downloads/clap-extracted"
clap_archives=("$evidence/downloads/clap-extracted"/*.tar.gz)
[[ ${#clap_archives[@]} == 1 && -f ${clap_archives[0]} ]] || {
    echo 'Expected one nested CLAP validator tarball' >&2
    exit 1
}
tar -xzf "${clap_archives[0]}" -C "$evidence/bin" clap-validator
chmod 755 "$evidence/bin/clap-validator"

validate_native_binary pluginval "$evidence/bin/pluginval" "$host_arch"
validate_native_binary clap-validator "$evidence/bin/clap-validator" "$host_arch"
fi

file "$evidence/bin/pluginval" "$evidence/bin/clap-validator" >"$evidence/binary-formats.txt"
ldd "$evidence/bin/pluginval" >"$evidence/pluginval-libraries.txt"
ldd "$evidence/bin/clap-validator" >"$evidence/clap-validator-libraries.txt"
if grep -q 'not found' "$evidence"/*-libraries.txt; then
    echo 'Validator runtime library is missing' >&2
    exit 1
fi
printf '%s\n' "$evidence/bin" >"$evidence/bin-path.txt"
printf 'Job-local validator path: %s\n' "$evidence/bin"
