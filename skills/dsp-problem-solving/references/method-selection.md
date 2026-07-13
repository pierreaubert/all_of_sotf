# Method Selection and Verification

## Classify before transforming

Record whether the signal and system are continuous-time or discrete-time, periodic or aperiodic, deterministic or stochastic, and LTI or time-varying. State the requested output and all initial/rest conditions.

| Need | Preferred representation | Required caveat |
|---|---|---|
| Direct response or short finite record | Time-domain convolution/difference equation | Check support and indexing |
| Harmonic content or steady-state response | Fourier series/transform or DTFT | Check convergence and transform convention |
| CT transients, poles, differential equations | Laplace transform | State ROC; use unilateral form for initial conditions |
| DT transients, poles, difference equations | z-transform | State ROC; use unilateral form for initial conditions |
| Sample-rate conversion | Sampling/DTFT analysis | Track physical Hz and normalized rad/sample |
| Adaptive acoustic path or room EQ | Block/frequency-domain adaptive method | Track latency, response-estimation error, and nonstationarity |

Do not route a Laplace-only task to Fourier analysis merely because no dedicated sub-skill exists. Solve it from first principles and preserve the ROC and initial-condition distinctions.

## Verification contract

1. Check units, indexing, and transform normalization.
2. Substitute the result into the original equation or compute a numerical spot check.
3. Check limiting cases, causality, BIBO stability, and real-signal conjugate symmetry where applicable.
4. For finite FFT implementations, state window, FFT length, overlap, padding, and whether the result is linear or circular convolution.
5. For learned or adaptive room methods, separate simulation, measured-RIR, and listening-test evidence. Never generalize beyond the tested room, sensor, signal, or motion distribution.

## Source map

- `books/Signals_and_Systems_2nd_Edition_by_Oppen.md`: Chapters 1–2 (signals/LTI systems), 3–7 (Fourier, filtering, sampling), 9–10 (Laplace/z-transform).
- `books/2501.16367.md`: adaptive acoustic state-space and neural Kalman-filter tradeoffs.
- `books/2606.22563.md`: closed-loop adaptive room EQ; frequency-domain losses, estimator accuracy, frame-size responsiveness/stability tradeoff.
