# Radiation and Resonators Pressure Scenarios

## Scenario A
**Prompt:** A Helmholtz resonator has a neck of length 20 mm and radius 8 mm, unflanged, and a cavity volume of 1.2 L. Estimate its resonance frequency in air at 20 °C. Someone argues that the neck length should be used exactly. Explain why that gives the wrong answer and quantify the correction.

**Expected with skill:**
- Use f₀ = (c/2π) √(S/(V L_eff)) with c ≈ 343 m/s, S = πa² = π(0.008)² m², V = 1.2 × 10⁻³ m³.
- Unflanged end correction: L_eff ≈ L + 0.6a = 0.020 m + 0.6 × 0.008 m = 0.0248 m.
- f₀ ≈ (343 / (2π)) √(π(0.008)² / (1.2 × 10⁻³ × 0.0248)) ≈ 141.9 Hz.
- Using the physical neck length alone ignores the radiation mass at the open end, which acts like extra length of air oscillating outside the neck. That lowers the resonance frequency compared with L_eff; here L_eff/L ≈ 1.24, so the corrected frequency is lower by about √(1/1.24) ≈ 0.90, i.e., ~10% lower.

## Subagent Response
> For air at 20 °C, c ≈ 343 m/s. Using f₀ = (c/2π)√(S/(V L_eff)) with L_eff = L + 0.6a for an unflanged neck gives L_eff = 24.8 mm and f₀ ≈ 141.9 Hz. Using the physical neck length alone gives f₀ ≈ 158.0 Hz.
>
> The exact length is wrong because air just outside the neck opening still accelerates and radiates; this radiation mass adds inertance, lowering the resonance frequency. Using the physical length only overestimates f₀ by about 16 Hz (~11%).

## Verification
**PASS** — response matches expected key points (formula, unflanged end correction, numerical f₀, explanation of radiation mass, quantified error).

