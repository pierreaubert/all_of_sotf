---
name: psychoacoustics-pitch-timbre-roughness
description: Analyze or implement perceptual models of pitch and pitch strength, virtual/missing-fundamental pitch, multidimensional timbre, sharpness, sensory pleasantness, fluctuation strength, roughness, beating, or subjective duration. Use for audio-feature interpretation, sound-quality metrics, modulation perception, timbre comparisons, or controlled listening-test design.
---

# Pitch, Timbre, and Modulation Attributes

## Identify the attribute

Separate the requested percept from acoustic proxies and likely confounds. State calibration, listener population, duration, temporal variation, and whether stimuli are level- and pitch-matched.

Read [references/attributes.md](references/attributes.md) for cue selection, model workflow, confounds, and spatial-playback cautions.

## Analyze

- For pitch, test harmonicity/periodicity and resolved/unresolved components; include virtual pitch for missing fundamentals.
- For timbre, preserve spectral envelope, attack/decay, modulation, and time variation; report multiple interpretable dimensions or a task-defined embedding.
- For sharpness, start from a calibrated loudness/excitation representation, not spectral centroid alone.
- For fluctuation strength and roughness, analyze modulation within auditory channels and use the selected model’s rate/level dependence.
- For subjective duration, include onset/offset and level/temporal context.

## Verify

Use synthetic controls: missing-fundamental complexes, equal-loudness spectral tilts, two-tone beating, AM-rate sweeps, and matched physical-duration stimuli. Compare against reference implementations or listening data and report model validity bounds.

## Red flags

- Do not estimate pitch from only the largest FFT bin.
- Do not define roughness and fluctuation strength by universal hard modulation cutoffs.
- Do not call a one-number spectral descriptor “timbre.”
- Do not attribute room-EQ preference to timbre when loudness, DRR, or apparent distance also changed.
