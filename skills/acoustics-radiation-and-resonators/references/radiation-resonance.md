# Radiation and Resonance Models

## Radiation hierarchy

Classify source order and compactness before using a far-field law. Monopole, dipole, and quadrupole efficiencies have different low-`ka` scaling and directivity. Separate near-field reactive terms from radiated far-field terms, and state whether boundaries are handled with images, a tailored Green’s function, or a radiation impedance.

For a baffled piston, do not use the small-`ka` impedance approximation near or above `ka ≈ 1`; use the full radiation impedance/directivity model. For open pipes and apertures, keep the flange geometry and the definition of end correction explicit.

## Resonator workflow

1. Establish a modal or lumped model from the geometry.
2. For a Helmholtz model, require neck dimensions and cavity dimensions small enough relative to wavelength; use an effective neck length appropriate to both terminations.
3. Include radiation, viscous, thermal, porous, and nonlinear losses as applicable.
4. Distinguish undamped natural frequency, damped resonance peak, and antiresonance.
5. Estimate bandwidth/Q from the complete impedance or energy balance, then verify against a sweep or decay.

Self-sustained oscillation requires loop gain and phase conditions plus a saturation mechanism. Apply Rayleigh’s criterion to thermoacoustics and a stability analysis to reed/jet feedback; a resonance frequency alone does not prove oscillation.

## Inverse/spatial-acoustic cautions

Early-reflection recovery from Ambisonics depends on array order, source count, noise, model order, and direction extraction; recovered reduced RIRs are not full late-reverberation models (`books/2305.03558.md`). Sparse sound-field magnitude estimates do not recover phase and should not be treated as complete radiation fields (`books/2605.10398.md`).

## Primary source

Read `books/An_Introduction_to_Acoustics.md`, Chapters 5–6 for resonators, stability, spherical waves, multipoles, compact-body radiation, and open-pipe radiation.
