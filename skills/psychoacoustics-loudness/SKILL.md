---
name: psychoacoustics-loudness
description: Calculate, implement, or validate psychoacoustic loudness and loudness level for stationary or time-varying sounds. Use for sone, phon, specific loudness, equal-loudness comparisons, ISO 532 Zwicker or Moore–Glasberg models, partial masking effects, calibrated audio-file loudness estimates, or distinguishing psychoacoustic loudness from A-weighted SPL and LUFS.
---

# Loudness

## Choose the metric

State whether the target is SPL, loudness level (phon), loudness (sone), specific loudness, or programme loudness. Name the standard/model, edition, presentation field, input calibration, and requested temporal statistic.

Read [references/loudness-practice.md](references/loudness-practice.md) for metric distinctions, model workflow, validation, and room/playback cautions.

## Compute

1. Convert the signal or band levels to calibrated ear-input levels.
2. Apply the selected free-/diffuse-field or headphone correction.
3. Form the required spectrum or third-octave representation.
4. Apply threshold, excitation, level-dependent compression, and specific-loudness stages exactly as specified.
5. Integrate on the model’s auditory scale.
6. Apply temporal integration for time-varying sounds and report the defined statistic.

## Verify

Use published reference cases or a trusted implementation; test a 1 kHz reference, monotonic level sweeps, bandwidth changes, equal-energy spectra, and attack/release behavior. Record filterbank resolution, interpolation, sample rate, and tolerances.

## Red flags

- Do not substitute A-weighted SPL or LUFS for psychoacoustic loudness.
- Do not use the phon-to-sone rule as the whole spectral model.
- Do not mix ISO 532-1 and ISO 532-2 stages or constants.
- Do not compare room-correction conditions without level matching and separate spatial/timbral assessment.
