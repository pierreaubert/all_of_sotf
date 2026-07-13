# RoomEQ and AutoEQ Reference

## Common areas

- `crates/autoeq`
- `crates/autoeq/bin/roomeq`
- `crates/app-gpui/components/room_eq`
- `crates/app-gpui/tests/room_eq_plot_tests.rs`
- `crates/sotf-plugins/crates/sotf-plugin-xtc`
- `crates/sotf-player` when library or measurement flow affects RoomEQ inputs

## Data and optimizer guardrails

- Preserve calibration and distinguish dB amplitude, dB power, linear magnitude, and complex transfer data.
- Check actual data bounds, invalid bins, duplicate/unsorted frequencies, sparse regions, and mismatched grids.
- State smoothing domain and bandwidth; include edge behavior and grid-invariance tests.
- Constrain gain, Q, frequency, count, headroom, and correction bandwidth; penalize solutions that fit noise or create excessive ringing.
- Treat deep narrow nulls and position-specific cancellations as poor inversion targets.
- Evaluate every measurement position plus the aggregate; record the sweet-spot/spatial-robustness tradeoff.
- Inspect impulse/step response and latency as well as magnitude error.

## Lessons from the bundled room literature

- Distance-weighted multi-position prototypes can improve a preferred position without losing area robustness, but the published work still calls for perceptual validation (`books/2409.10131.md`).
- Phase features can improve blind RT/volume estimation, but results are dataset/model dependent (`books/2303.07449.md`).
- Exact shoebox-ISM inversion is demonstrated for low-passed simulated multichannel RIRs, not arbitrary measured rooms (`books/2405.03385.md`).
- Sparse magnitude-field reconstruction is not complex-field reconstruction and was evaluated only within its training/test regime (`books/2605.10398.md`).
- Sound-speed drift can invalidate phase-sensitive multichannel control; record environmental/calibration assumptions (`books/2602.16416.md`).
- Adaptive DDSP room EQ exposes frame-size, computation, tracking, estimator, and optimizer-stability tradeoffs (`books/2606.22563.md`).
- Spectral correction alone does not control DRR or apparent distance; spatial compensation requires separate design and listening evidence (`books/2604.12439.md`).

## Export guardrails

- Assert primary files and sidecars.
- For CamillaDSP, verify channel names, filter ordering, gains, rates, paths, and downstream parsing.
- For convolution, verify sample rate, channel layout, normalization/headroom, latency, length, and artifact existence.
- For Linux streams, verify sample formats such as S24, endianness, interleaving, and short-read behavior.

## Frequent checks

- `cargo test -p autoeq roomeq`
- `cargo test -p autoeq spectral`
- `cargo test -p sotf-gpui room_eq`
- `just qa-autoeq`
- `just qa-roomeq-quick`
- `just qa-roomeq-multi-measurement`
- `just qa-roomeq-ci`
