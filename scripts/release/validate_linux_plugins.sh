#!/usr/bin/env bash
# Validate every staged Linux plugin and retain each validator transcript.
set -uo pipefail

format=${1:?select vst3 or clap}
evidence=${2:?absolute artifact evidence directory required}
case "$format" in
    vst3) directory=dist/vst3-linux; extension=vst3 ;;
    clap) directory=dist/clap-linux; extension=clap ;;
    *) echo "unsupported plugin format: $format" >&2; exit 2 ;;
esac
[[ $evidence == /* ]] || { echo 'artifact evidence path must be absolute' >&2; exit 2; }
shopt -s nullglob
plugins=("$directory"/*."$extension")
staged=("$evidence/artifacts/sotf-daw/$directory"/*."$extension")
if [[ ${#plugins[@]} -ne 43 || ${#staged[@]} -ne 43 || ${#plugins[@]} -ne ${#staged[@]} ]]; then
    printf 'Expected 43 built and staged %s plugins, found %s built and %s staged\n' \
        "$format" "${#plugins[@]}" "${#staged[@]}" >&2
    exit 1
fi
for plugin in "${plugins[@]}"; do
    [[ -e $evidence/artifacts/sotf-daw/$plugin ]] || {
        echo "built plugin missing from staged artifacts: $plugin" >&2
        exit 1
    }
done

log_directory="$evidence/logs/$format-validators"
mkdir -p "$log_directory" || exit 1
printf 'plugin\texit_code\tlog\n' >"$log_directory/results.tsv"
failed=0
for plugin in "${plugins[@]}"; do
    name=$(basename "$plugin" ".$extension")
    staged_plugin="$evidence/artifacts/sotf-daw/$plugin"
    log="$log_directory/$name.log"
    if [[ $format == vst3 ]]; then
        if [[ ! -f "$staged_plugin/Contents/x86_64-linux/$name.so" ]]; then
            printf 'VST3 bundle binary must match bundle name: %s/Contents/x86_64-linux/%s.so\n' \
                "$staged_plugin" "$name" >"$log"
            status=1
        else
            pluginval --validate "$staged_plugin" --strictness-level 5 --timeout-ms 30000 >"$log" 2>&1
            status=$?
        fi
    else
        clap-validator validate "$staged_plugin" >"$log" 2>&1
        status=$?
    fi
    printf '%s\t%s\t%s\n' "$name" "$status" "$log" >>"$log_directory/results.tsv"
    printf '%-32s %s (exit %s)\n' "$name" "$([[ $status -eq 0 ]] && echo PASS || echo FAIL)" "$status"
    if (( status != 0 )); then failed=$((failed + 1)); fi
done
printf '%s validation: %s passed, %s failed of %s\n' \
    "$format" "$(( ${#plugins[@]} - failed ))" "$failed" "${#plugins[@]}"
(( failed == 0 ))
