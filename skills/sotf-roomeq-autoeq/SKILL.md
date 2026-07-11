---
name: sotf-roomeq-autoeq
description: "Use for SOTF RoomEQ and AutoEQ work: measurement parsing, smoothing, optimizer behavior, passband detection, target curves, IIR/FIR export, CamillaDSP/convolution sidecars, Linux measurement streams, and RoomEQ QA."
---

# SOTF RoomEQ AutoEQ

## When To Use

Use this skill for changes involving `crates/autoeq`, RoomEQ UI/reporting in `crates/app-gpui`, RoomEQ plugin behavior, measurement import/export, CamillaDSP output, convolution artifacts, smoothing, target curves, or multi-measurement optimization.

## Working Sequence

1. Start with `tokensave_context` using RoomEQ-specific terms from the user request.
2. Locate the data contract first: input schema, output schema, measurement bounds, or export format.
3. Keep algorithm fixes close to the math/autoeq layer; keep app crates as thin presentation surfaces.
4. Add regression coverage around the exact data shape that failed.
5. Run a targeted test before any broader QA.

## Invariants

- Filters must stay within measurement-data frequency bounds.
- Passband detection uses relative-to-peak thresholds, not absolute dB values.
- Core filter type is `autoeq_iir::Biquad`.
- Handle mismatched response grids explicitly; do not assume equal frequency vectors.
- Preserve sidecar/export contracts for convolution, CamillaDSP, and report rendering.

## References

- Read `references/invariants-and-commands.md` for RoomEQ commands, known files, and common failure modes.
