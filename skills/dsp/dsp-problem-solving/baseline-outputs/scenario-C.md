# Scenario C: Ambiguous mixed-domain prompt

## Prompt

"I sampled a continuous cosine at 8 kHz and the reconstructed signal sounds wrong."

## Baseline agent response

The agent was invoked as a `coder` subagent with no DSP skills loaded. It produced the following response.

---

"The most likely explanation is aliasing."

The agent explained the Nyquist limit for the given sample rate:

"f_N = f_s/2 = 8000/2 = 4000 Hz"

and cited the sampling theorem:

"The Nyquist–Shannon sampling theorem says a continuous signal must contain no energy above f_s/2 in order to be perfectly reconstructed from its samples."

Because the cosine frequency was not provided, the agent gave conditional alias-frequency examples:

"If f0 >= 4000 Hz: the sample values are indistinguishable from those of a lower-frequency cosine. For example, a 5 kHz cosine sampled at 8 kHz will alias to 3 kHz; a 7 kHz cosine will alias to 1 kHz; an 8 kHz cosine will alias to DC."

The response also recommended practical fixes (raise the sample rate, lower the cosine frequency, or add an anti-aliasing filter before sampling) and noted that reconstruction artifacts could also come from missing or inadequate anti-imaging filtering.
