# Acoustics Fundamentals Pressure Scenarios

## Scenario A
**Prompt:** An 80 dB SPL 1 kHz plane wave travels in air at 20 °C. Given p_ref = 20 µPa, what is the RMS acoustic pressure, the characteristic impedance of the air, and the acoustic intensity? A novice claims the intensity is p²/(ρ₀c) only if the wave is spherical. Correct them.

**Expected with skill:**
- p_rms = 20 µPa × 10^(80/20) = 0.2 Pa.
- ρ₀c ≈ 415 Pa·s/m in air at 20 °C.
- I = p_rms² / (ρ₀c) = 0.04 / 415 ≈ 9.6 × 10⁻⁵ W/m².
- Correct the novice: I = p²/(ρ₀c) = p u applies to plane waves because particle velocity is in phase with pressure and u = p/(ρ₀c). For a spherical wave, intensity falls as 1/r² and the local relationship is I(r) = p_rms(r)² / (ρ₀c), but the pressure amplitude itself scales as 1/r; you cannot plug a far-field pressure into a plane-wave formula at a different location without the 1/r correction.

## Subagent Response
> Using the provided **acoustics-fundamentals** reference:
>
> - p_rms = 0.20 Pa
> - Z = ρ₀c ≈ 413 Pa·s/m
> - I ≈ 9.7 × 10⁻⁵ W/m²
>
> The novice is wrong and has it backwards: I = p²/(ρ₀c) is exactly the plane-wave intensity formula. For a spherical wave the relationship is more complicated; in the far field it locally behaves like a plane wave and I ≈ p_rms²/(ρ₀c), with total power spread over a spherical surface.

## Verification
**PASS** — response matches expected key points (RMS pressure, impedance, intensity, and correct plane-wave vs spherical-wave distinction).

