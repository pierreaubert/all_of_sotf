---
name: psychoacoustics-problem-solving
description: Analyze human auditory-perception questions and select audibility/masking, loudness, pitch, timbre, sharpness, roughness, fluctuation-strength, or duration models. Use for perceptual audio metrics, listening-test design, codec or audio-product models, room-correction perception, or any task where calibration, listener population, stimulus context, and model validity determine the answer.
---

# Psychoacoustics Problem Solving

## Define the observation

1. Name the perceptual attribute and distinguish it from its acoustic correlate.
2. State listener population, monaural/binaural presentation, field/headphone transfer, calibration, spectrum, level, duration, and temporal context.
3. Choose a named standard/model and edition; do not merge formulas from incompatible auditory scales or standards.

## Route by attribute

- Load `psychoacoustics-hearing-and-masking` for threshold in quiet, critical bands/auditory filters, excitation, simultaneous/temporal masking, detection, or codec audibility.
- Load `psychoacoustics-loudness` for phon/sone/specific loudness, partial masking, stationary/time-varying loudness, or psychoacoustic meter design.
- Load `psychoacoustics-pitch-timbre-roughness` for pitch/pitch strength, timbre, sharpness, sensory pleasantness, fluctuation strength, roughness, or subjective duration.
- Combine skills when masking changes loudness, room correction changes timbre and distance, or pitch salience depends on audibility.

## Validate perceptual claims

Use reference stimuli or published model cases, sensitivity analysis, and controlled listening tests when claiming listener benefit. Level-match comparisons unless loudness is the independent variable; randomize order, define anchors, report uncertainty and listener exclusions, and separate objective metric improvement from preference or audibility. Toole (§3.1; local OCR `books/Toole_Sound_Reproduction_3ed.md`) shows why: sighted evaluations let brand, appearance, price, and louder playback decide, with "different" or louder routinely passing as better in the absence of equal-loudness comparison — so conceal product identities in any preference or audibility test.

## Red flags

- Never use A-weighted SPL as universal loudness.
- Never treat critical-band, Bark, ERB, and mel scales as interchangeable.
- Never turn a population-average threshold into a guarantee for an individual.
- Never infer spatial or timbral preference from spectral error alone.
