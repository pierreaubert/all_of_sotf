# Fourier Analysis Skill Pressure Scenarios

**Baseline method:** The following baseline observations were collected by the controller using the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. These records capture how a coding agent behaves on Fourier-analysis problems without the `dsp-fourier-analysis` skill loaded.

## Scenario A: Choose Fourier series vs transform
**Prompt:** "Find the frequency representation of x(t) = cos(2πt) + cos(4πt) defined for all t."
**Expected with skill:** Agent recognizes the signal is aperiodic over (-∞, ∞) and uses Fourier transform, not series.

**Baseline observations:** The agent recognized the signal as periodic with fundamental frequency 1 Hz and derived the exponential Fourier-series coefficients. It also supplied the continuous-time Fourier transform as a sum of Dirac impulses.

- "Both frequencies are integer multiples of 1 Hz, so x(t) is periodic with fundamental frequency f0 = 1 Hz"
- "This is already the exponential Fourier series ... with coefficients: a1 = a-1 = 1/2, a2 = a-2 = 1/2"
- "Since the signal is periodic, its CTFT is a sum of Dirac impulses"

## Scenario B: Apply convolution theorem
**Prompt:** "An LTI system has impulse response h(t) = e^{-t}u(t) and input x(t) = e^{-2t}u(t). Find the output in the frequency domain."
**Expected with skill:** Agent computes Y(jω) = X(jω)H(jω) = 1/[(2+jω)(1+jω)] and checks convergence.

**Baseline observations:** The agent applied the convolution theorem, computed the individual transforms, multiplied them, and also provided a partial-fraction decomposition and the time-domain output.

- "For a continuous-time LTI system, convolution in time becomes multiplication in the frequency domain: Y(jω) = H(jω)X(jω)"
- "H(jω) = 1/(1+jω)"
- "X(jω) = 1/(2+jω)"
- "Y(jω) = 1/[(1+jω)(2+jω)]"

## Scenario C: DT Fourier confusion
**Prompt:** "Find the Fourier transform of x[n] = (1/2)^n u[n]."
**Expected with skill:** Agent uses DTFT, not CT Fourier transform, and states X(e^{jω}) = 1/(1 - (1/2)e^{-jω}).

**Baseline observations:** The agent correctly identified the signal as discrete-time and used the DTFT, deriving the transform with the region of convergence that includes the unit circle.

- "For the discrete-time signal x[n] = (1/2)^n u[n] the discrete-time Fourier transform (DTFT) is defined as ..."
- "X(e^{jω}) = 1/(1 - (1/2)e^{-jω})"
