# Source provenance and capture qualifications

Read on 2026-09-19: all four PDFs and both PPTX files directly under the sibling `books/keith` directory, plus all three DOCX guides and the PPTX in `books/toole3rd-extras`. Conversion used MarkItDown from a temporary installation because the configured Headroom executable was missing. The extracted text included document text and slide text/notes. Image-only settings, figures and equations were not independently visually verified; this skill does not invent values from those images.

The supplied material concerns acoustic measurement recordings rather than musical-performance recording, microphone artistry, editing, or mixing. This skill therefore focuses on acquisition for loudspeaker and room analysis. It requires no specific measurement application, convolver, operating system, or device brand. The sources remain optional further reading, not runtime dependencies.

The Toole material is his own set of simplified guides and slides supplementing *Sound Reproduction*, third edition. Since 2026-09-20 the full third-edition text has additionally been read via tesseract OCR of the owner's paper-copy scans (`books/toole3rd/1.png`–`474.png`, working copy in `books/Toole_Sound_Reproduction_3ed.md`, figure index in `books/Toole_Sound_Reproduction_3ed_figures.md`; both local-only, not for redistribution). Book chapter/section pointers below were verified against that OCR.

## Sources and relevant sections

| File | Author / edition | Capture material |
| --- | --- | --- |
| `2. REW Full eBook.pdf` | Keith Wong, *REW Book 2: Taking and Interpreting Measurements*, 84 pages; first published 2025-11-21, revised 2026-07-19 | §1: microphone, calibration and channel tests; §2: level/SNR, stationary/multi-point/moving/noise/sub captures; §3: direct-sound limits and processed routing; §4: quality and interpretation |
| `100. Acourate for Multichannel Speakers.pdf` | Keith Wong, *Acourate for DSP Controlled Active Speakers with Subwoofers*, 74 pages | §§1–3: mapping, clocking, calibration and gain; §5: driver capture and excitation; §6: timing; §8: verification; §9.1: spatial capture; §10.3–10.4: subwoofer timing ambiguities |
| `101. Acourate for Passive Speakers and One or More Subwoofers.pdf` | Keith Wong, *Acourate for Passive Speakers with Optional Subwoofers*, 36 pages | §§1–2: calibration/gain; §4: direct-sound geometry; §5: timing capture; §§6–7: room versus speaker measurements and final verification |
| `1. MAC Talk Treble.pptx` | Keith Wong, *Loudspeakers in listening rooms Part 1*, 173 slides | Slides 22–83: measurement views; 85–94: ambient noise; 99–170: interpretation context |
| `2. MAC Talk Bass.pptx` | Keith Wong, *Loudspeakers in listening rooms Part 2: Bass*, 201 slides | Slides 17–76: spatial dependence, IR/step and noise-limited decay; 138–154: time/phase context |
| `acoustic_measurement_standards.pdf` | Nyal Mellor and Jeff Hedback, 2011, *Acoustical Measurement Standards for Stereo Listening Rooms*, 30 pages | p.3 and §§A–F: individual versus combined measurement conditions, calibrated noise, ETC, frequency resolution and decay |

## Corrections applied in this skill

### Toole additions

| File in `books/toole3rd-extras` | Edition | Capture material |
| --- | --- | --- |
| `designing_a_home_theater_part_1.docx` | Floyd E. Toole, *Designing Home Theaters and Listening Rooms: Part 1—Acoustical Perspectives*, 2017-10-15 | §§4–8: source/seat geometry, limits of RT and omnidirectional measurements, relevant reflection tests |
| `designing_home_theaters_part_2.docx` | Floyd E. Toole, *Part 2—Loudspeaker Selection, Placement, and Calibration*, 2017-10-16 | §§2–5: coverage, spatial bass consistency, prime-seat calibration, direct-sound evidence for EQ |
| `designing_home_theaters_part_3.docx` | Floyd E. Toole, *Part 3—Power Amplifiers—How Much Power is Needed?*, 2017-10-17 | §§2–6: load/rating limitations, voltage sensitivity, calibration signal conventions and output estimates |
| `sound_isolation_2017.pptx` | Floyd E. Toole, *Sound Isolation and Noise Control in Home Theaters*, 81 slides | Slides 3–23: noise, absorption versus isolation and rating limitations; 33–46, 70–78: leaks, flanking and equipment noise |

The resulting capture guidance requires relevant angular data for speaker diagnosis, a source-by-seat matrix for joint bass processing, level/SPL conventions for sensitivity and compression, and frequency-resolved noise/isolation comparisons. These are generalized engineering procedures, not claims that the supplied guides prescribe every acquisition step or matrix notation used here.

### Full-book capture evidence (*Sound Reproduction*, 3rd ed.)

Verified against the OCR working copy (`books/Toole_Sound_Reproduction_3ed.md`):

- **Rank measurement types before capturing.** Toole orders evidence as comprehensive anechoic spinorama data first, compromised in-situ direct-sound measurements second, and steady-state room curves last: a steady-state curve is "simply not all of what we hear," and a time-blind analyzer compounds the gap because binaural listeners separate directions and arrival times a single microphone cannot (Ch. 14 opening). Plan the session around the highest-ranked evidence the task allows.
- **Anechoic characterization is angular by construction.** The spinorama grew out of measurements on horizontal and vertical orbits (34 positions in the early NRCC work), post-processed into on-axis, per-angle, listening-window, and sound-power views (§5.3). A single on-axis sweep is not a spinorama and cannot stand in for one.
- **Blind comparisons need blind-grade controls.** Sighted evaluations let brand, appearance, price, and louder playback decide; Toole documents cases where "different" or louder on a showroom floor passed as better, with no equal-loudness comparison (§3.1). For preference or audibility claims, level-match, conceal identities, and randomize order — the same discipline this skill requires for before/after correction comparisons.

