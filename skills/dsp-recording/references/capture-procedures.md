# Measurement capture procedures

Sources: REW §§1–3; Active guide §§1–6, 8–9.1; Passive guide §§1–5, 7; Treble slides 22–94; Bass slides 17–76; Mellor/Hedback §§A–F; Toole Part 1 §§4–8, Part 2 §§2–5, Part 3 §§2–6 and isolation slides 14–23. These procedures retain the underlying operations without depending on a particular software UI.

## Calibration, microphone, and level

Use a small-diaphragm omnidirectional measurement microphone with a suitable calibration. A USB mic is convenient; an analog measurement mic plus a shared-clock audio interface simplifies electrical loopback. Verify the microphone's power requirement before enabling phantom power.

- Use the individual serial-number calibration when available. Record whether values describe the microphone error or the correction to apply. Confirm the file convention with its supplier/software; a presumed 10 kHz peak is not a reliable sign test.
- For direct-sound measurements, point the microphone at the source with the appropriate on-axis calibration. For room/surround capture, a vertical mic with the corresponding 90° calibration is often practical. No orientation/calibration makes a physical microphone perfectly omnidirectional at every frequency; keep orientation repeatable and document any compromise.
- Apply calibration exactly once. If calibrating the interface, identify precisely which electrical path is included. A line-level loopback does not automatically characterize every microphone-preamp setting.
- Absolute SPL needs a suitable acoustic calibrator, a trustworthy sensitivity calibration supported by the acquisition path, or a calibrated reference meter with compatible weighting/time settings. Otherwise label results relative. Do not calibrate from a smoke alarm's nominal regulatory minimum.
- Leave enough input/output margin to avoid clipping. Increasing microphone gain may improve use of ADC range but does not improve the acoustic signal-to-ambient-noise ratio.
- Measure at a level representative of the intended operation, within equipment capability. Music volume-control position alone does not set a known sweep SPL; account for stimulus RMS/crest factor. Check another level if compression or rattles are suspected.

## Stationary sweep and room IR

1. Mark the microphone's acoustic-center position at ear height. Keep the room in its normal listening state and record door/window/HVAC conditions. Keep the operator away from the direct path where practical.
2. Select the excitation bandwidth based on the actual source and protection. Logarithmic sweeps start at a positive frequency; a log sweep cannot start at DC. Set the upper end within the acquisition/playback bandwidth rather than blindly choosing Nyquist.
3. Capture adequate pre-roll, the full excitation, any timing markers, and a post-sweep tail long enough for the intended decay analysis. Retain the known stimulus and deconvolution settings.
4. Measure individual sources with a stable timing reference when timing or summation matters. Capture L+R, sub+main, or other relevant combinations as separate labeled recordings.
5. Derive the IR using a matching inverse/deconvolution method. Inspect reference timing, direct arrival, harmonic/nonlinear contamination, late tail, and repeatability.
6. Keep the raw long IR for room analysis. Create windowed copies for a specific purpose; a short gate that isolates the speaker also removes the room decay being measured.

A logarithmic sweep spreads energy over time and can separate nonlinear distortion components during suitable deconvolution. Correctly deconvolved LTI impulse responses do not inherently acquire the sweep's frequency-dependent emission times. Distortion estimates need adequate SNR at the fundamental and harmonics and a method valid for the stimulus. A high percentage at a deep fundamental null can be misleading.

## Repetition and SNR

Repeat coherent stationary captures only if the source, microphone, gains, and clock/reference remain stable. Correct documented timing drift before coherent averaging; preserve the original takes. Under independent equal-variance noise, averaging `N` aligned repetitions improves power SNR by approximately `10 log10(N)` dB: four repeats give about 6 dB. Correlated noise, movement, drift, distortion, and thermal changes defeat that estimate.

Do not prescribe a universal sweep time or repetition count. Use a short trial, then extend duration or average until uncertainty is adequate. A long high-level stimulus is not interchangeable with a short one for driver stress. For poor bass SNR, first reduce noise and check level/position before increasing drive.

## Multiple stationary positions

Define the listening region first. Include the main position and meaningful left/right/fore/aft or additional-seat positions at representative ear heights. Keith uses 20–30 cm offsets as illustrative single-seat trials; spacing should follow the actual area, not a mandatory pattern. Record coordinates relative to a stable origin.

At each position capture each required source and keep the individual IRs. Preserve a dedicated main-position capture for phase/timing work. Equal or priority-seat weighting should be explicit.

