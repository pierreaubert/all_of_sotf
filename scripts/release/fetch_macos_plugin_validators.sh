#!/usr/bin/env bash
# Fetch pinned validators into this job's evidence directory, without installing them.
set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
evidence="${SOTF_ARTIFACT_EVIDENCE_DIR:-$root/release-artifact-evidence-plugins-macos}/validators"
[[ $evidence == /* ]] || { echo 'validator evidence path must be absolute' >&2; exit 2; }
mkdir -p "$evidence/downloads" "$evidence/extracted" "$evidence/bin"

[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || {
    echo 'Pinned macOS validators require an Apple Silicon runner' >&2
    exit 1
}
macos_major=$(sw_vers -productVersion | cut -d. -f1)
[[ $macos_major =~ ^[0-9]+$ && $macos_major -ge 15 ]] || {
    echo 'Pinned CLAP validator requires macOS 15 or newer' >&2
    exit 1
}

pluginval_url=https://github.com/Tracktion/pluginval/releases/download/v1.0.4/pluginval_macOS.zip
pluginval_sha=3c4c533bda0c5059eea3ddaea752d757ee2025041f0f47e6bcb0e87f6082b29f
clap_url=https://github.com/free-audio/clap-validator/releases/download/0.4.1/clap-validator-0.4.1-127-g152b982-macos-15-aarch64.zip
clap_sha=719a0248ea431718bb7c92c8a0b9a78afa0bb23d692cf452e80973fe8b89282d

fetch() {
    local name=$1 url=$2 sha=$3
    curl --fail --location --show-error --silent --retry 3 --connect-timeout 15 --max-time 180 \
        --output "$evidence/downloads/$name.zip" "$url"
    printf '%s  %s\n' "$sha" "$evidence/downloads/$name.zip" | shasum -a 256 --check
    printf '%s\t%s\t%s\n' "$name" "$url" "$sha" >>"$evidence/provenance.tsv"
}

fetch pluginval "$pluginval_url" "$pluginval_sha"
fetch clap-validator "$clap_url" "$clap_sha"

# Keep the application bundle intact so pluginval can locate its resources.
ditto -x -k "$evidence/downloads/pluginval.zip" "$evidence/extracted/pluginval"
pluginval="$evidence/extracted/pluginval/pluginval.app/Contents/MacOS/pluginval"
[[ -x $pluginval ]] || { echo 'pluginval executable missing from official archive' >&2; exit 1; }
cat >"$evidence/bin/pluginval" <<EOF
#!/usr/bin/env bash
exec "$pluginval" "\$@"
EOF
chmod 755 "$evidence/bin/pluginval"

ditto -x -k "$evidence/downloads/clap-validator.zip" "$evidence/extracted/clap-validator"
shopt -s nullglob
clap_archives=("$evidence/extracted/clap-validator"/*.tar.gz)
[[ ${#clap_archives[@]} == 1 ]] || { echo 'expected one nested CLAP validator tarball' >&2; exit 1; }
tar -xzf "${clap_archives[0]}" -C "$evidence/bin" clap-validator
[[ -x $evidence/bin/clap-validator ]] || { echo 'CLAP validator executable missing' >&2; exit 1; }

file "$pluginval" "$evidence/bin/clap-validator" >"$evidence/binary-formats.txt"
printf '%s\n' "$evidence/bin" >"$evidence/bin-path.txt"
printf 'job-local validator path: %s\n' "$evidence/bin"