### Qualifications to Toole's summaries

- Voltage sensitivity at 2.83 V does not assume an 8-ohm speaker; converting it to 1 W does. Preserve voltage, impedance, analysis band, and distance explicitly.
- Calibration-noise level, ordinary listening level, maximum sine-equivalent RMS output, and instantaneous peak SPL differ. The sources' examples are not universal sweep-level settings.
- A similar RT across seats does not establish a diffuse field. A steady-state omnidirectional response is not a complete model of two-ear perception. Measure the relevant paths without treating every visible irregularity as an audible fault.
- A single shared EQ may benefit more than one seat, but cannot change relative seat-to-seat transfer functions. A spatial average alone does not provide the separate source responses required for joint optimization.
- Isolation slide 16's description of absorption as the percentage reflected is a wording error; absorption and transmission loss must also be distinguished. Room-to-room level differences do not automatically constitute standardized transmission-loss ratings.
- Do not extrapolate 2017 smartphone, immersive-format, or product examples into current equipment capabilities. Verify the user's actual measurement path and uncertainty.

### Earlier-source qualifications

- **Calibration sign:** The Acourate guides' visual 10 kHz peak check is not reliable. Confirm whether calibration numbers represent measured error or inverse correction and how the acquisition software interprets them.
- **Absolute SPL:** A smoke alarm's minimum specified output is not a calibration reference. Use a suitable calibrated reference or explicitly report relative measurements.
- **Orientation:** The REW book alternates between vertical and forward-pointing instructions. Match orientation to purpose and the available calibration; document it consistently.
- **Timing units:** REW's “300 µs … a third of a microsecond” should be 0.3 milliseconds. Treble's 1 m ≈ 0.3 ms should be approximately 2.92 ms. Time in milliseconds must be divided by 1000 before multiplying by sound speed in m/s.
- **Clock assumptions:** USB microphones are not categorically incapable of timing measurements. Separate clocks require appropriate reference/drift handling and measured repeatability. ASIO/WASAPI/device aggregation details and vendor latency claims are version-dependent and have not been carried over as universal restrictions.
- **SNR:** The books' “45 seconds gives 90 dB noise rejection” is not a universal law. Distinguish ambient SPL from the residual noise of a deconvolved/averaged estimate. Increasing mic gain alone does not improve acoustic SNR.
- **Excitation:** A log sweep cannot start at 0 Hz. Correct deconvolution removes the known sweep timing; a sinc/impulse measurement is not inherently more accurate simply because its stimulus has constant group delay. Choose based on usable bandwidth, energy, nonlinear effects, SNR and validation.
- **Averaging:** Spatial vector averaging can invent cancellations. Use documented magnitude or power averaging for area tonality. Repeated sweeps at one fixed position may be coherently averaged after timing checks. Individual multi-point IRs retain timing even though a spatial magnitude average does not.
- **Geometry:** Gate length is limited by reflected minus direct travel time, not total reflected travel time. The books give conflicting 153/307 Hz examples for similar geometry; this skill derives the interval explicitly. A nominal gate or cycle count is not evidence that reflections have been excluded.
- **Decay:** Reported T20/T30 values generally already extrapolate to 60 dB. Noise, band-limited analysis, and room non-diffuseness constrain interpretation; use the fitted range and quality indicators.
- **Room state:** For a representative room capture, retain normal furnishings. For direct-sound capture, alter geometry intentionally and document it. Removing a sofa does not by itself justify full-band speaker inversion.
- **Driver safety and phase:** Broadening a test band, bypassing DSP, or raising click/sweep level is conditional on driver capability and necessary protection. Do not adopt the books' battery tests or crossover-removal suggestions as general acquisition steps. A polarity inversion and a time delay are distinguishable broadband operations.

## File identity

SHA-256 of the sources read:

```text
f452bd6aab915f86211d41b61dfe3e15708dccb53af9bb3629a03ca47300c8c5  2. REW Full eBook.pdf
ffeacd180d224e19baf16fd1c74560ed847a766abc0cc9d28be4ea7674afd1a0  100. Acourate for Multichannel Speakers.pdf
a2501481808a807f0f698e56f9f0309aaaf12e12cbdbabf481815dd4f19cd0e5  101. Acourate for Passive Speakers and One or More Subwoofers.pdf
871932bfd9b1bf0f1cb5d5883ff19e375829aab9f018340e076438e5e60faf0e  1. MAC Talk Treble.pptx
dd2759ce716aa8ce493fb8ce563f4aa7807f8c06745a42c8af19bd470eb59978  2. MAC Talk Bass.pptx
8f8c3852534fe811af31bf064f4ad67ec0c4efe1a4173908d5ba3a39a1e518b0  acoustic_measurement_standards.pdf
0406bbc436da9ee7d2bb5fb2a26f6c2292045872daf61aed3f846befbcbbf2df  designing_a_home_theater_part_1.docx
77e2c2519c5e58838991ee53b51917b790cf488f5df173bcb178e2e899b39f8e  designing_home_theaters_part_2.docx
085f9b0e6ef2a6ddcb221e99c1f88f11bfab4c9b4abf6aa702a98102abd4e47d  designing_home_theaters_part_3.docx
2b19f91ef108e55fab4de515d83981c818fa5e94de99adf5a8ed0ef21be48989  sound_isolation_2017.pptx
```
