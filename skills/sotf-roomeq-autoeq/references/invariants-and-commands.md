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

### Toole third edition: implementation and QA consequences

Source: *Sound Reproduction*, third edition, sections 8.2.4, 8.2.8–8.6,
12.2.3–12.3, 13.3 and 14.1–14.2.3. Checked against local OCR files
`books/toole3rd/toole_ocr/{241,242,252..268,346..349,370..385}.txt`
(file indices, not printed pages). These are engineering applications of the
book's evidence, not book-specified software defaults or acceptance thresholds.

- **Objective validity:** matching a preferred steady-state room curve does not
  establish improved direct sound. Keep requested correction bounds separate
  from the measured usable band used for calibration and playback assessment.
  Upper-band speaker correction needs appropriate direct-sound/angular evidence;
  a spatial room average alone cannot reveal or repair directivity errors.
- **Multi-sub trade-offs:** optimize the complex sum at each seat; report spatial
  variation, target error, and output efficiency separately. Compare solutions
  before independent normalization and retain per-seat failures. Do not obtain a
  better score simply by cutting useful output or hiding nulls in an average.
- **Routing tests:** replay each logical input, then relevant correlated inputs
  through the same serialized graph. Include L=R bass for shared-bass systems:
  opposite per-input route polarities can pass isolated-input splice tests yet
  cancel mono bass. Preserve explicit stereo-bass intent when it is requested.
  Keep LFE gain/bandwidth distinct from redirected bass; a main high-pass does not
  eliminate the low-pass signal redirected from that input.
- **Resolution and decay:** retain fine, reliable bass data for matching modal Q,
  plus a smoother perceptual view. Matched PEQ can reduce driven-system ringing
  without changing passive room damping. Do not optimize a coarse display alone
  or make a universal decay-time gate from stimulus-specific audibility studies.
- **Acceptance evidence:** a residual dip exceeding a quality target is not by
  itself proof of regression. Compare against the same protected structural
  baseline and retain independent safety, seat, output, and summation checks.
  Do not relabel a remaining defect as a correction-induced defect, or a numeric
  improvement as demonstrated audibility. Budgets remain explicit product/user
  choices, not values inferred from this book.
- **Useful regression fixtures:** a smoother spatial mean with a worse seat;
  similar seat consistency but materially different required drive; a shared
  bass matrix with opposing input polarities; an unchanged upper-band response
  under bass-only EQ; and a minimum-phase modal peak whose matched cut reduces
  delivered ringing. Assert behavior, not just formatted reports or lower scores.

### Other research

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
