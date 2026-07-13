# Duct and Waveguide Models

## Choose the model

Use a 1D plane-wave model only below the first higher-order-mode cutoff and when cross-sectional variation is sufficiently slow or represented by explicit junctions. For a hard circular duct, the first non-plane cutoff is approximately `f_c = 1.841 c/(2πa)`; for a hard rectangular duct, derive cutoffs from the transverse modal wavenumbers. Mean flow, lining, and nonrigid walls change propagation constants and cutoffs.

Use characteristic impedance consistently:

- specific impedance for particle velocity: `Z0 = ρ0 c`;
- volume-velocity impedance for duct area `S`: `Zc = ρ0 c/S`.

Do not mix them in reflection or transfer-matrix equations.

## Boundary/junction workflow

1. Define pressure and positive volume-velocity directions at every port.
2. Write forward/backward waves with one phasor convention.
3. Enforce pressure and volume-flow continuity at lossless junctions.
4. Apply the terminal load through `R = (Z_L - Z_c)/(Z_L + Z_c)` using matching impedance definitions.
5. Include end correction/radiation impedance for open ends instead of assuming an exact pressure-release boundary.
6. Check power balance for lossless elements and passivity for lossy ones.

For networks, prefer transfer or scattering matrices with explicit reference impedances. Scattering formulations are usually better conditioned for long or evanescent sections.

## Loss and high-level limits

Thermoviscous loss is frequency-dependent and important when boundary-layer thickness is not negligible relative to hydraulic radius. Nonlinear loss and vortex shedding can dominate at high acoustic amplitude or sharp orifices. A slowly varying horn invites Webster’s equation; abrupt changes invite mode matching, not a smooth-area approximation.

## Primary source

Read `books/An_Introduction_to_Acoustics.md`, Chapter 4 for 1D characteristics, junctions, and thermoviscous damping; Chapters 7–8 for modal duct acoustics, reflection/transmission, open ends, and slowly varying ducts.
