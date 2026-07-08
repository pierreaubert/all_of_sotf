# Router Skill Pressure Scenarios

## Scenario A: Discrete-time filter problem
**Prompt:** "I have a difference equation y[n] - 0.5y[n-1] = x[n]. I need the system function, the impulse response, and to check stability."
**Expected behavior without skill:** Agent may jump straight to z-transform but skip ROC analysis or confuse with Laplace.
**Expected behavior with skill:** Agent loads `dsp-z-transform`, writes H(z), identifies ROC |z| > 0.5, computes inverse transform, declares stable (pole inside unit circle).

**Baseline observations:**
- The baseline agent solved the problem directly and correctly via the z-transform, yielding H(z)=1/(1-0.5z^{-1}) and h[n]=(0.5)^n u[n], and declared BIBO stability.
- It did not load a DSP skill; its internal reasoning noted that the user's "do not load any DSP skill" instruction took precedence.
- It did not explicitly state the ROC, though it implicitly relied on the causal pair |z|>|a| to obtain h[n].
- No Laplace confusion appeared.

## Scenario B: Continuous-time Fourier problem
**Prompt:** "Find the Fourier transform of e^{-at}u(t), a > 0, and use it to find the output of an LTI system with this input."
**Expected behavior without skill:** Agent may guess the transform pair wrong or omit convergence condition.
**Expected behavior with skill:** Agent loads `dsp-fourier-analysis`, states X(jω) = 1/(a + jω), notes convergence requires a > 0, then applies convolution theorem.

**Baseline observations:**
- The baseline agent computed X(jω)=1/(a+jω) correctly and explicitly used a>0 for convergence.
- It treated the LTI system as unspecified, giving the general output Y(jω)=H(jω)/(a+jω) and noting a concrete answer requires the system's frequency/impulse response.
- It did not load a DSP skill and rationalized that the user instruction overrode any skill invocation.

## Scenario C: Ambiguous mixed-domain prompt
**Prompt:** "I sampled a continuous cosine at 8 kHz and the reconstructed signal sounds wrong."
**Expected behavior without skill:** Agent may guess the issue without checking Nyquist criterion.
**Expected behavior with skill:** Agent first loads `dsp-fourier-analysis` (fallback), then routes to `dsp-sampling` once it identifies aliasing/reconstruction as the issue.

**Baseline observations:**
- The baseline agent correctly identified aliasing as the likely cause and cited the Nyquist frequency F_s/2=4 kHz, giving alias examples (5 kHz → 3 kHz, etc.).
- It noted the cosine frequency is missing but, because of auto mode, chose to answer conditionally rather than ask.
- It considered whether a systematic-debugging skill might apply, then concluded it was not applicable to a conceptual non-code question.
- It did not load any DSP skill.
