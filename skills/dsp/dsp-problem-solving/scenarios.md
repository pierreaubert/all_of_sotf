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

**With-skill observations:**
- Agent decision: "I would load the `dsp-z-transform` sub-skill."
- Reasoning: "The system is described by a difference equation in discrete time ... Rule 2 of the router applies directly."
- Outcome: Correct. The agent then solved via z-transform, found H(z) = 1/(1 - 0.5z^{-1}), h[n] = (0.5)^n u[n], and declared stable.
- Compliance: Router skill routed to the expected `dsp-z-transform` sub-skill and produced a correct, complete answer.

## Scenario B: Continuous-time Fourier problem
**Prompt:** "Find the Fourier transform of e^{-at}u(t), a > 0, and use it to find the output of an LTI system with this input."
**Expected behavior without skill:** Agent may guess the transform pair wrong or omit convergence condition.
**Expected behavior with skill:** Agent loads `dsp-fourier-analysis`, states X(jω) = 1/(a + jω), notes convergence requires a > 0, then applies convolution theorem.

**Baseline observations:**
- The baseline agent produced a correct answer. It computed the Fourier transform and correctly stopped at the general output expression because the LTI system was unspecified.
- Verbatim quotes from the baseline transcript:
  - "So: \(\boxed{\mathcal{F}\{e^{-at}u(t)\}=\frac{1}{a+j\omega}}\)"
  - "the output in the frequency domain is: \(Y(j\omega)=H(j\omega)X(j\omega)=\frac{H(j\omega)}{a+j\omega}\)"
  - "The problem statement does not specify the LTI system (i.e., \(h(t)\) or \(H(j\omega)\)). Without that, we can only give the general expression above."
- It did not load a DSP skill. The baseline run was executed by the controller via the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. The implementer subagent did not have access to the `Agent` tool and initially used the Kimi CLI instead.
- Full output: [`baseline-outputs/scenario-B.md`](baseline-outputs/scenario-B.md)

**With-skill observations:**
- Agent decision: "Load `dsp-fourier-analysis`."
- Reasoning: "The problem asks for the Fourier transform of a continuous-time signal ... frequency-domain analysis ... matches routing rule 4."
- Outcome: Correct. The agent then found X(jω) = 1/(a + jω) and Y(jω) = H(jω)/(a + jω).
- Compliance: Router skill routed to the expected `dsp-fourier-analysis` sub-skill and produced a correct, complete answer.

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

**With-skill observations:**
- Agent decision: "Sub-skill to load: `dsp-sampling`"
- Reasoning: "The question explicitly mentions sampling and reconstruction, which triggers routing rule 1."
- Outcome: Correct. The agent then diagnosed aliasing and cited Nyquist frequency f_N = 4 kHz.
- Compliance: Router skill routed directly to `dsp-sampling` because the prompt explicitly mentioned sampling and reconstruction, and produced a correct aliasing diagnosis.
