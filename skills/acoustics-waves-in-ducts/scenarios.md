# Waves in Ducts Pressure Scenarios

## Scenario A
**Prompt:** A 250 Hz plane wave in a circular duct (diameter 5 cm) hits a rigid end closure. What is the pressure reflection coefficient, and what is the pressure amplitude at the wall relative to the incident amplitude? Explain why a narrow duct is necessary for this 1D treatment.

**Expected with skill:**
- Rigid wall boundary condition gives u = 0, so pressure reflection coefficient R = 1.
- At the wall p_total = p_incident + p_reflected = 2 p_incident; pressure doubles (standing-wave pressure maximum).
- The 1D plane-wave assumption requires wavelength >> duct cross-section. At 250 Hz, λ = c/f ≈ 343/250 ≈ 1.37 m, which is much larger than 5 cm, so higher-order modes are cut off and only the plane wave propagates.

## Subagent Response
> For a rigid end closure, R = +1, so the reflected pressure wave has the same amplitude and phase as the incident wave. At the wall p_wall = p_i + p_r = 2p_i, so the pressure amplitude doubles (+6 dB).
>
> The 1D plane-wave treatment is valid only when the wavelength is much larger than the duct cross-section. For the 5 cm diameter duct at 250 Hz, ka ≈ 0.115 ≪ 1, and the first higher-order mode cuts on around 4.0 kHz, so only the plane wave propagates.

## Verification
**PASS** — response matches expected key points (R = +1, pressure doubling, narrow-duct justification via ka and cut-on frequency).

