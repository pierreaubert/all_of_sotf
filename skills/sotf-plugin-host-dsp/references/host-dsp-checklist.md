# Plugin Host DSP Checklist

## Realtime and buffer contracts

- Allocate and plan FFTs in setup; reuse buffers and state in `process()`.
- Avoid mutexes, blocking I/O, formatting/logging, filesystem access, and unpredictable destruction on the audio thread.
- `NodeBuffer::clear()` resets `actual_len`; do not assume it zeroes memory.
- Know whether every output sample/channel must be overwritten, cleared, or accumulated.
- Preserve `context.num_frames`; STFT/ring-buffer plugins must not silently shorten output.
- Define channel order and behavior for absent, added, or changing channels.
- Reset delay lines, smoothers, overlap buffers, and adaptive state deterministically.

## FFT, STFT, and filters

- Declare sample rate, FFT length, hop, window, scaling, padding, and algorithmic latency.
- Verify constant-overlap-add or weighted overlap-add reconstruction.
- Distinguish DFT bin spacing from resolution and circular from linear convolution.
- Check conjugate symmetry and DC/Nyquist handling for real transforms.
- Prefer SOS for higher-order IIR; test coefficient updates, state scaling, denormals, overflow, and pole stability.
- Smooth parameters in physical or perceptually suitable domains and test sample-rate/block-size independence.

## Parameter/preset wiring

- Update cached parameter rebuild, registration, `set_parameter`, `get_parameter`, units/ranges/defaults, UI layout/schema, and serialization together.
- Preserve older preset state through explicit defaults/version migration.
- Test host-visible automation at block boundaries and within blocks where supported.

## Adaptive/acoustic DSP evidence

Recent room-EQ work in `books/2606.22563.md` highlights a tradeoff between frame size, stability, computation, and tracking; reliable online response estimation is part of the control loop, not an incidental input. `books/2501.16367.md` likewise treats process/observation uncertainty explicitly in acoustic adaptive filtering. Carry these lessons into tests without claiming the papers validate a particular SOTF implementation.

## Frequent checks

- `cargo test -p sotf-plugins <plugin-or-feature>`
- `cargo test -p sotf-host automation --lib`
- `cargo test -p sotf-engine <decoder-or-engine-filter> --lib`
- `cargo check -p sotf-host`
- `cargo check -p sotf-engine`
- `cargo clippy -p sotf-plugins -- -W warnings`
- `just qa-plugin`
