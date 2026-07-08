# With-Skill Scenario B: Inverse z-transform

**Prompt:** "Find h[n] for H(z) = 1/(1 - (1/3)z^{-1}) with ROC |z| > 1/3."

**Skill loaded:** `dsp-z-transform`

**Execution method:** Controller ran this via the `Agent` tool with `subagent_type: "coder"`. The system prompt included the full content of `skills/dsp/dsp-z-transform/SKILL.md` (SHA-256: `d54316dbef450934a679d296888cd8dd8e59341a0c3f3117758bf2840f41a7db`) followed by the user prompt below.

**Agent response (full):**

Following the z-transform skill's core pattern:

**1. Difference equation**

From
\[
H(z)=\frac{Y(z)}{X(z)}=\frac{1}{1-\frac13 z^{-1}}
\]
cross-multiply:
\[
Y(z)\left(1-\frac13 z^{-1}\right)=X(z)
\]
\[
y[n]-\frac13 y[n-1]=x[n]
\]

**2. Take the z-transform**

The equation is already in the z-domain. Using the time-shift property \(y[n-1]\leftrightarrow z^{-1}Y(z)\) confirms the same \(H(z)\).

**3. System function**

\[
H(z)=\frac{1}{1-\frac13 z^{-1}}
\]

**4. Region of convergence**

Given ROC is \(|z|>\frac13\): this is the exterior of a circle, so the impulse response is **right-sided / causal**.

**5. Inverse z-transform**

From the standard pair:

\[
a^n u[n]\;\leftrightarrow\;\frac{1}{1-az^{-1}},\qquad |z|>|a|
\]

Here \(a=\frac13\), so:

\[
\boxed{h[n]=\left(\frac13\right)^n u[n]}
\]

**6. Stability check**

The pole is at \(z=\frac13\). Since \(|\frac13|<1\), the pole lies inside the unit circle, and because the system is causal (ROC \(|z|>\frac13\)), it is **BIBO stable**.
