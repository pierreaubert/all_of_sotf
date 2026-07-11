# Plugin Host DSP Checklist

## Parameter Wiring

Plugin parameters commonly need updates in all of these places:

- Cached parameter rebuild path.
- `set_parameter`.
- `get_parameter`.
- UI schema or layout metadata when exposed to the app.
- Preset serialization/deserialization when persistent.
- Tests that prove host-visible updates are accepted.

Missing cached metadata can cause silent rejection.

## Audio Engine and Host Contracts

- `NodeBuffer::clear()` resets `actual_len`; do not assume it zeroes memory.
- Output buffers may be pre-zeroed; know whether the plugin is expected to overwrite or accumulate.
- Channel count can change across plugins, such as stereo to upmixed layouts.
- Automation curves and smoothing coefficients should be tested with block-size and sample-rate variation.
- MIDI and transport context changes should be checked at host boundaries, not only plugin internals.

## Frequent Checks

- `cargo test -p sotf-plugins <plugin-or-feature>`
- `cargo test -p sotf-host automation --lib`
- `cargo test -p sotf-engine <decoder-or-engine-filter> --lib`
- `cargo check -p sotf-host`
- `cargo check -p sotf-engine`
- `cargo clippy -p sotf-plugins -- -W warnings` when changing shared plugin code.
- `just qa-plugin` for plugin QA.

## Review Focus

- Allocations or locks in process paths.
- Parameter range, default, smoothing, and unit mismatches.
- Preset compatibility with older saved state.
- Multichannel behavior and channel ordering.
- Regression tests for the exact plugin variant touched.
