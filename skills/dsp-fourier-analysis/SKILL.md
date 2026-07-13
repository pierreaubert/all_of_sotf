---
name: dsp-fourier-analysis
description: Derive, interpret, or implement Fourier-series, CTFT, DTFT, DFT/FFT, spectral, frequency-response, convolution, filtering, sampling, and multirate analyses for continuous- or discrete-time signals. Use for spectra, windowing/leakage, PSD or amplitude normalization, phase/group delay, aliasing, FFT convolution, or frequency-domain acoustic features.
---

# Fourier Analysis

## Establish the representation

1. Identify CT/DT and periodic/aperiodic structure.
2. Choose CT/DT Fourier series, CTFT, DTFT, or DFT/FFT accordingly.
3. Declare forward/inverse normalization and distinguish `f` (Hz), `ω` (rad/s), and normalized `Ω` (rad/sample).
4. State whether generalized functions are required and whether the transform exists in the ordinary, energy, power, or distributional sense.

Read [references/fourier-practice.md](references/fourier-practice.md) for finite-record FFT work, sampling, convolution, or room/acoustic data.

## Solve and interpret

- Use properties only after matching the declared convention.
- For LTI systems, compute `Y = HX`, then inspect magnitude, phase, delay, causality, and realizability—not magnitude alone.
- For real signals, verify conjugate symmetry.
- For sampled data, account for window coherent gain/noise bandwidth, one- versus two-sided scaling, leakage, record duration, and aliasing.
- For FFT convolution, distinguish linear from circular convolution and pad to at least `Lx + Lh - 1`.

## Verify

Check Parseval/energy or power where applicable, reconstruct selected samples, compare against direct convolution, and test a limiting or known transform pair. Report window, sample rate, FFT size, overlap, padding, and output units for code or measurements.

## Red flags

- DTFT frequency is `2π`-periodic; a single complex exponential corresponds to a periodic impulse train in frequency.
- Zero-padding interpolates a spectrum but does not improve true resolution.
- Raw phase is unreliable at near-zero magnitude and under unknown synchronization.
- A magnitude-only sound-field estimate is not a complete complex acoustic field.
