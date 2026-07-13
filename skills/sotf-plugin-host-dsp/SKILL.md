---
name: sotf-plugin-host-dsp
description: Implement and review SOTF plugin-host and DSP behavior across sotf-plugins, sotf-host, and engine integration. Use for realtime process paths, STFT/FFT or adaptive processing, automation and smoothing, parameter registration, channel layouts, presets, external plugin hosting, plugin UI schemas, latency, or host transport/MIDI contracts.
---

# SOTF Plugin Host DSP

## Working sequence

1. Use TokenSave to locate the plugin, host contract, callers, and focused tests before reading source.
2. Classify the change as signal behavior, block/streaming behavior, parameter metadata, UI schema, preset compatibility, or host context.
3. Write the DSP convention and invariants: sample rate, block length, channel order, latency, overwrite/accumulate semantics, transform normalization, state reset, and parameter units.
4. Keep allocation, locking, logging, and unbounded work out of realtime processing.
5. Update registration, setters/getters, cached metadata, schemas, presets, and automation together when a parameter changes.
6. Add a deterministic regression test and run focused crate checks before broader QA.

Read [references/host-dsp-checklist.md](references/host-dsp-checklist.md) for realtime, FFT/STFT, parameter, and verification guardrails.

## DSP verification

- Compare streaming output with an offline/reference calculation across varied block sizes, including partial final blocks.
- Test impulse, silence, DC, sinusoid, step, and non-finite inputs as relevant.
- Verify bypass, reset, sample-rate change, channel-count transition, and automation boundaries.
- For FFT/STFT code, test window/overlap normalization, reconstruction, padding, latency, and circular-versus-linear behavior.
- For adaptive algorithms, report convergence, tracking, latency, estimator error, and stability under nonstationary programme material; a lower loss in one scenario is not a realtime-safety result.

## Handoff

Report affected contracts, audible behavior, realtime-path impact, preset/schema compatibility, and exact verification commands.
