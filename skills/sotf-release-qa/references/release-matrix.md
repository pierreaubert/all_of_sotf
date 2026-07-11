# Release and QA Matrix

## Baseline

- `just` lists available commands.
- `just ntest` should pass cleanly for release-level confidence.
- Full `just qa` is slow and can take hours.

## Minimal QA Subsets

- AutoEQ: `just qa-autoeq`
- RoomEQ quick: `just qa-roomeq-quick`
- RoomEQ multi-measurement: `just qa-roomeq-multi-measurement`
- Plugins: `just qa-plugin`

## Build and Packaging

- Release helper: `./scripts/build-release.sh --help`
- macOS ARM: `just cross-macos-arm64`
- Linux ARM: `just cross-linux-arm64`
- Windows ARM: `just cross-windows-arm64`
- Linux x86 host builds: `just cross-linux-x86`
- Windows x86 from Linux notes: `just cross-windows-86`
- GPUI debug run signs with `scripts/debug.entitlements`.
- GPUI release run signs with `scripts/entitlements.plist`.
- Distribution files land in `./dist` unless the command says otherwise.

## Apple Platforms

- iOS simulator: `just ios-sim`
- iOS device: `just ios-device`
- tvOS simulator is experimental and may require nightly plus `aarch64-apple-tvos-sim`.

## Reporting Template

Use this shape in final summaries and PR descriptions:

- Summary: what changed.
- Verification: exact commands and results.
- Skipped: checks not run and why.
- Risk: remaining platform or data-shape risk.
