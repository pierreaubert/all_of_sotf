# Fourier Analysis Practice

## Conventions and representations

Declare the forward/inverse convention before using a table. Keep angular frequency `ω` (rad/s), ordinary frequency `f` (Hz), and normalized DT frequency `Ω` (rad/sample) distinct, with `ω = 2πf` and `Ω = 2πf/f_s`.

| Signal class | Representation | Key structure |
|---|---|---|
| CT periodic | Fourier series | Discrete harmonics `kω0` |
| CT aperiodic | CTFT | Generally continuous in `ω` |
| DT periodic | DT Fourier series | Finite coefficient set, periodic in index |
| DT aperiodic | DTFT | Periodic in `Ω` with period `2π` |
| Finite sampled record | DFT/FFT | Samples one period of a periodic spectrum model |

Distributional transforms are legitimate: constants, sinusoids, and periodic signals produce impulses. Do not apply ordinary-function convergence tests to them without stating the distributional interpretation.

## Finite-record workflow

1. Choose the observation interval and window based on amplitude accuracy, frequency resolution, and leakage tolerance.
2. Distinguish bin spacing `f_s/N` from true resolving power, which is governed primarily by record duration and the window main lobe.
3. Normalize coherently for amplitude, power, PSD, or energy. One-sided spectra require the appropriate interior-bin factor for real signals.
4. Use zero-padding only to interpolate the sampled spectrum; it does not add information or improve true resolution.
5. Use sufficient padding for FFT convolution (`N >= Lx + Lh - 1`) or explicitly report circular convolution.

## Sampling and systems

For ideal impulse-train sampling, spectral replicas are spaced by `ω_s`. Exact bandlimited reconstruction requires nonoverlap; practical antialias/reconstruction filters need a transition band. In multirate work, filter before decimation and after zero-insertion for interpolation.

For LTI systems, use `Y = HX` only after checking that the relevant transforms exist. Interpret magnitude and phase together; unwrap phase only across meaningful-energy regions, and compute group delay from a consistent phase branch.

## Room/acoustic data cautions

- Phase features can improve blind room-parameter estimation, but phase wrapping, synchronization, and low-energy bins make raw phase fragile (`books/2303.07449.md`).
- Magnitude-only sound-field reconstruction may support coloration/modal analysis but cannot establish a phase-correct field or 6-DoF rendering (`books/2605.10398.md`).
- Spatially averaged or distance-weighted prototype responses trade sweet-spot accuracy against area robustness; validate both (`books/2409.10131.md`).

## Primary source

Read `books/Signals_and_Systems_2nd_Edition_by_Oppen.md`, Chapters 3–7, for Fourier series, CTFT/DTFT, magnitude-phase behavior, filtering, and sampling.
