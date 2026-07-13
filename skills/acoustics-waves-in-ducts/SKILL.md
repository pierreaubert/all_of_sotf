---
name: acoustics-waves-in-ducts
description: Analyze pipes, ducts, horns, transmission-line acoustic networks, and one-dimensional or modal waveguides. Use for plane-wave validity and modal cutoffs, forward/backward waves, characteristic impedance, reflection/transmission, area changes, junctions, open/closed/impedance terminations, transfer or scattering matrices, mean flow, and thermoviscous attenuation.
---

# Waves in Ducts

## Choose 1D or modal analysis

1. Define cross-section, wall condition, mean flow, frequency range, and loss model.
2. Compute the first higher-order-mode cutoff; use the 1D plane-wave model only sufficiently below it.
3. Distinguish specific impedance `ρ0 c` from volume-velocity impedance `ρ0 c/S`.
4. Fix pressure and volume-flow sign conventions at every port.

Read [references/duct-models.md](references/duct-models.md) for cutoff estimates, junction workflow, network conditioning, losses, and high-level limits.

## Solve

- Write consistent forward/backward phasors and propagation constants.
- Enforce pressure and volume-flow continuity at lossless junctions.
- Use `R = (Z_L - Z_c)/(Z_L + Z_c)` only with compatible impedance definitions.
- Include radiation impedance/end correction at open ends.
- Use mode matching near discontinuities or above cutoff; evanescent modes can matter locally even when they carry no far-field power.
- Add thermoviscous, wall, leakage, and nonlinear/orifice losses as the scale requires.

## Verify

Check rigid/open limiting cases, lossless power balance, passivity, reciprocity where applicable, and convergence with modal truncation or spatial resolution. Validate resonances and attenuation against a transfer-matrix calculation, simulation, or measurement.

## Red flags

- Never use spherical `1/r²` spreading inside a uniform lossless duct.
- Never treat an open end as exactly pressure release across all frequencies.
- Never apply a smooth-horn approximation to a sharp discontinuity without checking error.
