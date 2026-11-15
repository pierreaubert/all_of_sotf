#!/usr/bin/env bash
#
# Gate shipped Linux artifacts against the declared support floors
# (linux-2026114.md, decision D1):
#
#   * CPU: x86-64-v2 / Apollo Lake (Celeron J3455) — no AVX at all on
#     the floor machines. No instruction outside the v2 baseline may
#     appear in non-dispatched code. AMD-only SSE4a (`extrq`/`insertq`
#     and friends, emitted by target-cpu=native on a Zen builder) is
#     rejected unconditionally: it SIGILLs on every Intel CPU and was
#     the root cause of sotf#246. AVX-512 (zmm/%k registers) is allowed
#     only inside known CPUID-dispatched code (aws-lc crypto, the aes
#     crate's vaes512 backend, vello's fearless_simd, crc32fast).
#   * glibc: Ubuntu 24.04 floor — no GLIBC_ requirement above 2.39, so
#     a builder upgrade cannot silently lock out 24.04 users.
#
# Usage:
#   scripts/check-linux-artifact.sh <path>...
#
# Each path may be an ELF binary, a directory (scanned recursively),
# an .AppImage, a .deb, or a .tar.gz. Exit code 0 = all artifacts pass.
#
# Negative control: this script must FAIL on the shipped 0.7.17
# sotf-desktop binary (12 SSE4a sites) — if it ever passes that file,
# the gate is broken.

set -euo pipefail

MAX_GLIBC="2.39"
# Symbols allowed to contain AVX-512 (all CPUID-dispatched upstream).
AVX512_ALLOW='aws_lc|avx512|fearless_simd|vaes512|ifma|skip_iv_|iv_len_'

fail=0
checked=0
tmpdirs=()
cleanup() {
    local d
    for d in "${tmpdirs[@]:-}"; do
        if [ -n "$d" ]; then rm -rf "$d"; fi
    done
    return 0
}
trap cleanup EXIT

is_elf() {
    head -c 4 "$1" 2>/dev/null | grep -q $'\x7fELF'
}

check_elf() {
    local elf="$1"
    checked=$((checked + 1))

    # --- glibc floor -------------------------------------------------
    local max_glibc
    max_glibc=$(objdump -T "$elf" 2>/dev/null \
        | grep -o 'GLIBC_[0-9][0-9.]*' | sed 's/GLIBC_//' \
        | sort -Vu | tail -n 1 || true)
    if [ -n "$max_glibc" ]; then
        local newest
        newest=$(printf '%s\n%s\n' "$max_glibc" "$MAX_GLIBC" | sort -V | tail -n 1)
        if [ "$newest" != "$MAX_GLIBC" ]; then
            echo "FAIL $elf: requires GLIBC_$max_glibc > $MAX_GLIBC (Ubuntu 24.04 floor)"
            fail=1
        fi
    fi

    # --- instruction floor (x86-64 only) -----------------------------
    if file "$elf" | grep -q 'x86-64'; then
        local hits
        # NB: no \b in the awk patterns — mawk does not support it.
        hits=$(objdump -d --no-show-raw-insn "$elf" 2>/dev/null | awk \
            -v allow="$AVX512_ALLOW" '
            /^[0-9a-f]+ </ { sym = $0; next }
            /(^|[ \t])(extrq|insertq|clzero|wbnoinvd|mwaitx)([ \t]|$)/ {
                print "SSE4a in " sym; next
            }
            /zmm|%k[0-7]([^0-9]|$)/ {
                if (sym !~ allow) print "AVX-512 outside dispatched code in " sym
            }' | sort -u | head -n 10 || true)
        if [ -n "$hits" ]; then
            echo "FAIL $elf: instructions above the x86-64-v2 floor:"
            echo "$hits" | sed 's/^/  /'
            fail=1
        fi
    fi
}

scan_path() {
    local path="$1"
    if [ -d "$path" ]; then
        local f
        while IFS= read -r f; do
            is_elf "$f" && check_elf "$f"
        done < <(find "$path" -type f -perm -u+x | sort)
        return
    fi
    case "$path" in
        *.AppImage)
            local d; d=$(mktemp -d); tmpdirs+=("$d")
            (cd "$d" && "$OLDPWD/$path" --appimage-extract >/dev/null 2>&1) \
                || (cd "$d" && "$(readlink -f "$path")" --appimage-extract >/dev/null 2>&1) \
                || { echo "FAIL $path: cannot extract AppImage"; fail=1; return; }
            scan_path "$d/squashfs-root"
            ;;
        *.deb)
            local d; d=$(mktemp -d); tmpdirs+=("$d")
            dpkg-deb -x "$path" "$d" || { echo "FAIL $path: dpkg-deb -x failed"; fail=1; return; }
            scan_path "$d"
            ;;
        *.tar.gz|*.tgz)
            local d; d=$(mktemp -d); tmpdirs+=("$d")
            tar -xzf "$path" -C "$d" || { echo "FAIL $path: tar extract failed"; fail=1; return; }
            scan_path "$d"
            ;;
        *)
            if is_elf "$path"; then
                check_elf "$path"
            else
                echo "SKIP $path: not an ELF, AppImage, .deb or .tar.gz"
            fi
            ;;
    esac
}

[ $# -ge 1 ] || { echo "usage: $0 <artifact>..." >&2; exit 2; }
for p in "$@"; do
    [ -e "$p" ] || { echo "FAIL $p: no such file"; fail=1; continue; }
    scan_path "$p"
done

if [ "$checked" -eq 0 ]; then
    echo "FAIL: no ELF binaries found in the given artifacts"
    exit 1
fi
if [ "$fail" -ne 0 ]; then
    echo "check-linux-artifact: FAILED ($checked ELF file(s) checked)"
    exit 1
fi
echo "check-linux-artifact: OK ($checked ELF file(s), x86-64-v2 + GLIBC <= $MAX_GLIBC)"
