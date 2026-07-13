---
name: dsp-problem-solving
description: Analyze signals-and-systems and DSP problems, select time-domain, Fourier, Laplace, z-domain, sampling, or adaptive-filter methods, and verify implementations. Use for CT/DT signals, LTI systems, convolution, difference/differential equations, transforms, sampling and multirate processing, frequency response, stability, or adaptive acoustic processing when the right representation is not yet clear.
---

# DSP Problem Solving

## Classify the problem

1. State CT versus DT, periodic versus aperiodic, deterministic versus stochastic, and LTI versus time-varying.
2. Record the requested quantity, transform convention, units, support, initial conditions, and causality assumptions.
3. Read [references/method-selection.md](references/method-selection.md) when choosing a representation, handling sampling, or validating adaptive/room-processing claims.

## Route deliberately

- Load `dsp-fourier-analysis` for spectra, harmonic representations, frequency response, filtering, sampling, DFT/FFT, and convolution by multiplication.
- Load `dsp-z-transform` for DT transients, rational system functions, pole-zero/ROC reasoning, difference equations, stability, and realizations.
- For CT differential equations or transients, use Laplace analysis directly: state bilateral/unilateral form, ROC, initial conditions, and stability criteria. Do not disguise it as Fourier analysis merely because there is no Laplace sub-skill.
- Stay in the time domain when direct convolution, recursion, or state-space analysis is clearer and cheaper.
- For stochastic/adaptive tasks, define the estimator, objective, stationarity assumptions, update schedule, and convergence evidence before selecting an algorithm.

## Produce a checkable answer

Include the governing equation, assumptions, derivation or algorithm, units/normalization, and at least one verification. For code, also report latency, complexity, boundary behavior, numerical precision, and test vectors.

## Reject common shortcuts

- Never omit the ROC from Laplace/z-transform conclusions.
- Never infer LTI stability from pole locations without the system class and ROC/causality assumptions.
- Never confuse DFT bin spacing with resolving power or zero-padding with added information.
- Never claim room-EQ robustness from one point, one simulated room, or one spectral metric.
