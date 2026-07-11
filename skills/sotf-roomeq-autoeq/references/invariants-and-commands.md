# RoomEQ and AutoEQ Reference

## Common Areas

- `crates/autoeq`
- `crates/autoeq/bin/roomeq`
- `crates/app-gpui/components/room_eq`
- `crates/app-gpui/tests/room_eq_plot_tests.rs`
- `crates/sotf-plugins/crates/sotf-plugin-xtc`
- `crates/sotf-player` when library or measurement flow affects RoomEQ inputs

## Frequent Checks

- `cargo test -p autoeq roomeq`
- `cargo test -p autoeq spectral`
- `cargo test -p sotf-gpui room_eq`
- `just qa-autoeq`
- `just qa-roomeq-quick`
- `just qa-roomeq-multi-measurement`
- `just qa-roomeq-ci` for broader CI-style RoomEQ validation when available.

## Data and Export Guardrails

- Check the real measurement frequency range before optimizer changes.
- If smoothing changes, include tests for mismatched frequency grids and sparse data.
- For export fixes, assert both primary files and sidecars.
- For CamillaDSP output, verify channel naming, filter ordering, and paths expected by downstream consumers.
- For Linux measurement streams, verify sample format assumptions such as S24 handling.

## Debugging Pattern

1. Reproduce from the smallest measurement/export fixture possible.
2. Inspect the generated DSP output, not only the UI report.
3. Compare before/after filter counts, frequency bounds, and channel maps.
4. Prefer deterministic fixtures over broad golden churn.
