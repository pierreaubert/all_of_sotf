# Router Skill Pressure Scenarios

## Scenario A: Discrete-time filter problem
**Prompt:** "I have a difference equation y[n] - 0.5y[n-1] = x[n]. I need the system function, the impulse response, and to check stability."
**Expected behavior without skill:** Agent may jump straight to z-transform but skip ROC analysis or confuse with Laplace.
**Expected behavior with skill:** Agent loads `dsp-z-transform`, writes H(z), identifies ROC |z| > 0.5, computes inverse transform, declares stable (pole inside unit circle).

## Scenario B: Continuous-time Fourier problem
**Prompt:** "Find the Fourier transform of e^{-at}u(t), a > 0, and use it to find the output of an LTI system with this input."
**Expected behavior without skill:** Agent may guess the transform pair wrong or omit convergence condition.
**Expected behavior with skill:** Agent loads `dsp-fourier-analysis`, states X(jω) = 1/(a + jω), notes convergence requires a > 0, then applies convolution theorem.

## Scenario C: Ambiguous mixed-domain prompt
**Prompt:** "I sampled a continuous cosine at 8 kHz and the reconstructed signal sounds wrong."
**Expected behavior without skill:** Agent may guess the issue without checking Nyquist criterion.
**Expected behavior with skill:** Agent first loads `dsp-fourier-analysis` (fallback), then routes to `dsp-sampling` once it identifies aliasing/reconstruction as the issue.
