# Room diagnosis and contextual targets

Sources: Treble slides 14–83, 99–170; Bass slides 17–109, 123–154, 162–196; REW §§4.1–4.11; Mellor/Hedback §§A–G; Toole Part 1 §§4–9 and Part 2 §§2–5. See [sources-and-caveats.md](sources-and-caveats.md) for attribution and corrections.

## Physical scale and geometry

Use SI units unless explicitly converting. At about 20 °C, take sound speed `c ≈ 343 m/s`:

- Wavelength: `λ = c/f`.
- Extra reflection path: `Δr = c Δt`, with time in seconds. One millisecond is about 0.343 m; one metre is about 2.92 ms.
- Rectangular rigid-room modes: `f(nx,ny,nz) = (c/2) sqrt((nx/Lx)^2 + (ny/Ly)^2 + (nz/Lz)^2)`, with nonnegative integer indices, not all zero. One nonzero index is axial, two tangential, three oblique.
- Lowest mode for that model: `c/(2 max(Lx,Ly,Lz))`. A room diagonal is not an independent longer axial dimension. Below the lowest mode a sealed room may exhibit pressure behavior; openings and compliant boundaries change it.
- Approximate Schroeder transition: `fS ≈ 2000 sqrt(T60/V)` Hz, using seconds and m³. REW's reported T20/T30 already extrapolate to 60 dB. Do not multiply the displayed T30 by two again.
- Simple front-wall SBIR estimate: `fnull ≈ c/(4d)`, where `d` is source acoustic-center-to-wall distance, not cabinet clearance. The general equal-amplitude, same-polarity reflection model has cancellation at `(2k+1)c/(2Δr)`; real reflection phase/directivity change it.

These estimates suggest experiments. Irregular rooms, openings, boundary losses, and non-monopole speakers require more appropriate models. Neither a golden ratio nor the rule of thirds guarantees a good seat.

Toole uses roughly 300–500 Hz as a practical transition region in these guides. This is not an exact substitute for a calculated Schroeder modal-overlap frequency, nor a universal EQ cutoff. Source directivity, room losses, and measurement evidence determine the useful correction bands. Reproduction concerns the modes excited between installed sources and intended listeners; a performance/recording room with movable instruments and microphones presents a different spatial problem.

## Diagnosis by controlled comparison

Keep one factor fixed while changing another:

- Move the microphone over the listening area. Strongly position-dependent structure should not drive a sharp single-seat inverse correction for every seat. Preserve broad deficits and bad seats in the report even if the average is smooth.
- Compare each source alone to sources playing together. A new crossover dip implicates summation; confirm with timing-referenced complex data, polarity/delay trials, and actual combined playback.
- Move a speaker relative to a boundary. A dip moving approximately with `1/d` supports an SBIR explanation. Multiple boundaries and modes can overlap; a persistent dip alone does not uniquely identify SBIR.
- Compare repeated sweeps and a second test level. Changing noise artifacts, clipping, thermal compression, or rattles invalidate an LTI inverse model.
- Compare direct-sound/on-axis and available off-axis measurements. One EQ applied to a speaker cannot independently reshape its directional radiation.

Where available, examine anechoic on-axis, listening-window, early-reflection and sound-power curves, plus directivity indices or equivalent polar data. Smooth on-axis sound with a directivity discontinuity presents a different problem from a resonance appearing in several radiation directions. A listening-window curve describes an angular range around a loudspeaker; it is not a spatial average of seats in a room. Speaker aim, mounting, screens, and the listeners' actual off-axis angles belong in the diagnosis.

Place main speakers for imaging and directivity, then explore sub locations for bass coverage. Reciprocity can guide a subwoofer crawl for an approximately linear, reciprocal system, but the final installed source and seat must still be measured. Boundary placement can increase output and reduce one SBIR path while changing modal excitation; assess the full result.

## Read several views of the same data

**Magnitude:** Start with sensible common axes (for example 20 Hz–20 kHz and a 50 dB vertical span), then zoom to the fault. Use 1/6 or 1/12 octave for general viewing; examine raw or 1/24 octave bass for resonances; use 1/3 octave only when comparing to a target specified at that resolution. ERB/psychoacoustic views help assess trends but are not audibility guarantees. Broad low-Q errors generally matter more than isolated narrow dips. Windowing changes the IR being analyzed; graph smoothing does not remove reflections from it.

**Impulse/step:** Preserve a common time reference. The step is the integral of the IR; an IR peak corresponds to a steep step slope, not generally to the step peak. Compare early shape and the later bass tail, but account for the system's bandwidth and phase design. A minimum-phase crossover need not resemble a linear-phase one. Similar-looking peaks do not prove good sub/main phase alignment.

**ETC:** Normalize the direct arrival consistently and inspect the first 40–50 ms. Compare L/R and investigate strong or asymmetric reflections using extra path length and geometry. Broadband ETC is spectrally blind: use octave-band ETC around 500 Hz, 1, 2, and 4 kHz when spectral balance is in doubt. First-reflection treatment is a choice involving imaging, envelopment, directivity, and frequency balance, not an automatic command to absorb every reflection.

