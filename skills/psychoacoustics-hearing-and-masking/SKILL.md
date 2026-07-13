---
name: psychoacoustics-hearing-and-masking
description: Predict or measure auditory threshold, audibility, excitation, critical-band/auditory-filter effects, simultaneous masking, forward/backward masking, partial masking, or spatial release from masking. Use for detection margins, psychoacoustic codec models, hearing-area calculations, tonal/noise maskers, temporal masking, or peripheral auditory-model implementations.
---

# Hearing and Masking

## Establish the experiment/model

Record calibration, presentation path, listener population, target/masker spectrum and level, duration/onsets, binaural configuration, and psychophysical criterion. Choose a named threshold and auditory-filter model.

Read [references/audibility-models.md](references/audibility-models.md) for the complete workflow, implementation tests, and codec cautions.

## Compute audibility

1. Convert stimuli to the calibrated ear-input domain.
2. Apply threshold-in-quiet and outer/middle-ear transfer assumptions.
3. Transform frequency using the chosen Bark/ERB/filterbank definition.
4. Compute level-dependent excitation/spreading and tonal-versus-noise behavior.
5. Combine maskers in the prescribed model domain.
6. Apply temporal masking/integration and binaural processing only if the selected model supports them.
7. Report target level minus masked threshold with uncertainty and parameter sensitivity.

## Verify

Test the no-masker threshold, frequency asymmetry/upward spread, monotonicity with masker level, temporal release, low/high-frequency limits, and reference cases from the model source.

## Red flags

- Do not add masker levels or threshold shifts directly in dB unless the model explicitly says so.
- Do not use a fixed critical bandwidth or universal premasking/postmasking duration.
- Do not confuse detectability, partial masking, and loudness reduction.
- Do not apply a monaural model to binaural unmasking without an explicit binaural stage.
