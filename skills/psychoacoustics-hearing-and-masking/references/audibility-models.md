# Audibility and Masking Models

## Measurement context first

State presentation method (free field, diffuse field, headphones), calibration quantity, listener population, ear/channel handling, stimulus duration, bandwidth, level statistic, and psychophysical procedure. Threshold curves and masking data are conditional measurements, not universal constants.

## Audibility workflow

1. Convert the target and masker into a calibrated ear-input representation.
2. Account for outer/middle-ear transfer and threshold in quiet using a named standard/model.
3. Map frequency to the model’s auditory scale (Bark, ERB-rate, or filterbank index); do not mix scales or bandwidth formulas.
4. Compute excitation with level-dependent auditory filters where the chosen model requires them.
5. Combine maskers in the model’s prescribed domain; do not simply add dB thresholds.
6. Apply temporal integration, forward masking, and backward masking only with the model’s stimulus definitions.
7. Report detection margin and model uncertainty, not just a binary audible/inaudible label.

Masking is asymmetric in frequency and level-dependent. Tonal and noise maskers behave differently. Partial masking changes apparent loudness even when a target remains detectable.

## Implementation checks

- Verify frequency warping and filter bandwidth at several reference frequencies.
- Test threshold-in-quiet behavior with no masker.
- Test monotonicity with masker level and sensible release after masker offset.
- Keep binaural unmasking/spatial release separate from monaural critical-band models.
- For codecs, add tonality, temporal smearing, pre-echo control, and conservative safety margins; a textbook threshold model is not by itself a production codec model.

## Primary source

Read `books/Psycho_Acoustics-Zwicker_Fastl.md`, Chapters 1–4 and 6 for procedures, hearing area, nonlinear peripheral processing, masking, critical bands, and excitation.