Toole emphasizes that a microphone's comb filter does not directly predict two-ear timbre or spatial perception when the arrivals come from different directions. Floor and lateral reflections are not interchangeable, and a close rear-wall reflection can be particularly troublesome for stereo phantom images. Treat clearly troublesome echoes, coloration, or localization issues; do not optimize solely for the lowest reflection peak. A diffuser placed very close behind a listener can disrupt the phantom image. Test the actual source-to-seat geometry, not only a handclap at an arbitrary spot.

**Decay:** For bass, inspect frequency-resolved waterfall/spectrogram/decay slices with sufficient window length. Use both absolute level and peak-normalized views: the former shows delivered sound, the latter helps compare relative decay. A dip near the noise floor can create misleading normalized tails. Report the valid decay range; do not claim a 40 dB decay if only 20 dB is observable. For mid/high frequencies, compare T20/T30/Topt across bands and positions, including fit/noise quality. Topt is a useful REW estimate, not an automatic cure for invalid data or proof of a diffuse field.

**Noise:** Measure ambient sound with playback silent and calibrated SPL. Distinguish ambient noise, microphone/interface self-noise, and the effective noise in a deconvolved sweep. A longer sweep can reduce random measurement noise without quieting the room. RC, NC, and NR are distinct rating procedures, not interchangeable 1 kHz readings.

For bass, Toole prioritizes the audible resonant magnitude peak over optimizing a picturesque waterfall. Decay remains valuable for diagnosis, but compare it with magnitude and usable dynamic range. For small-room mid/high frequencies, similar RT estimates do not imply similar early-reflection spectra or directions; measure the particular paths when choosing surface treatments.

## Optional stereo listening-room benchmarks

Mellor and Hedback's 2011 white paper proposes these benchmarks for high-performance domestic stereo. They are not universal standards for every room, studio, or home theater. If adopting them, retain their measurement conditions and identify any adaptation to a house curve.

| Metric | Source proposal and conditions |
| --- | --- |
| Ambient noise | Below RC30 for existing rooms; RC20 design target for purpose-built rooms; use the full RC procedure |
| Early reflected sound | L/R ETC similar over 0–40 ms, a clear declining pattern, approximately 10 dB reduction by 40 ms; interpret with spectral balance |
| Bass magnitude | 20–250 Hz, both speakers playing together: ±10 dB at 1/24 octave and ±5 dB at 1/3 octave |
| Midrange magnitude | Each speaker separately, 250 Hz–4 kHz: ±3 dB at 1/3 octave and no greater than 3 dB L/R discrepancy |
| Midrange decay | 250 Hz–4 kHz: T60 estimates 0.2–0.5 s, T20/T30 band variation within approximately ±25% |
| Bass resonance decay | §§C text: 35–300 Hz reach −40 dB or the observable noise floor within 350 ms; below 35 Hz, 450 ms. Noise-floor truncation is not proof of a measured −40 dB decay |

Keith's talks add a −15 dB early-reflection heuristic and illustrate bass decay at −40 dB by about 300 ms at 100 Hz and 500 ms at 20 Hz. The REW book gives a 250–400 ms example at 100 Hz. Do not merge these into one supposedly exact limit; state which reference is being used.

The white paper warns that a simple peak-threshold ETC test is insufficient. It also contains construction/room-size recommendations and inconsistent volume figures. Do not turn these into mandatory renovation specifications. Similarly, select an actual applicable DIN/EBU document and edition before asserting formal compliance; the Keith documents mix EBU numbers and application contexts.

Toole Part 1 §5 instead describes about 0.3–0.5 s as typical of satisfactory furnished listening rooms and cautions against using RT as the main evaluator of a few dominant directional reflections. Retain the table as an optional benchmark from a different source, not a mandate to force every band within ±25%. Differences between these proposals should prompt a purpose-specific assessment, not increasingly aggressive treatment.

## Match treatment to the measured problem

Absorption reduces energy; diffusion redistributes it and may also absorb. Thin porous panels predominantly affect higher frequencies and can worsen a room with already-short treble decay and long bass decay. Bass treatment effectiveness depends on material flow resistivity, depth, air gap, area, placement, and resonance tuning. Neither a universal quarter-wave minimum nor a one-eighth-wave rule is a complete absorber model.

Use measured frequency-dependent absorption/scattering data where available. Pressure absorbers and porous velocity absorbers interact differently with the modal field. Active traps, tuned devices, additional subs, or placement can all be reasonable depending on the actual constraints; the talk's dismissive product judgments are not engineering exclusions.

Random-incidence absorption data from a reverberation chamber may not describe an individual oblique reflection in a small room. Examine the treatment's relevant incidence angles, thickness, mounting, and covering; decorative fabric can itself attenuate treble. Scattering can redirect energy into existing absorbers, changing the room decay without adding much absorbing material. Shallow treatments that eliminate a high-frequency handclap flutter may leave the loudspeaker's lower-frequency reflection intact.