For multiple independently controlled subs, keep a source-by-seat matrix of captures. Hold mic/reference position and gains fixed while measuring all sources for a seat; then move to the next seat. Capture the real combinations for verification too. A common EQ cannot change the relative responses between seats; these individual transfers let the processing stage optimize source placement and independent filters before shared tonal EQ. Do not independently flatten the sources during capture unless that processing is an intentional, documented part of the plant.

Different averaging definitions answer different questions. For normalized nonnegative weights `wi`:

| Average | Definition | Meaning |
| --- | --- | --- |
| Linear magnitude | `M = Σ wi |Hi|`, then `20 log10(M)` | Average pressure magnitude |
| Power/RMS | `M = sqrt(Σ wi |Hi|²)`, then `20 log10(M)` | Average squared pressure |
| dB | `L = Σ wi 20 log10(|Hi|)` | Geometric-mean magnitude |
| Complex/vector | `H = Σ wi Hi` | Coherent sum/average including phase |

Do not use a coherent spatial average as a substitute for listening-area energy response. Opposing phase at different locations can create a dip in the vector average that is absent from every individual magnitude response. Coherent averaging is useful for aligned repeated captures at the same position or a deliberately defined coherent-field quantity.

## Moving-microphone magnitude capture

Use a known broadband noise stimulus and a real-time spectral estimator appropriate for that stimulus. For pink noise, constant-fractional-octave band levels can be flat; a constant-Hz PSD is sloped. Record analyzer mode, bandwidth, averaging, and calibration so that stimulus spectrum is not mistaken for speaker tilt.

1. Define the swept spatial area and intended weighting. Keep speaker routing and gains fixed.
2. Keep the microphone away from the operator's body where possible. Use a wand/stand extension, secure the cable, and maintain a documented orientation.
3. Move slowly and cover the region evenly. Avoid wind/handling noise, cable knocks, and disproportionately long dwell at one spot.
4. Continue until the average stabilizes, then repeat the scan to assess repeatability. Increase level only as justified by SNR and equipment/listener limits.
5. Save each source's spatial magnitude with the region and estimator settings. Capture a separate stationary sweep for timing, phase, ETC, and decay.

The moving method does not record a stationary-system IR. Minimum-phase reconstruction of its magnitude is a model, not measured phase. It also conceals individual-seat problems, so retain stationary seats where worst-seat performance matters.

## Ambient noise and decay

For noise, stop the stimulus while keeping the normal room/equipment conditions of interest. Use calibrated measurement of sufficient duration to characterize steady and intermittent components. Record weighting, bandwidth, integration time, and microphone/interface noise limits. When comparing doors open/closed or HVAC states, hold calibration and estimator settings fixed. Use the full specified procedure for RC/NC/NR rather than labeling a single frequency.

Toole's isolation slides emphasize that single-number ratings can hide low-frequency and tonal problems. Add a narrowband view for hum/tones and an event/time record for intermittent disturbances where relevant. Separate projector/fan/HVAC states, external airborne sources, and structure-borne noise through controlled on/off or location comparisons. For an informal isolation comparison, keep source spectrum/level and both-room conditions consistent and report receiving-room noise limits. A room-to-room level difference is not automatically a standardized transmission-loss or STC/Rw measurement; source/receiving geometry, absorption, flanking paths and the applicable test procedure matter.

For decay, capture stationary IRs with a sufficiently long tail and observable dynamic range per frequency band. Inspect the energy-decay fit and its noise intersection. Common 60 dB extrapolated estimates use:

- EDT: fit approximately 0 to −10 dB and extrapolate.
- T20: fit approximately −5 to −25 dB and extrapolate.
- T30: fit approximately −5 to −35 dB and extrapolate.

Check the implementation's actual definitions and reported units. A displayed T30 generally already estimates a 60 dB decay time. Do not multiply it again. A theoretical 30 dB fit requires more usable range than exactly 30 dB from the initial level. For bass in small rooms, report frequency- and position-dependent modal decay rather than presuming a single diffuse-field RT60.

Similar decay estimates across positions do not prove a diffuse field or identical early-reflection spectra. When investigating treatment, compare relevant source-to-seat paths and frequency bands. A handclap at an arbitrary point can excite reflections that the installed loudspeaker hardly excites; test from the source location and listen/measure at the seats. Keep a clap-based flutter screen distinct from a calibrated speaker-response measurement.

## Direct-sound speaker/driver capture

