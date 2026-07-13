---
name: acoustics-fundamentals
description: Derive and check linear fluid-acoustic models for wave propagation, sound speed, pressure/velocity/impedance, energy and intensity, source terms, free-field spreading, room parameters, and acoustic measurements. Use for foundational acoustics, simulation setup, SPL/power conversions, RIR/RT/DRR interpretation, or deciding whether plane-wave, compact-source, far-field, diffuse-field, or linear assumptions apply.
---

# Acoustics Fundamentals

## Model from conservation laws

1. Define the equilibrium medium and acoustic perturbations.
2. State the constitutive/thermodynamic relation and boundary conditions.
3. Linearize only after checking perturbation amplitude and mean-flow/inhomogeneity scales.
4. Derive or select the wave equation, source model, and observable.
5. Keep RMS/peak and phasor conventions explicit.

Read [references/linear-acoustics.md](references/linear-acoustics.md) for scale checks, intensity/impedance restrictions, sound-speed sensitivity, and room-inference/EQ cautions.

## Essential relations

- Ideal-gas sound speed: `c = sqrt(γRT)` for specific gas constant `R`.
- Progressive plane-wave impedance: `p/u = ρ0 c`.
- SPL: `L_p = 20 log10(p_rms/p_ref)` with `p_ref = 20 µPa` in air.
- Plane-wave mean intensity: `I = p_rms²/(ρ0 c)`.
- Wavenumber: `k = ω/c`; compactness requires `ka << 1`.

Apply these only under their stated assumptions. For general harmonic fields use complex intensity and separate active from reactive components.

## Verify

Check units, wave speed, wavelength-to-geometry ratios, energy conservation/passivity, boundary conditions, and near-/far-field scaling. Record temperature/humidity when delay or phase matters. For inferred room properties, report sensor/source model, bandwidth, noise, dataset/domain limits, and uncertainty.
