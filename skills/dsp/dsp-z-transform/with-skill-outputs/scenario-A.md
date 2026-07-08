# With-Skill Scenario A: System function from difference equation

**Prompt:** "Find H(z) for y[n] - (1/2)y[n-1] = x[n] and determine stability."

**Skill loaded:** `dsp-z-transform`

**Execution method:** Controller ran this via the `Agent` tool with `subagent_type: "coder"`. The system prompt included the full content of `skills/dsp/dsp-z-transform/SKILL.md` (SHA-256: `d54316dbef450934a679d296888cd8dd8e59341a0c3f3117758bf2840f41a7db`) followed by the user prompt below.

**Agent response (full):**

Following the z-transform core pattern:

## 1. Difference equation
$$y[n] - \frac{1}{2}y[n-1] = x[n]$$

## 2. Apply the z-transform
Using the time-shift property $y[n-k] \leftrightarrow z^{-k}Y(z)$:

$$Y(z) - \frac{1}{2}z^{-1}Y(z) = X(z)$$

## 3. Solve for $H(z) = \frac{Y(z)}{X(z)}$
$$Y(z)\left(1 - \frac{1}{2}z^{-1}\right) = X(z)$$

$$\boxed{H(z) = \frac{1}{1 - \frac{1}{2}z^{-1}} = \frac{z}{z - \frac{1}{2}}}$$

## 4. Region of convergence
For the standard causal impulse response $\left(\frac{1}{2}\right)^n u[n]$, the ROC is:

$$\boxed{|z| > \frac{1}{2}}$$

## 5. Inversion (impulse response)
Using the pair $a^n u[n] \leftrightarrow \frac{1}{1 - az^{-1}}$ with $a = \frac{1}{2}$:

$$\boxed{h[n] = \left(\frac{1}{2}\right)^n u[n]}$$

## 6. Stability check
The only pole is at $z = \frac{1}{2}$.

A causal discrete-time LTI system is stable iff all poles lie inside the unit circle ($|z| < 1$).

$$\left|\frac{1}{2}\right| = 0.5 < 1$$

The ROC $|z| > 0.5$ also includes the unit circle.

$$\boxed{\text{The system is stable.}}$$
