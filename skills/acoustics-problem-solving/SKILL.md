---
name: acoustics-problem-solving
description: Analyze physical and room-acoustics problems and select a free-field, duct/waveguide, radiation, resonator, modal, geometric, or statistical model. Use for wave propagation, impedance, sources, reflection/transmission, room impulse responses, room parameters, sound-field control, or room equalization when assumptions and scale determine the right acoustics sub-skill.
---

# Acoustics Problem Solving

## Establish the physical regime

1. Define geometry, medium, boundaries, source/receiver, frequency/amplitude range, mean flow, losses, and requested observable.
2. Compare wavelength with source, obstacle, duct, and room dimensions; compute `ka` and relevant cutoff/transition scales.
3. State linearity, homogeneity, stationarity, far-/near-field, plane-wave, compactness, and diffuse-field assumptions.

## Route by mechanism

- Load `acoustics-fundamentals` for governing equations, sound speed, energy/intensity, impedance, free-field propagation, sources, room parameters, or model-validity checks.
- Load `acoustics-waves-in-ducts` for 1D waves, pipes, horns, modal cutoffs, junctions, terminations, transfer/scattering matrices, or thermoviscous duct losses.
- Load `acoustics-radiation-and-resonators` for multipoles, pistons/apertures, radiation impedance/directivity, Helmholtz/modal resonators, or self-sustained oscillation.
- Combine skills explicitly when a duct termination radiates, a resonator couples to a room, or an inverse room problem mixes propagation and DSP.

## Evidence and verification

Check dimensions, passivity/power balance, limiting cases, and at least one numerical or measured comparison. Separate simulated-model recovery, measured-RIR performance, and perceptual evidence. For room EQ, evaluate target-position accuracy, spatial robustness, time behavior, and audible artifacts; do not report a single smoothed magnitude score as complete validation.

## Red flags

- Do not use plane-wave intensity in a reactive near field.
- Do not use diffuse/statistical room formulas below their validity range.
- Do not assume a shoebox/image-source inverse generalizes to measured arbitrary rooms.
- Do not equate spectral correction with corrected DRR, distance, or spatial impression.
