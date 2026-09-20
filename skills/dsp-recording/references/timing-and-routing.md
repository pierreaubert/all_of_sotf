# Timing references, routing, and reproducibility

Sources: REW §§1.2–1.3, 2.1.1, 2.1.5, 3.2; Active guide §§1–2, 6, 8, 10.3–10.4; Passive guide §§1, 5, 7; Toole Part 2 §§3–4 and Part 3 §5. Application-specific routing examples are generalized here.

## Draw the actual path

Represent the measurement as:

```text
known stimulus -> optional router/convolver -> DAC channel -> amplifier/protection -> source
                                                                               |
                                                                            room
                                                                               |
capture data <- ADC/input channel <- microphone/preamp <-------------------------+

timing reference: electrical return OR a fixed acoustic reference source/path
```

Identify the tap point of an electrical reference. A reference before the convolver measures the convolver's latency as part of the system; a reference after it may exclude that latency. Neither is automatically wrong, but all compared captures must use a consistent definition.

When measuring a corrected system, the excitation must pass through the actual processing being verified. When measuring a baseline, bypass optional correction while retaining driver protection and the routing needed for safe operation. Do not replace the measured processing chain with a simulation and call the result a verification recording.

Confirm every physical output at low level. Mute unused sources during individual captures. Distinguish muting a driver from muting the reference needed to acquire the recording. Check that a stereo-to-mono route, channel duplication, automatic gain feature, or active sub crossover has not changed between runs.

Distinguish a source channel from a physical output: one program channel may drive several subs, and a sub feed may combine redirected main-channel bass with a separate LFE signal. Preserve those gains, band limits, and routing identities in metadata. Do not assume LFE and redirected bass use identical gain conventions. A single-speaker mono test examines that speaker; identical mono sent to L+R examines two-source summation and the phantom image. Label them differently.

## Electrical and acoustic references

**Electrical loopback:** Route a known output or designated marker to a suitable input, with compatible signal levels. A common-clock interface generally provides reproducible timing. Do not connect speaker-level outputs directly to an ordinary line/mic input. Ensure monitoring does not route the return back into itself or into the loudspeakers.

**Acoustic reference:** Use a fixed source capable of reproducing the reference marker, with an unobstructed and repeatable path to the microphone. A low-passed sub may not reproduce a high-frequency chirp. Keep reference routing, gain, processing, and position unchanged across the sources being compared.

An acoustic time reference includes its own propagation and processing delay. Zero relative delay between two speakers means equal measured arrival time, not necessarily equal geometric distance. Do not “center” a mic by equalizing arrivals unless the two paths have comparable processing and transducer behavior. Moving the microphone changes reference travel time too.

Record whether the software removes device latency, uses an estimated delay, centers the IR automatically, or retains raw timing. If individual IRs are separately recentered, preserve their original offsets so coherent sums and delay estimates can be reconstructed.

Level/delay calibration is tied to the reference seat; verify other seats as separate outcomes. For multi-seat capture, preserve a common timing reference among all sources at each seat. Cross-seat acoustic-reference travel changes must be accounted for before any operation that truly requires absolute cross-seat phase; a spatial power average does not require such phase alignment.

## Clock drift and repeatability

Nominally equal sample rates do not prove synchronized ADC and DAC clocks. Separate devices can accumulate timing drift over a sweep; software aggregation alone does not eliminate it. Common clocking, verified asynchronous resampling, or explicit drift estimation may be appropriate.

With start/end markers of known separation `Tnom`, measure `Trec = (n2−n1)/Fnom` in the capture. The ratio `ρ = Trec/Tnom` estimates duration scaling, and `10^6(ρ−1)` is the corresponding approximate drift in ppm. Define the resampler's convention explicitly: to map the captured marker interval to nominal time, the output interval in samples at the same nominal sample rate should be divided by `ρ`. Some APIs express the reciprocal ratio. Verify corrected marker spacing and a repeated sweep; do not blindly apply the same correction twice.

Use more markers or fit over repeats when detection uncertainty is significant. Markers must be detectable through the actual source band and not confused with reflections. Preserve raw samples and the estimated correction factor.

Set timing tolerances from the task:

- Sample interval: `1/Fs`; at 48 kHz this is about 20.83 µs.
- Acoustic distance equivalent: `c Δt`; one 48 kHz sample is about 7.15 mm at 343 m/s.
- Phase error: `Δφdeg = 360 f Δt`; 0.5 ms is 18° at 100 Hz but 180° at 1 kHz.
- A 50 ppm drift over 20 seconds is 1 ms, large enough to matter for many phase measurements.

Fractional-delay estimation is possible; one sample is not a universal lower bound on delay estimates. Choose uncertainty appropriate to bandwidth and SNR. Keith's example timing spreads are examples, not acceptance tolerances for every system.

## Subwoofer timing capture

Capture a stable reference and the sub at the same microphone position used for the main. Low-frequency IRs are broad and small, and the bass noise floor often rises just where source output drops. Repeat the measurement before trusting an automated peak/onset estimate.

A deliberately delayed broadband reference can help visually separate the arrivals. If used, record the added delay and remove it from the calculation and final configuration. Do not mistake an editing offset for a physical path delay.

Preserve the intended sub/main crossovers in the data handed to an integration process. Impulse peaks, step peaks, and phase at a crossover are different quantities. A nice-looking alignment of peaks is not proof of constructive acoustic summation. Deliver individual complex responses plus the measured combination so the processing stage can assess phase over the overlap band.

If temporarily altering a crossover for a diagnostic capture, remain within driver capability, label the change, restore the final filter, and recapture the real configuration. Do not silently use diagnostic data as the final plant response.

## Offline recording

Offline measurement is suitable when excitation must be played by another device or through a playback-only chain:

1. Save the exact known stimulus with reference markers when supported. Record its sample rate, channel order, length, amplitude, and generation settings.
2. Play it through the intended chain with normalization, time stretching, and unintended processing disabled. Document intentional processing and unavoidable resampling.
3. Record the microphone and any reference channel with adequate pre-roll/post-roll. Preserve an unprocessed lossless original.
4. Identify the stimulus and markers, check rate mismatch/drift, then use the matching analysis/deconvolution procedure.
5. Verify arrival times, channel identity, bandwidth and repeatability before accepting the recording.

Do not assume an arbitrary recorded sweep can be analyzed using a merely similar generated sweep. A mismatch in sweep law, duration, rate, or gain handling can corrupt the derived response.

## Handoff record

Use a readable metadata file or equivalent session fields. Include what was actually measured; unknown values should remain unknown rather than being filled with defaults.

```text
session / date / room state:
capture purpose and source(s):
source -> physical output -> amplifier/driver:
microphone model/serial and calibration file/convention:
mic x/y/z, orientation, source/reference geometry:
stimulus identity, band, duration, amplitude, repeats:
capture/playback sample rates and formats:
input gain / output trims / absolute SPL calibration status:
processing chain and required protection:
timing reference and tap point / original IR offset:
clock correction, marker fit, timing uncertainty:
analysis window, smoothing and averaging definition:
valid frequency band / SNR / clipping or dropout status:
raw files / derived files / accepted and rejected take reasons:
```

Keep whole-session gain changes, per-source changes, and display-only normalization distinct. A plot shifted for readability must not become an undocumented gain change in exported data.