Place the source and mic away from boundaries and use an appropriate measurement axis. Choose enough distance for the radiating elements, baffle, horn, or waveguide to combine as required. A fixed 1 m rule is not valid for every speaker. Extreme nearfield woofer/port data omit normal far-field geometry and baffle effects; do not use them as a complete speaker response without appropriate processing and corroboration.

Let `rD` be direct path length and `rR` the earliest reflected path length. The available reflection-free interval is `(rR−rD)/c`. Choose a gate ending before that reflection, allowing for window taper. The order-of-magnitude frequency resolution is `1/Twindow`; robust amplitude/phase estimation may need several cycles.

For equal source and mic height `h` above a flat floor with horizontal separation `r`, `rD = r`, `rR = sqrt(r²+(2h)²)`. At `h=r=1 m`, the extra path is 1.236 m, about 3.60 ms: the one-cycle scale is about 278 Hz. Moving the microphone farther away at the same height reduces this floor-reflection separation. Check walls, ceiling, supports, and other earlier reflectors too.

Frequency-dependent windowing uses a duration on the order of `cycles/f`; it cannot recover uncontaminated low frequencies when reflections fall within the required cycles. State the valid lower bound, and use suitable nearfield/ground-plane/outdoor methods or room measurements for lower frequencies. Those are different measurement models, not interchangeable captures.

Where speaker correction is the goal, capture or obtain on-axis and relevant off-axis responses, not just one axial curve. A formal listening-window/spinorama dataset requires its defined angular sampling and processing; a few ad hoc angles are useful diagnostics but should not be labeled as that standard dataset. Record physical source axis, mic angle, distance, gate, and angular coverage. For a multi-driver speaker, check that measurement distance permits the drivers to combine before normalizing the result to 1 m.

For mounting or screen-loss diagnosis, compare installation states with matched geometry, voltage/gain, and windowing where feasible. Distinguish new boundary loading/diffraction from screen attenuation. Do not mix an on-axis reference with an off-axis installed measurement and attribute the entire difference to the screen.

## Sensitivity, reference level, and compression

For system-level comparison, distinguish equal measured SPL from equal perceived
loudness. Toole, third edition, sections 3.5.1.5–3.5.1.6 and 14.2 (local OCR
files 72–74 and 378–383) shows why calibration signal spectrum, weighting,
playback level, and geometry matter. Record these explicitly. A channel balance
obtained with one spectrum need not remain a loudness match for another; do not
use a narrow correction band as an unexplained broadband level reference.

For bass-managed verification, capture both isolated logical inputs and their
intended simultaneous combinations through the actual exported chain. A useful
shared-bass check is identical, coherent L and R excitation at a safe known
level: independently acceptable routes can cancel when combined if their
polarities or phases conflict. Record the stimulus relationship, not just
"L+R". This is an engineering check motivated by Toole sections 8.4–8.6 (OCR
265–268), not a substitute for electrical overload tests or all-seat capture.

Toole Part 3 distinguishes voltage sensitivity from an ambiguous nominal watts-to-SPL specification. If measuring sensitivity, document input RMS voltage, acoustic reference distance, analysis frequency band, weighting, and reflection removal. A rating at 2.83 V corresponds to about 1 W only for an 8-ohm resistor; real loudspeaker impedance varies with frequency. Do not measure or connect an amplifier output using an unsuitable microphone/line input. If voltage was not safely measured, do not invent a voltage sensitivity from a volume-control setting.

For level linearity, compare otherwise identical captures at two or more safe drive levels. Retain the input level difference; normalize copies by that known difference to reveal frequency-dependent compression. Also inspect distortion, clipping, and repeatability after cool-down where thermal effects are suspected. Raising mic gain to avoid a quiet recording does not test higher speaker output. Compression can originate in the driver, amplifier, limiter, or another processing stage; an acoustic recording alone may not identify the culprit.

For system reference calibration, use the specified noise signal, bandwidth, digital level, channel route, meter weighting, and integration time. The guides' domestic −30 dBFS/75 dBC example and cinema −20 dBFS/85 dBC example are contextual conventions, not universal stimulus settings. Confirm whether internal test noise traverses EQ, bass management, and output trims in the same way as ordinary content. Separate calibration level from chosen listening level and from maximum-output tests.

Report SPL type precisely: time-weighted RMS-derived level, equivalent continuous level, and instantaneous peak are not interchangeable. Do not infer unclipped output or remaining amplifier current margin merely because a broadband sound-level meter reaches a target. Where multichannel load matters, a one-channel acoustic trial does not establish all-channels-driven output capability.
