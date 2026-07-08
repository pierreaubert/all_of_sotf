# Fourier Analysis Skill Pressure Scenarios

**Baseline method:** The following baseline observations were collected by the controller using the `Agent` tool with `subagent_type: "coder"` and a plain prompt that did not reference any DSP skill. These records capture how a coding agent behaves on Fourier-analysis problems without the `dsp-fourier-analysis` skill loaded.

## Scenario A: Choose Fourier series vs transform
**Prompt:** "Find the frequency representation of x(t) = cos(2πt) + cos(4πt) defined for all t."
**Expected with skill:** Agent recognizes the signal is periodic (fundamental frequency 1 Hz) and uses the exponential Fourier series; it may also state the CTFT as Dirac impulses at the harmonic frequencies.

**Baseline observations:** The agent recognized the signal as periodic with fundamental frequency 1 Hz and derived the exponential Fourier-series coefficients. It also supplied the continuous-time Fourier transform as a sum of Dirac impulses.

- "Both frequencies are integer multiples of 1 Hz, so x(t) is periodic with fundamental frequency f0 = 1 Hz"
- "This is already the exponential Fourier series ... with coefficients: a1 = a-1 = 1/2, a2 = a-2 = 1/2"
- "Since the signal is periodic, its CTFT is a sum of Dirac impulses"

**With-skill observations:** The agent followed the core pattern: it identified the domain as continuous-time, noted the signal is periodic with fundamental period \(T_0 = 1\) and fundamental angular frequency \(\omega_0 = 2\pi\), and chose the CT Fourier series. It produced the coefficients \(a_1 = a_{-1} = a_2 = a_{-2} = 1/2\), and also stated the CTFT as impulses at \(\pm 2\pi\) and \(\pm 4\pi\). Outcome: correct.

- "Domain: CT"
- "Periodicity: periodic with T0 = 1, ω0 = 2π"
- "Tool choice: CT Fourier series"
- "a_1 = a_{-1} = a_2 = a_{-2} = 1/2"
- "Also gave CTFT as impulses at ±2π, ±4π"

## Scenario B: Apply convolution theorem
**Prompt:** "An LTI system has impulse response h(t) = e^{-t}u(t) and input x(t) = e^{-2t}u(t). Find the output in the frequency domain."
**Expected with skill:** Agent computes Y(jω) = X(jω)H(jω) = 1/[(2+jω)(1+jω)] and checks convergence.

**Baseline observations:** The agent applied the convolution theorem, computed the individual transforms, multiplied them, and also provided a partial-fraction decomposition and the time-domain output.

- "For a continuous-time LTI system, convolution in time becomes multiplication in the frequency domain: Y(jω) = H(jω)X(jω)"
- "H(jω) = 1/(1+jω)"
- "X(jω) = 1/(2+jω)"
- "Y(jω) = 1/[(1+jω)(2+jω)]"

**With-skill observations:** The agent followed the core pattern: it identified the domain as continuous-time and the aperiodic nature of the signals, selected the CT Fourier transform, applied the known transform pairs \(H(j\omega) = 1/(1+j\omega)\) and \(X(j\omega) = 1/(2+j\omega)\), and used the convolution theorem to write \(Y(j\omega) = 1/[(1+j\omega)(2+j\omega)]\). It also stated the convergence conditions. Outcome: correct.

- "Domain: CT"
- "Periodicity: aperiodic → CT Fourier transform"
- "Applied pairs: H(jω) = 1/(1+jω), X(jω) = 1/(2+jω)"
- "Used convolution theorem: Y(jω) = 1/[(1+jω)(2+jω)]"
- "Stated convergence conditions"

## Scenario C: DT Fourier confusion
**Prompt:** "Find the Fourier transform of x[n] = (1/2)^n u[n]."
**Expected with skill:** Agent uses DTFT, not CT Fourier transform, and states X(e^{jω}) = 1/(1 - (1/2)e^{-jω}).

**Baseline observations:** The agent correctly identified the signal as discrete-time and used the DTFT, deriving the transform with the region of convergence that includes the unit circle.

- "For the discrete-time signal x[n] = (1/2)^n u[n] the discrete-time Fourier transform (DTFT) is defined as ..."
- "X(e^{jω}) = 1/(1 - (1/2)e^{-jω})"

**With-skill observations:** The agent followed the core pattern: it identified the domain as discrete-time, recognized the signal as aperiodic and therefore chose the DTFT, and derived \(X(e^{j\omega}) = 1/(1 - (1/2)e^{-j\omega})\). It also stated convergence and the \(2\pi\)-periodicity of the DTFT. Outcome: correct.

- "Domain: DT"
- "Periodicity: aperiodic → DTFT"
- "Applied transform: X(e^{jω}) = 1/(1 - (1/2)e^{-jω})"
- "Stated convergence / periodicity"
