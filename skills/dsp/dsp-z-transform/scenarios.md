# Z-Transform Skill Pressure Scenarios

> **Baseline run note:** These baseline runs were performed by the controller using the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. The observations below record how a generic coding agent behaves on these z-transform problems without the `dsp-z-transform` skill loaded.

## Scenario A: System function from difference equation
**Prompt:** "Find H(z) for y[n] - (1/2)y[n-1] = x[n] and determine stability."
**Expected with skill:** Agent takes z-transform, gets H(z) = 1/(1 - (1/2)z^{-1}) = z/(z - 1/2), ROC |z| > 1/2, stable because pole at z = 1/2 is inside the unit circle.

**Baseline observations:** The baseline agent took the z-transform using the time-shift property, obtained $H(z) = 1/(1 - (1/2)z^{-1}) = z/(z - 1/2)$, assumed causality, chose ROC $|z| > 1/2$, and declared the system stable because the pole at $z = 1/2$ is inside the unit circle. Verbatim quotes:
- "H(z) = 1/(1 - (1/2)z^{-1})"
- "Multiply numerator and denominator by z to get a cleaner form: H(z) = z/(z - 1/2)"
- "The system is BIBO stable because its single pole at z = 1/2 lies inside the unit circle"

## Scenario B: Inverse z-transform
**Prompt:** "Find h[n] for H(z) = 1/(1 - (1/3)z^{-1}) with ROC |z| > 1/3."
**Expected with skill:** Agent recognizes right-sided sequence: h[n] = (1/3)^n u[n].

**Baseline observations:** The baseline agent used the standard pair $a^n u[n] \leftrightarrow 1/(1 - az^{-1})$ with ROC $|z| > |a|$, identified $a = 1/3$, and gave $h[n] = (1/3)^n u[n]$. It also correctly noted that the ROC determines the right-sided/causal sequence. Verbatim quotes:
- "A standard z-transform pair is a^n u[n] ↔ 1/(1 - a z^{-1}), ROC: |z| > |a|"
- "h[n] = (1/3)^n u[n]"
- "If the ROC were |z| < 1/3, the inverse transform would instead be the anti-causal sequence"

## Scenario C: Stability vs ROC confusion
**Prompt:** "A system has a pole at z = 2 and is causal. Is it stable?"
**Expected with skill:** Agent says causal → ROC |z| > 2, which excludes unit circle, so unstable.

**Baseline observations:** The baseline agent correctly reasoned that causality implies ROC $|z| > 2$, which excludes the unit circle, and therefore concluded the system is unstable. Verbatim quotes:
- "No — a causal system with a pole at z = 2 is unstable."
- "For a causal LTI system, the Region of Convergence (ROC) is the exterior of a circle: |z| > r_max"
- "The pole is at z = 2, so r_max = 2. Because the system is causal, the ROC is |z| > 2. This region lies entirely outside the unit circle and does not include |z| = 1."
