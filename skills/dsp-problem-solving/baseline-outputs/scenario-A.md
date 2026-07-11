# Baseline Scenario A: Discrete-time filter problem

**Prompt:** "I have a difference equation y[n] - 0.5y[n-1] = x[n]. I need the system function, the impulse response, and to check stability."

**Execution method:** Controller ran this via the `Agent` tool with `subagent_type: "coder"` and a plain system prompt that did not load or reference any DSP skill.

**Baseline response (full):**

For the difference equation

\[
y[n] - 0.5\,y[n-1] = x[n]
\]

we assume a causal LTI system (initial rest, so \(y[n]=0\) for \(n<0\) when \(x[n]=0\)).

## 1. System function \(H(z)\)

Take the \(z\)-transform of both sides, using the delay property

\[
\mathcal{Z}\{y[n-1]\} = z^{-1}Y(z).
\]

\[
Y(z) - 0.5z^{-1}Y(z) = X(z)
\]

\[
Y(z)\left(1 - 0.5z^{-1}\right) = X(z)
\]

\[
H(z) = \frac{Y(z)}{X(z)} = \frac{1}{1 - 0.5z^{-1}}
\]

Multiply numerator and denominator by \(z\) to get a rational form:

\[
H(z) = \frac{z}{z - 0.5}
\]

The pole is at \(z = 0.5\). For a causal system, the region of convergence (ROC) is the exterior of the pole circle:

\[
|z| > 0.5
\]

## 2. Impulse response \(h[n]\)

The standard pair is

\[
a^n u[n] \xleftrightarrow{\mathcal{Z}} \frac{1}{1 - az^{-1}}, \quad |z| > |a|
\]

with \(a = 0.5\). Therefore,

\[
h[n] = (0.5)^n u[n]
\]

where \(u[n]\) is the unit-step sequence. So explicitly,

\[
h[n] = \begin{cases}
(0.5)^n, & n \ge 0 \\
0, & n < 0
\end{cases}
\]

## 3. Stability check

A discrete-time LTI system is BIBO stable if its impulse response is absolutely summable:

\[
\sum_{n=-\infty}^{\infty} |h[n]| < \infty
\]

Here,

\[
\sum_{n=-\infty}^{\infty} |h[n]|
= \sum_{n=0}^{\infty} |0.5|^n
= \sum_{n=0}^{\infty} (0.5)^n
= \frac{1}{1 - 0.5}
= 2
\]

Since the sum is finite, the system is **BIBO stable**.

Equivalently, the pole of \(H(z)\) is at \(z = 0.5\), which lies inside the unit circle (\(|0.5| < 1\)), and the ROC \(|z| > 0.5\) includes the unit circle — both confirm stability.

## Summary

- **System function:** \(\displaystyle H(z) = \frac{1}{1 - 0.5z^{-1}} = \frac{z}{z - 0.5},\quad |z| > 0.5\)
- **Impulse response:** \(\displaystyle h[n] = (0.5)^n u[n]\)
- **Stability:** The system is **stable**, because \(\sum |h[n]| = 2 < \infty\) and the pole is inside the unit circle.
