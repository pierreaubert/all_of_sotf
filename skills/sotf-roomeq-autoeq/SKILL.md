---
name: sotf-roomeq-autoeq
description: Implement and validate SOTF RoomEQ and AutoEQ measurement, optimization, filtering, and export workflows. Use for measurement parsing or streams, response-grid alignment, smoothing, passband and target curves, multi-position optimization, IIR/FIR design, RoomEQ UI/reporting, convolution or CamillaDSP export, adaptive/online room response work, and RoomEQ QA.
---

# SOTF RoomEQ and AutoEQ

## Working sequence

1. Start with `tokensave_context` using the concrete RoomEQ terms, then locate data contracts, call paths, and tests.
2. Record measurement calibration, sample rate, frequency range/grid, smoothing, channel/position identity, and uncertainty before changing math.
3. Keep algorithm changes in the math/AutoEQ layer and app crates as presentation/coordination surfaces.
4. Define the optimization objective, parameter bounds, regularization, spatial aggregation, phase/latency treatment, and expected artifact contract.
5. Add a deterministic regression fixture for the exact data shape and run focused tests before broad QA.

Read [references/invariants-and-commands.md](references/invariants-and-commands.md) for repository contracts, research-derived guardrails, and verification commands.

## Core invariants

- Keep filters inside trustworthy measurement-data frequency bounds.
- Use relative-to-peak thresholds for passband detection.
- Use `autoeq_iir::Biquad` as the core filter type.
- Align or resample mismatched response grids explicitly; never zip by index without proving equality.
- Preserve convolution, CamillaDSP, report, and sidecar contracts.
- Optimize no finer than the measurement/smoothing resolution warrants.
- Separate minimum-phase/magnitude correction from excess-phase, time-domain, and spatial-control claims.

## Validation dimensions

Evaluate raw and smoothed response, target error, filter gain/Q/count, time response/ringing, headroom, latency, robustness across positions, and export round-trip. For perceptual claims, level-match and test timbre/spatial attributes rather than relying on one spectral score.

## Handoff

Report the measurement assumptions, algorithmic change, affected exports/UI, before/after objective values, spatial/time-domain tradeoffs, and exact QA commands.
