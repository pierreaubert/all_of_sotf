---
name: acoustics-radiation-and-resonators
description: Analyze acoustic radiation and resonance from monopoles, dipoles, quadrupoles, pistons, spheres, apertures, open pipes, Helmholtz or duct resonators, and feedback-driven instruments or thermoacoustic systems. Use for directivity, near/far fields, radiation impedance/power, end correction, resonance frequency/Q/damping, modal coupling, or self-sustained oscillation.
---

# Radiation and Resonators

## Classify first

1. Compare source/resonator dimensions with wavelength and compute `ka`.
2. Identify source order, directivity, boundaries, observation region, and loss mechanisms.
3. Choose a Green’s-function/multipole, piston/aperture, modal, or lumped-element model.

Read [references/radiation-resonance.md](references/radiation-resonance.md) for compact-source limits, radiation models, resonance/Q distinctions, and feedback stability.

## Solve

- Separate radiating far-field terms from reactive near-field terms.
- Use full piston/aperture radiation impedance when `ka` is not small.
- For a Helmholtz resonator, use `f0 ≈ c/(2π) sqrt(S/(V L_eff))` only when the neck/cavity are acoustically compact and `L_eff` matches the termination geometry.
- Add radiation, viscous, thermal, porous, and amplitude-dependent losses before estimating Q or peak response.
- For self-oscillation, establish loop gain/phase and a nonlinear saturation mechanism; resonance alone is insufficient.

## Verify

Check dimensional scaling, low-/high-frequency limits, power conservation/passivity, directivity normalization, resonance bandwidth/decay consistency, and agreement with a sweep, impulse decay, or higher-fidelity model.

## Red flags

- Do not use monopole directivity or efficiency for a dipole-like source.
- Do not equate undamped natural frequency with the damped response peak.
- Do not treat sparse magnitude-only field reconstruction as phase-correct radiation recovery.
