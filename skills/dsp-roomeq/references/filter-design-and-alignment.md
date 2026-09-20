# Filter design, integration, and verification

Sources: Active Acourate §§4–11; Passive Acourate §§3–7; REW §2.1.5 and phase addendum; Bass slides 138–161; Toole Part 1 §4 and Part 2 §§3–5. The equations and qualifications below correct the simplifications identified in [sources-and-caveats.md](sources-and-caveats.md).

## Measurement-to-filter contract

Keep immutable raw captures and derived/windowed/averaged copies distinct. Each correction needs a stated input measurement, valid frequency range, spatial objective, target, processing chain, and output channel.

Use spatial magnitude or power averages to guide tonal correction across seats. Use timing-referenced complex measurements at an actual position to predict phase and summation. A spatial magnitude average has no measured spatial-average phase. Do not manufacture such a phase from a minimum-phase reconstruction and label it measured.

For joint multi-sub optimization, retain a transfer matrix `H[s,k](f)` from source `k` to seat `s`, with a common reference within each seat. Predict `Ys(f) = Σk H[s,k](f) Gk(f) Xk(f)` using the actual bass-routing relationship among input signals. Optimize the intended sources together: independently flattening each sub can defeat useful complementary responses. Track seat variation, target error, output demand, and practical delay bounds. Rectangular-room symmetric layouts are candidates, not guaranteed solutions for irregular or open-plan rooms.

If every seat response is multiplied by the same filter `C(f)`, then `Ys/Yt` is unchanged wherever defined. Shared EQ can correct a common peak but cannot reduce relative seat-to-seat variation at that frequency. Source placement or independent source processing changes the spatial response; a common final EQ addresses what remains. Inspect individual seats so that a smooth average cannot hide cancellations.

For passive speakers, treat the complete speaker as the accessible plant. Do not assume independent driver control or bypass the internal crossover. For active ways, choose safe crossover bands from driver response, distortion/output capability, and directivity; keep protection in the chain. Electrical crossover complementarity does not guarantee acoustic complementarity.

## Magnitude correction

Let `M(f)` be measured magnitude in dB and `T(f)` the selected target. A bounded correction can start from `T(f) − M(f)`, with smoothing, regularization, gain limits, and a taper to neutral correction outside the usable band.

- Attenuate repeatable resonant peaks before contemplating boosts.
- Do not attempt to recover a deep cancellation or missing bandwidth through large gain. Boosting a source usually boosts its canceling reflection too, consuming excursion and headroom.
- Where moderate boost is justified, bound it using output capability, noise, filter peak gain, and all relevant seats. Report the compromise rather than silently lowering the whole target until a plot looks flat.
- Avoid dense high-Q treble EQ fitted to a listening-position comb filter. Correct stable speaker errors using valid direct-sound data and consider broad tonal adjustment separately.
- Make the corrected/uncorrected transition continuous in magnitude and inspect resulting phase and time behavior. Avoid independent per-channel normalization that destroys the intended L/R or driver gain relationship.

Distinguish a narrow cancellation from a broad repeatable energy deficit: the latter can sometimes justify low-Q compensation within output limits, even if boundary interaction contributed to it. A blanket prohibition on all boosts is as unhelpful as inverting every notch. For the upper band, evidence from valid direct-sound/angular measurements or a measured installation change is required before imposing detailed correction. Keep optional recording/preference tone controls separate from the measured calibration.

## Phase models and implementation

With Fourier convention `H(f) = ∫ h(t) exp(−j2πft) dt`, a delay `τ` contributes `−2πfτ` radians. Group delay is `−dφ/dω`, or `−(1/(2π))dφ/df`, after appropriate phase unwrapping.

Minimum-phase means a stable causal system has a stable causal inverse within the relevant mathematical model. Practical speaker inverses still need band limits and regularization. Neither all loudspeakers nor all room responses are minimum-phase. Compare measured phase to a minimum-phase reconstruction after handling bulk delay; assess excess group delay, SNR, and window sensitivity. Ordinary minimum-phase filters can have strongly frequency-dependent group delay.

- IIR filters may be minimum-phase, all-pass, or non-minimum-phase. A biquad is not necessarily a PEQ section.
- FIR filters can be minimum-, linear-, mixed-, or maximum-phase. Exact linear phase corresponds to constant group delay in bands where phase is defined.
- A finite symmetric FIR of length `N` has delay `(N−1)/(2 Fs)` seconds. At 48 kHz, 65,536 taps imply about 0.683 s of linear-phase delay. `Fs/N ≈ 0.732 Hz` is a frequency-grid scale, not a guarantee of realizable correction quality. Tap count, design bandwidth, transition width, and window all matter.
- Reverse-all-pass/excess-phase correction requires finite approximation and sufficient delay for causal playback. Negative sample rotation in an editor does not allow physical anticipation. Avoid circular wraparound and truncation of meaningful tails.
- Pre-ringing depends on bandwidth, slope, gain mismatch, alignment, and phase correction. There is no universal “under 20 ms is inaudible” rule. Inspect its level, spectrum, and duration, and listen with suitable transients.

