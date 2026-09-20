---
name: dsp-recording
description: Plan, capture, and validate acoustic measurement recordings for loudspeakers and rooms. Use for calibrated microphone setup, swept-sine or impulse-response recording, moving-microphone measurements, multi-position capture, timing references, clock drift, loopback routing, or measurement-data handoff. Tool-independent measurement acquisition, not music tracking or mixing.
---

# Acoustic measurement recording

Capture data that can support the intended acoustic decision. Establish what the recording must preserve before choosing the stimulus, microphone placement, routing, or averaging method. This skill draws on Keith Wong's measurement/DSP guides and talks, Mellor/Hedback's stereo-room white paper, and Floyd Toole's supplied home-theater guides and sound-isolation slides, plus the full text of *Sound Reproduction*, third edition, read via OCR of the owner's paper-copy scans (local `books/Toole_Sound_Reproduction_3ed.md`; figure index in `books/Toole_Sound_Reproduction_3ed_figures.md`). The procedures are independent of any particular application.

## Define the capture

Determine the purpose from the user's task and available setup:

| Purpose | Required evidence |
| --- | --- |
| Room tonal balance or multi-seat EQ | Individual-source spatial magnitude data, with seat coverage and weights |
| Driver/sub timing or crossover integration | Stationary sweeps/IRs with a common timing reference, each source and relevant combinations |
| Reflections, decay, or room IR | Stationary IR capture long enough to include the decay, with frequency-dependent SNR checks |
| Speaker/driver linearization | Valid direct-sound measurement, documented geometry/window and usable frequency band |
| Ambient noise | Silent playback path, calibrated absolute SPL, stated bandwidth/weighting and averaging |

One session may need both spatial tonal measurements and stationary timing captures. Moving-microphone magnitude data cannot supply a physical phase response or room impulse response.

For upper-band correction, a smooth spatial average is insufficient evidence: obtain suitable direct-sound and angular-response data when possible. An omnidirectional microphone, even with timing analysis, does not reproduce two-ear directional perception. Do not convert every measured reflection or comb-filter feature into a presumed audible defect.

Read [capture-procedures.md](references/capture-procedures.md) for setup and the selected capture mode. Read [timing-and-routing.md](references/timing-and-routing.md) for timing, offline capture, clock drift, or a multi-channel processing chain. Consult [sources-and-caveats.md](references/sources-and-caveats.md) when a source recommendation appears contradictory or unusually absolute.

## Establish a trustworthy signal path

- Identify microphone, calibration file and orientation, interface inputs/outputs, sample rate, capture format, gain, channel mapping, stimulus band, and processing state. Preserve this metadata with the recording.
- Match calibration to the actual microphone and orientation. Distinguish frequency-response calibration from absolute SPL calibration; relative dBFS data alone is not calibrated room SPL.
- For stationary measurements, use a stable stand at a marked position. Preserve normal furnishings for room measurements; change geometry deliberately to isolate a speaker for direct-sound measurements.
- Confirm physical channel routing at low level using a stimulus safe for the addressed driver. Keep crossovers and protection required by active drivers in every path. Do not send a full-band test to an unprotected tweeter.
- Disable unintended monitoring/feedback, AGC, noise suppression, enhancement, normalization, and mixer processing. Keep intentional processing when measuring the corrected playback chain and identify it explicitly.
- Prefer a common ADC/DAC clock for precise timing. Separate devices can still be used if reference and drift behavior are measured and adequate for the task.

## Capture and quality gate

1. Start with a conservative test level and short representative recording. Check the actual output, input peaks, clipping, overload, dropouts, reference detection, and plausible response.
2. Select sufficient stimulus duration/repeats for the needed SNR and driver capability. A fixed sweep length does not guarantee a fixed noise rejection. Longer or repeated stimuli increase exposure and thermal load as well as averaging benefit.
3. Capture each accessible source separately, then the required combinations. For phase/timing tasks, keep microphone position, gain, reference source/path, and routing consistent.
   For joint multi-sub analysis, capture every independently controlled sub at every relevant seat, retaining a common timing/gain reference within each seat. Record bass routing and the complete source-by-seat matrix rather than only a combined spatial average.
4. Repeat enough to establish stability. Check frequency-dependent SNR and the timing uncertainty appropriate to the crossover band; do not discard a take merely because it looks less favorable.
5. For spatial capture, retain every individual position and a separately labeled stationary reference capture. State whether the average is magnitude, power, dB, or coherent complex averaging.
6. Inspect raw data before committing to the full session. Reacquire clipped, misrouted, corrupted, or unstable captures. Mark noise-limited frequencies rather than claiming the full nominal sweep band is valid.

## Preserve a useful handoff

Save the original recording/session and the stimulus when available, plus derived IRs or frequency responses without overwriting originals. Include:

- Source/driver and physical output channel; microphone position, orientation, and reference geometry.
- Sample rate, sample format, duration/band, gain/SPL status, calibration identity and application state.
- Timing reference, any drift correction, latency, IR time origin, windowing, averaging method, and processing-chain identity.
- Accepted/rejected take status, valid bandwidth, observed noise/overload, and repeatability limits.

Keep absolute gain and timing information needed for coherent sums. Do not independently normalize or center each exported IR when those relationships matter. Provide the raw analysis data alongside plots; choose common axes and processing for before/after comparisons.

When measuring output capability or calibration levels, distinguish voltage sensitivity, acoustic SPL, and digital level. Use the specified calibration signal and meter settings, and do not generalize one receiver's reference-noise level to sweep recordings. For noise or isolation comparisons, retain frequency-resolved data and the operating conditions; a single noise/transmission rating is not a full description of bass leakage or tonal disturbances.
