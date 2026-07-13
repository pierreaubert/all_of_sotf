# z-Transform Practice

## Bilateral analysis

Use `X(z) = Σ x[n]z^{-n}` and always report the ROC. The algebraic expression alone does not identify the sequence.

For rational transforms:

- The ROC contains no poles and is a connected annulus.
- A right-sided sequence has an ROC outside its outermost active pole.
- A left-sided sequence has an ROC inside its innermost active pole.
- A two-sided sequence has an ROC between poles.
- The DTFT exists when the unit circle lies in the ROC.
- A rational LTI system is causal when its impulse response is right-sided; for a causal rational system the ROC is outside the outermost pole.
- BIBO stability requires the unit circle in the ROC. “All poles inside the unit circle” is sufficient only after causality is established.

Pole-zero cancellation must be handled before declaring the effective poles, but hidden unstable modes can remain relevant in nonminimal internal realizations.

## Inversion choices

Choose among inspection/standard pairs, partial fractions, power-series expansion, and the inverse contour integral. Attach the ROC before selecting a right- or left-sided pair. Verify a few sequence samples by direct summation or by the original difference equation.

## Difference equations and initial conditions

Under initial rest, transform the LCCDE and form `H(z) = Y(z)/X(z)`. For nonzero initial conditions, use the unilateral z-transform or explicitly include boundary terms; the bilateral time-shift rule alone silently drops initial-state contributions.

After deriving a realization:

1. Normalize the denominator leading coefficient.
2. Check sign conventions against the original recurrence.
3. Compare direct, cascade/SOS, and parallel forms for numerical conditioning.
4. Use SOS for higher-order floating-point IIR filters and verify coefficient quantization, state scaling, overflow, and limit cycles.
5. Confirm frequency response by evaluating `H(z)` on the unit circle only when it lies in the ROC.

## Primary source

Read `books/Signals_and_Systems_2nd_Edition_by_Oppen.md`, Chapter 10, especially Sections 10.1–10.3 (definition, ROC, inversion), 10.7 (causality/stability/LCCDEs), and 10.9 (unilateral transform).
