#!/usr/bin/env bash
# Fetch pinned Linux validators into this Gitea job's evidence directory.
set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
evidence="$root/release-artifact-evidence-plugins-linux/validators"
mkdir -p "$evidence/downloads" "$evidence/bin"

[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || {
    echo 'Pinned Linux validators require an x86_64 Linux runner' >&2
    exit 1
}

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

file "$evidence/bin/pluginval" "$evidence/bin/clap-validator" >"$evidence/binary-formats.txt"
ldd "$evidence/bin/pluginval" >"$evidence/pluginval-libraries.txt"
ldd "$evidence/bin/clap-validator" >"$evidence/clap-validator-libraries.txt"
if grep -q 'not found' "$evidence"/*-libraries.txt; then
    echo 'Validator runtime library is missing' >&2
    exit 1
fi
printf '%s\n' "$evidence/bin" >"$evidence/bin-path.txt"
printf 'Job-local validator path: %s\n' "$evidence/bin"
