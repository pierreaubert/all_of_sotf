# Scenario B: Continuous-time Fourier problem

## Prompt

"Find the Fourier transform of e^{-at}u(t), a > 0, and use it to find the output of an LTI system with this input."

## Baseline agent response

The agent was invoked as a `coder` subagent with no DSP skills loaded. It produced the following response.

---

The agent began by computing the Fourier transform from the definition, noting that a > 0 guarantees convergence:

"F[e^{-at}u(t)] = 1/(a + jω)"

It then applied the convolution (or multiplication) property for an LTI system:

"If the input is x(t) = e^{-at}u(t) with Fourier transform X(jω) = 1/(a + jω), and the LTI system has frequency response H(jω), then the output in the frequency domain is: Y(jω) = H(jω)X(jω) = H(jω)/(a + jω)."

Because the problem did not specify the system, the agent stopped at the general expression rather than inventing a specific impulse response:

"The problem statement does not specify the LTI system (no H(jω) or h(t) is given). Without that, we can only give the general expression Y(jω) = H(jω)/(a + jω), or equivalently y(t) = h(t) * e^{-at}u(t) in the time domain. If you provide the system, I can compute the concrete output."
