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

## Toole corroboration (room-reproduction context)

From *Sound Reproduction*, 3rd ed. (local OCR: `books/Toole_Sound_Reproduction_3ed.md`):

- For a simple minimum-phase resonance, magnitude shape and ringing are linked;
  neither peak height nor decay duration alone supplies an audibility threshold.
  Bandwidth/Q, frequency, stimulus spectrum, persistence, and reflections matter.
  Low-Q peaks can be detected at smaller heights, but high-Q defects can become
  conspicuous when programme energy excites them (§4.6.2). Do not classify a
  complete multi-driver speaker-room transfer as minimum-phase on this basis.
- Dense programme can mask products that sparse test tones expose. THD/IMD
  percentages without product spectra, level and masking context do not establish
  audibility or preference. Section 4.9's comparison is not a guarantee that music
  masks all distortion or that intermodulation always sounds worse.
- Upward masking spread is level- and frequency-dependent. Bass masking is one
  possible contributor to poor dialogue intelligibility, not a diagnosis from
  bass level alone; mix balance, other maskers, room paths and binaural hearing
  also matter. Difference products may fall in less-masked regions in a particular
  test, but assess the actual target/masker spectra rather than the product label.

### Resolution and population limits

Focused source check: Toole sections 4.6.2–4.6.5, 4.9 and 17.3, local
`books/toole3rd/toole_ocr/{101..112,117..119,430..431}.txt`. Numbers identify
OCR files, not printed pages; no numerical threshold was recovered from plots.

- A critical band or ERB describes an auditory-filter property, not a hard bin
  below which spectral changes are inaudible. Within-band changes can alter
  beating, roughness and timbre. Do not discard narrow features merely because
  a coarse 1/3-octave display or excitation average hides them.
- Describe spatial release from masking using the stated task and outcome, often
  a change in speech-reception threshold between spatial conditions. It is not
  universally an angular-resolution threshold. Preserve target/masker directions,
  ear signals, room context and listener characteristics; monaural SNR is not a
  complete binaural prediction.
- Hearing loss can affect filter selectivity, loudness growth and binaural
  processing, not just shift threshold. A normal audiogram does not certify
  identical speech-in-noise performance. Do not diagnose neural damage from
  these observations or apply a reported group result to every individual.
