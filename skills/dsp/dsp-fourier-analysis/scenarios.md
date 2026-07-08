# Fourier Analysis Skill Pressure Scenarios

## Scenario A: Choose Fourier series vs transform
**Prompt:** "Find the frequency representation of x(t) = cos(2πt) + cos(4πt) defined for all t."
**Expected with skill:** Agent recognizes the signal is aperiodic over (-∞, ∞) and uses Fourier transform, not series.

## Scenario B: Apply convolution theorem
**Prompt:** "An LTI system has impulse response h(t) = e^{-t}u(t) and input x(t) = e^{-2t}u(t). Find the output in the frequency domain."
**Expected with skill:** Agent computes Y(jω) = X(jω)H(jω) = 1/[(2+jω)(1+jω)] and checks convergence.

## Scenario C: DT Fourier confusion
**Prompt:** "Find the Fourier transform of x[n] = (1/2)^n u[n]."
**Expected with skill:** Agent uses DTFT, not CT Fourier transform, and states X(e^{jω}) = 1/(1 - (1/2)e^{-jω}).