## Sub/main and multi-source alignment

1. Capture each source separately with a stable common reference, through the intended crossover and processing. Also measure combinations. Keep gain and microphone position fixed.
2. Estimate gross delay from geometry and known processing. `Δt = Δr/c`; 1.3 m is about 3.79 ms. Geometry does not include sub DSP, driver/crossover group delay, or convolver latency.
3. Use repeated IR measurements to reject timing mistakes and gross offsets. Low-passed sub IRs are broad and small; choosing a peak alone can select the wrong alignment.
4. Inspect relative phase and predicted acoustic summation across the crossover overlap. For a delayed sub, `Hsum(f) = Hmain(f) + g Hsub(f) exp(−j2πfτ)`, with signed `g` representing gain/polarity. For multiple subs, sum all routed sources.
5. Search plausible polarity/delay/gain choices. Resolve phase-cycle ambiguity using gross timing and behavior over a band: at 50 Hz, delays separated by 20 ms have identical phase at that one frequency.
6. If one delay cannot reconcile different phase slopes, consider crossover frequency/slope, placement, or a bounded all-pass/phase adjustment. Do not assume an all-pass can fix every spatial cancellation.
7. Implement advances as reduced existing delay or added common latency, preserving alignment of other channels. Keep an explicit delay ledger in seconds and samples.
8. Verify the actual combined response at the MLP and other intended seats. Retain any trade-off between temporal alignment and crossover summation; a single-frequency match is insufficient.

For normalized equal-amplitude sources, in-phase coherent summation is +6 dB relative to either alone; the prediction requires phase and gain information. Summing dB magnitudes or adding spatial averages is not a coherent prediction.

Sine-wave convolution can visualize the relative phase of two IRs near a chosen crossover frequency. It is a diagnostic view of the same information: check more than one frequency and keep the actual crossover response in the final verification. Do not extend a woofer into an unsafe band merely to make its IR resemble a sub's.

## Gain and export

Evaluate the entire routed transfer, including stereo-to-mono summation, crossover overlap, EQ, and resampling. A per-filter 0 dB maximum does not guarantee that the summed playback chain cannot clip. Reserve input attenuation and verify output peaks/true peaks where applicable. Check amplifier and driver limits as well as digital full scale.

Large digital attenuation can reduce signal-to-analog-noise ratio; it does not simply discard one source-file bit for every 6 dB in a floating-point pipeline. Prefer sensible analog gain structure when accessible, then use documented digital trims. A constant gain alone does not introduce pre-ringing.

Export the required sample rate, sample format, tap length, channel order, polarity, delays, and normalization. Confirm whether the host applies automatic gain normalization or sample-rate conversion. Rebuilding a filter at another rate must preserve delay in seconds and the acoustic response, not blindly reuse sample counts.

## Acceptance evidence

Use an uncorrected/reference capture that retains essential protection and the same routing. Compare against corrected playback with matched measurement settings and reported level normalization. Check:

- Target error and individual-seat/worst-seat behavior, not only the mean.
- Each source and combined crossover response, L/R consistency, and plausible relative delays.
- IR/step shape, pre-ringing, decay under both absolute and normalized views, and valid SNR.
- Digital/output margin, latency, stable playback, and correct physical channel routing.

EQ can reduce excitation and audible ringing of a mode. It does not by itself change the room's physical absorption or modal decay constant everywhere. A DBA or other spatial cancellation system needs geometry and multi-position validation; a delayed front-source “VBA” is not automatically equivalent to a rear absorbing array.

Likewise, multi-source room control acts on the signals reproduced by those sources. It does not necessarily damp an unrelated acoustic source after playback is paused. Validate the controlled playback system using its own excitation; use independent-source room-decay tests only when assessing actual passive damping or an explicitly active absorber. Do not claim that output-based cancellation has physically treated the entire room.

For listening validation, compare several familiar recordings, match levels, and use blind switching where practical. A single loudspeaker playing mono is useful for exposing coloration without stereo/spatial distractions. Distinguish that test from sending identical mono to L+R, which tests the phantom image and interspeaker summation. Listener preference, adaptation, and the program itself remain factors; a visually ideal step response is not an independent proof of superior sound.
