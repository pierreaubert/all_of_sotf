# Linear Acoustics and Room-Model Practice

## Governing assumptions

Decompose pressure, density, and velocity into mean plus perturbation. Linearize only when acoustic Mach number and fractional thermodynamic perturbations are small and the mean medium varies slowly enough for the chosen model. State whether the medium is lossless, homogeneous, stationary, and unbounded.

Use RMS pressure for SPL unless peak amplitude is explicitly intended. For harmonic plane waves, specific impedance is `p/u = ρ0 c`; intensity is `Re{p u*}/2` for peak phasors or `p_rms²/(ρ0 c)` for a progressive plane wave. These shortcuts do not transfer unchanged to reactive near fields or standing waves.

## Scale checks

- Compact source: characteristic dimension `a` satisfies `ka << 1`.
- Far field: distance is large relative to source size and reactive near-field scale.
- Plane wave: wavefront curvature is negligible over the region of interest.
- Geometric acoustics: wavelength is short relative to obstacle and medium-variation scales.
- Diffuse room formulas: sufficient modal overlap and statistical mixing; do not use below the room’s transition region as though individual modes vanished.

## Sound speed and propagation

For an ideal gas, `c = sqrt(γRT)` when `R` is the specific gas constant. Record temperature, humidity, and composition when phase or delay accuracy matters. Recent online-control work shows that sound-speed mismatch alone can degrade multichannel spatial control; simulation-only estimators still require measured validation (`books/2602.16416.md`).

## Room inference and equalization cautions

- Estimate RT, DRR, volume, or geometry only under a stated measurement/source/noise model.
- Phase-aware blind estimation can outperform magnitude-only features but is dataset- and architecture-dependent (`books/2303.07449.md`).
- Image-source inversion can be nearly exact for low-passed simulated shoebox RIRs with known arrays; that does not imply robustness to measured rooms, model mismatch, or arbitrary geometry (`books/2405.03385.md`).
- Report behavior at the target point and across the listening region. A single-position inverse can overfit spatially (`books/2409.10131.md`).
- Separate spectral correction from spatial/perceptual effects such as DRR (`books/2604.12439.md`).

## Primary source

Read `books/An_Introduction_to_Acoustics.md`, Chapters 1–3 for fluid assumptions, wave equations, sound speed, sources, acoustic energy, impedance, and evanescence.
