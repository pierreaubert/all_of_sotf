# Loudness Practice

## Select the quantity and standard

Distinguish:

- sound pressure level (dB SPL), an acoustic level;
- loudness level (phon), an equal-loudness match referenced to a 1 kHz tone;
- loudness (sone), a perceptual magnitude;
- specific loudness (sone/Bark or the model’s corresponding density);
- programme loudness (for example LUFS under ITU-R BS.1770), a broadcast measurement that is not a Zwicker/ISO 532 psychoacoustic loudness model.

Name the model/edition and field correction. ISO 532-1 (Zwicker) and ISO 532-2 (Moore–Glasberg) are not interchangeable implementations.

## Workflow

1. Calibrate the input to physical level; digital full scale alone is insufficient.
2. Choose free-field, diffuse-field, or headphone transfer assumptions.
3. Form the required spectrum or third-octave levels with the model’s time weighting.
4. Apply threshold, critical-band excitation, and level-dependent compression.
5. Integrate specific loudness using the model’s prescribed frequency scale and numerical resolution.
6. Apply temporal stages for time-varying loudness and report the requested statistic (instantaneous, short-term, percentile, maximum, etc.).
7. Validate against published reference cases or a trusted implementation.

The relation `N = 2^((L_N - 40)/10)` above 40 phon is a conventional approximation/reference mapping, not a substitute for spectral loudness calculation. Likewise, A-weighted level cannot predict loudness across arbitrary spectra, bandwidths, levels, or durations.

## Room/playback cautions

Room compensation can change timbre, DRR, and spatial impression without equivalent changes in a single loudness number. Level-match listening comparisons and evaluate spatial attributes separately (`books/2604.12439.md`). Perceptually weighted spectral losses are useful engineering objectives but require listening or standard-model validation (`books/2606.22563.md`).

## Primary source

Read `books/Psycho_Acoustics-Zwicker_Fastl.md`, Chapters 6–8 for critical-band excitation, partial masking, and loudness.

## Toole corroboration (room-reproduction context)

From *Sound Reproduction*, 3rd ed., §4.4 (local OCR: `books/Toole_Sound_Reproduction_3ed.md`): loudness is the perceptual correlate of level but also depends on frequency, incident angle, signal duration, and temporal envelope. The equal-loudness contours originate in Fletcher and Munson (1933) headphone experiments matching pure tones to a 1 kHz reference, with each contour labeled in phons (the reference SPL) rather than decibels. Practical consequence used throughout the book: playback below the reference/monitoring level shifts the perceived spectral balance, so loudness comparisons and correction evaluations must be level-matched.
