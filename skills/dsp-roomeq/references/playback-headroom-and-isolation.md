# Playback constraints: coverage, output, and noise

Use when these constraints affect a proposed correction. Sources are Toole's supplied Part 2 §§2–6, Part 3 §§2–7, and *Sound Isolation and Noise Control in Home Theaters* slides 3–23, 33–46, 62–78. The full book and the standards referenced by the sources were not consulted.

## Direct sound and installation

Check coverage at the intended seats before using EQ to compensate for an off-axis deficit. Center, surround, and elevated channels need adequate direct sound as well as the fronts. A shared brand or nominal frequency range does not establish timbral matching; compare radiation data and installation angles. Horizontal driver layouts can have narrow lobing in the seating plane; assess the actual polar response rather than assuming a center speaker covers a sofa.

Measure installation changes. A screen can attenuate and reflect high frequencies; a baffle wall can change boundary loading and enclosure diffraction. A free-standing design placed in a recess is no longer in its original acoustic loading. Screen-loss correction can be legitimate when before/after data establish the loss, but correction must still respect headroom and spatial behavior. Do not prescribe a baffle wall or cabinet modification merely to imitate a cinema.

System level/delay calibration refers to a chosen reference seat. It cannot make every listener equidistant or equally on-axis. Report the prime-seat result separately from coverage over the rest of the audience. Preserve the user's playback layout and use the applicable current format requirements if layout changes are requested; the 2017 guide's immersive-format examples are historical.

## Output and headroom

Do not infer usable playback level from amplifier watts alone. Check:

- Trustworthy voltage sensitivity and its measurement band/distance.
- Frequency-dependent loudspeaker impedance and demanding phase angles, not only nominal ohms.
- Amplifier voltage/current limits, rated load, duration, distortion criterion, and number of simultaneously driven channels.
- Loudspeaker compression, excursion, thermal limits, crossover allocation, and EQ boost.
- Actual listening distance, desired peak/average level, and available output margin.

Voltage sensitivity `S` in dB SPL at 1 m for 2.83 V does not assume the speaker is 8 ohms. It corresponds to approximately 1 W only into an 8-ohm resistor; into 4 ohms the same voltage corresponds to about 2 W. Do not silently interchange dB/2.83 V and dB/1 W.

For a first estimate, let `D` be propagation loss in dB from the sensitivity reference distance and `L` the desired level with compatible measurement definitions:

```text
ΔL = L + D − S
Vrequired = 2.83 × 10^(ΔL/20) volts RMS
Presistive ≈ Vrequired²/R
```

The last expression is a resistive-load estimate. For a sinusoid into complex impedance, current magnitude is `V/|Z|` and real power is `V² Re(1/Z)`. Reactive loads also stress an amplifier in ways the real-power number misses. Loudspeaker nonlinearity limits the validity of extrapolating small-signal sensitivity.

For a far-field point source, direct-sound loss is `20 log10(r/1 m)` (about 6 dB per doubling). Toole illustrates about 3 dB per doubling for combined steady-state direct-plus-reflected sound in typical furnished rooms. Treat this as an empirical planning estimate, not a law or a guaranteed transient/low-frequency room gain. Bracket uncertain predictions and prefer measured level-versus-distance data.

Every 3 dB of extra required level or boost approximately doubles resistive power; 6 dB requires about four times the power and twice the voltage, before compression. High-passing mains may reduce bass excursion and improve available output, but another driver or amplifier limit then dominates. Retain digital headroom independently of analog output capability.

Reference calibration is not a prescribed listening volume. The guides describe domestic examples using −30 dBFS noise at 75 dBC and cinema examples using −20 dBFS at 85 dBC. Those values depend on the defined noise signal, band, channel path, meter, and convention. Follow the actual calibration specification; do not use 75 dB as a universal sweep target. Nor should cinema X-curve equalization be transplanted into domestic playback. Do not conflate a time-weighted SPL, a sine-equivalent RMS maximum, and an instantaneous peak.

## Isolation is different from internal treatment

Absorption/scattering controls sound within the room; transmission loss controls sound passing to another space. Porous absorbers may provide little isolation. EQ cannot seal an air leak or stop structure-borne vibration.

If noise limits usable dynamics, distinguish equipment/HVAC noise, external airborne noise, and structure-borne or flanking paths. Inspect doors, windows, service penetrations, shared ducts, ceilings/floors, and mechanical connections. A high-rated wall can be undermined by a small leak or an untreated parallel path.

Use frequency-resolved evidence. STC/Rw single-number ratings do not characterize deep-bass isolation adequately; NRC does not specify deep-bass absorption; IIC addresses a different impact-transmission test. NC and related room-noise ratings do not alone describe tonality, intermittency, or information-bearing distractions. Do not estimate sound in an adjacent furnished room by subtracting a laboratory STC rating from broadband playback SPL.

Boundary mass, cavity depth, damping, and mechanical decoupling affect transmission and also the internal bass response. Adding mass for isolation can reduce useful boundary absorption, increasing resonant peaks. Re-measure after structural changes rather than assuming isolation and room damping improve together. Resilient assemblies can be mechanically shorted by fasteners or rigid connections. Use tested construction details and appropriate structural/HVAC expertise when design work is requested; this skill does not specify assemblies from a slide's illustrative STC number.
