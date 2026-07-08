# Router Skill Pressure Scenarios

## Scenario A: Discrete-time filter problem
**Prompt:** "I have a difference equation y[n] - 0.5y[n-1] = x[n]. I need the system function, the impulse response, and to check stability."
**Expected behavior without skill:** Agent may jump straight to z-transform but skip ROC analysis or confuse with Laplace.
**Expected behavior with skill:** Agent loads `dsp-z-transform`, writes H(z), identifies ROC |z| > 0.5, computes inverse transform, declares stable (pole inside unit circle).

**Baseline observations:**
- The baseline agent produced a correct answer. It solved the problem directly via the z-transform and explicitly stated the region of convergence.
- Verbatim quotes from the baseline transcript:
  - "Take the z-transform of both sides, using the delay property ... H(z) = Y(z)/X(z) = 1/(1 - 0.5z^{-1})"
  - "The pole is at z = 0.5. For a causal system, the region of convergence (ROC) is the exterior of the pole circle: |z| > 0.5"
  - "h[n] = (0.5)^n u[n]"
  - "The system is BIBO stable ... the pole of H(z) is at z = 0.5, which lies inside the unit circle"
- It did not load a DSP skill. The baseline run was executed by the controller via the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. The implementer subagent did not have access to the `Agent` tool and initially used the Kimi CLI instead.
- Full output: [`baseline-outputs/scenario-A.md`](baseline-outputs/scenario-A.md)

## Scenario B: Continuous-time Fourier problem
**Prompt:** "Find the Fourier transform of e^{-at}u(t), a > 0, and use it to find the output of an LTI system with this input."
**Expected behavior without skill:** Agent may guess the transform pair wrong or omit convergence condition.
**Expected behavior with skill:** Agent loads `dsp-fourier-analysis`, states X(jω) = 1/(a + jω), notes convergence requires a > 0, then applies convolution theorem.

**Baseline observations:**
- The baseline agent produced a correct answer. It computed the Fourier transform and correctly stopped at the general output expression because the LTI system was unspecified.
- Verbatim quotes from the baseline transcript:
  - "F[e^{-at}u(t)] = 1/(a + jω)"
  - "the output in the frequency domain is: Y(jω) = H(jω)X(jω) = H(jω)/(a + jω)"
  - "The problem statement does not specify the LTI system ... Without that, we can only give the general expression"
- It did not load a DSP skill. The baseline run was executed by the controller via the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. The implementer subagent did not have access to the `Agent` tool and initially used the Kimi CLI instead.
- Full output: [`baseline-outputs/scenario-B.md`](baseline-outputs/scenario-B.md)

## Scenario C: Ambiguous mixed-domain prompt
**Prompt:** "I sampled a continuous cosine at 8 kHz and the reconstructed signal sounds wrong."
**Expected behavior without skill:** Agent may guess the issue without checking Nyquist criterion.
**Expected behavior with skill:** Agent first loads `dsp-fourier-analysis` (fallback), then routes to `dsp-sampling` once it identifies aliasing/reconstruction as the issue.

**Baseline observations:**
- The baseline agent produced a correct answer. It identified aliasing as the likely cause and grounded the diagnosis in the Nyquist criterion.
- Verbatim quotes from the baseline transcript:
  - "The most likely explanation is aliasing"
  - "f_N = f_s/2 = 8000/2 = 4000 Hz"
  - "The Nyquist–Shannon sampling theorem says a continuous signal must contain no energy above f_s/2"
  - "If f0 >= 4000 Hz: the sample values are indistinguishable from those of a lower-frequency cosine"
- It did not load a DSP skill. The baseline run was executed by the controller via the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. The implementer subagent did not have access to the `Agent` tool and initially used the Kimi CLI instead.
- Full output: [`baseline-outputs/scenario-C.md`](baseline-outputs/scenario-C.md)
