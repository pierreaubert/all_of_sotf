---
name: dsp-roomeq
description: Diagnose and correct loudspeaker-room playback systems from acoustic measurements. Use for room EQ, target curves, speaker/subwoofer integration, crossover timing and phase, FIR/IIR correction, or comparing measured correction results. Tool-independent guidance for room processing rather than measurement recording or music production.
---

# Room processing from measurements

Turn measurements into a correction that improves the intended listening area. Separate speaker response, room response, and measurement artifacts before choosing a filter. This skill distills Keith Wong's measurement/DSP guides and talks, Mellor and Hedback's stereo-room white paper, and Floyd Toole's supplied three-part home-theater guide and sound-isolation slides, plus the full text of *Sound Reproduction*, third edition, read via OCR of the owner's paper-copy scans (local `books/Toole_Sound_Reproduction_3ed.md`; figure index in `books/Toole_Sound_Reproduction_3ed_figures.md`). Source claims and technical corrections are documented in [sources-and-caveats.md](references/sources-and-caveats.md).

## Establish the correction problem

Use available context to establish:

- System topology: passive speakers, independently driven active ways, subs, bass routing, accessible gains/delays, existing crossovers and protection.
- Listening purpose and area: one seat, several seats, stereo music, or multichannel playback; desired tonal balance and practical placement limits.
- Measurement provenance: individual sources and combined playback, microphone positions/orientation/calibration, timing reference, sample rate, level, processing state, raw IRs and spatial magnitude data.
- Implementation limits: available filter types/taps, sample rates, output mapping, headroom, latency, and maximum practical correction band.

Missing phase or timing data does not prevent a magnitude-only diagnosis. It does prevent reliable phase correction or coherent prediction of source summation. State that boundary and request only the measurements needed to resolve it. Do not infer measurements from illustrative curves in the source books.

## Choose the right evidence

Read [diagnosis-and-targets.md](references/diagnosis-and-targets.md) when interpreting frequency response, ETC, decay, noise, or spatial variability.

1. Check capture quality before treating an anomaly as real: calibration, clipping, noise, routing, repeatability, and consistency of before/after settings.
2. Compare individual speakers/subs, their actual combination, and several listening positions. Retain individual seats alongside any average.
3. Separate frequency regimes. Estimate the modal transition from room volume and a credible decay estimate; treat it as a region, not a sharp universal cutoff.
4. For bass, identify persistent peaks, cancellations, and crossover summation errors. For higher frequencies, use direct-sound and off-axis evidence to distinguish speaker tonal errors from reflections. A steady-state spatial average does not establish which correction will preserve the direct sound.
5. Compare like measurements: same smoothing, frequency/time limits, reference level, windowing, and normalization. Use fine bass resolution as well as a perceptual trend view.

## Choose an intervention

For target selection, multi-sub objectives, or claims about correction quality,
read [Toole third-edition decision rules](references/toole-third-edition.md).
They distinguish a predicted room curve from a justified inverse-EQ target,
spatial consistency from output efficiency, and reduced playback ringing from
changed passive room acoustics. For shared bass, verify correlated-channel
playback as well as each input separately.

| Evidence | Useful next action |
| --- | --- |
| Repeatable bass peak across seats | Bounded attenuation; check decay and remaining headroom |
| Deep dip that moves with listener/source position | Placement, routing, or another source; avoid aggressive inverse boost |
| Dip appears when sources play together | Check polarity, gain, crossover phase, and delay |
| Stable loudspeaker tonal error in valid direct-sound data | Bounded speaker correction within the measured usable band |
| Treble combing changes with tiny microphone movements | Placement, directivity/toe-in, or treatment; avoid narrow room inverse filters |
| Spectrally uneven reflections or decay | Diagnose geometry and treatment bandwidth before adding absorption |
| Apparent long decay at the measurement noise floor | Improve or limit the measurement; do not optimize the artifact |

Prefer measured placement trials when they can resolve a cancellation that EQ cannot. Subs can provide independent placement and additional bass sources; their count and position depend on the room and listening area. For multiple seats, first reduce response variation through source placement and joint sub gain/delay/filter choices, then apply shared EQ to the remaining common response. A shared filter cannot remove relative seat-to-seat response differences. Do not impose a fixed number of subs or a universal requirement to replace existing hardware.

Treat reflections as directional, spectral, and temporal events. A smoother ETC or lower RT is not automatically an audible improvement. Good off-axis radiation can make lateral reflections beneficial; use measured bandwidth, listening purpose, and controlled comparisons to decide whether to retain, absorb, or scatter them.

## Design and verify

Read [filter-design-and-alignment.md](references/filter-design-and-alignment.md) before calculating EQ, crossover integration, delays, or phase correction. Express operations in terms of measurements, transfer functions, filters, and signal routing; adapt them to the user's chosen implementation.

- Keep speaker linearization and room correction conceptually separate. Validate the reflection-free bandwidth of speaker measurements; furniture removal alone does not make an in-room capture anechoic.
- Use the user's target. Otherwise choose a restrained target consistent with the speaker's usable response, directivity, listening distance, and available output. A flat anechoic target and a flat listening-position target are different decisions.
- Preserve a measured calibration baseline separately from optional preference or program-dependent tone/tilt settings. Do not retune the room to compensate for one unusually bright or bass-heavy recording. Do not import the cinema X-curve as a domestic playback target.
- Specify correction limits, gain/boost limits, transition behavior, and latency. Smoothly return to neutral correction outside the chosen band; neutral magnitude need not mean zero system delay.
- Complete driver/crossover processing before final alignment. Recheck alignment whenever processing or routing changes. For subs, assess phase and acoustic summation throughout the crossover overlap, not just impulse peaks.
- Preserve necessary crossover, excursion, limiter, and tweeter protection in every measurement and playback configuration.
- Treat test convolution as prediction. Verify through the actual convolver, DAC channels, crossovers, amplifiers, and loudspeakers at the original positions and additional seats.
- Inspect level-matched magnitude, combined response, timing, pre-ringing, decay, and output margin. A lower absolute tail after EQ is not by itself proof that physical room damping improved.

Read [playback-headroom-and-isolation.md](references/playback-headroom-and-isolation.md) when output capability, noise leakage, HVAC, mounting, or multichannel coverage limits the proposed correction. These are separate design constraints; room EQ cannot repair sound isolation or a speaker's unsuitable coverage pattern.

For a completed analysis, report the diagnosed cause and evidence, proposed/applied changes, filter and routing details needed to reproduce them, measured validation, and unresolved limits. Use listening comparisons at matched levels to assess whether the result serves the user's preference.
