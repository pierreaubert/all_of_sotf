# Scenario A: Discrete-time filter problem

## Prompt

"I have a difference equation y[n] - 0.5y[n-1] = x[n]. I need the system function, the impulse response, and to check stability."

## Baseline agent response

The agent was invoked as a `coder` subagent with no DSP skills loaded. It produced the following response.

---

"Take the z-transform of both sides, using the delay property. With zero initial rest, the difference equation becomes:

Y(z) - 0.5z^{-1}Y(z) = X(z)

Therefore the system function is

H(z) = Y(z)/X(z) = 1/(1 - 0.5z^{-1})"

"The pole is at z = 0.5. For a causal system, the region of convergence (ROC) is the exterior of the pole circle: |z| > 0.5."

Inverting H(z) within this ROC gives the causal impulse response:

"h[n] = (0.5)^n u[n]"

For stability, the agent checked that the pole lies inside the unit circle and that the impulse response is absolutely summable:

"The system is BIBO stable. To verify, note that the pole of H(z) is at z = 0.5, which lies inside the unit circle, and sum_{n=-inf}^{inf} |h[n]| = sum_{n=0}^{inf} (0.5)^n = 1/(1-0.5) = 2 < infinity."
