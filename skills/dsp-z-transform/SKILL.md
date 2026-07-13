---
name: dsp-z-transform
description: Analyze or implement discrete-time sequences and LTI systems with bilateral or unilateral z-transforms. Use for rational system functions, regions of convergence, inverse transforms, poles and zeros, causality/BIBO stability, difference equations with or without initial conditions, frequency response, block diagrams, IIR realizations, or numerical filter checks.
---

# z-Transform

## Core workflow

1. Define `X(z) = Σ x[n]z^{-n}` and state bilateral or unilateral form.
2. Derive the algebraic expression and the ROC together.
3. Infer sidedness, causality, DTFT existence, and stability from both poles and ROC.
4. Invert by a method consistent with the ROC.
5. For an LTI system under initial rest, form `H(z) = Y(z)/X(z)`; for nonzero initial state, retain unilateral shift terms.
6. Verify samples in the original recurrence and evaluate `H(e^{jΩ})` only when the unit circle belongs to the ROC.

Read [references/z-transform-practice.md](references/z-transform-practice.md) for ROC rules, initial conditions, inverse methods, and realization checks.

## Implementation workflow

Normalize the denominator, derive coefficient signs from the recurrence, choose direct/cascade/SOS/parallel form intentionally, and test impulse response, frequency response, stability margins, quantization, state scaling, and finite-value behavior. Prefer SOS for higher-order floating-point IIR filters.

## Red flags

- The same rational expression with different ROCs represents different sequences.
- “Poles inside the unit circle” does not prove stability unless causality/right-sidedness is established.
- Bilateral time shifting does not encode nonzero initial conditions.
- Pole-zero cancellation in the transfer function can hide unstable internal modes in a nonminimal realization.
