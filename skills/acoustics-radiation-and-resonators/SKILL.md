---
name: acoustics-radiation-and-resonators
description: Use when analyzing sound radiation, resonators, or self-sustained oscillations.
---

# Radiation and Resonators

## Overview
Model radiation from compact sources and resonators using Green’s functions, impedance matching, and lumped-element approximations.

## When to Use
- You need radiation from a speaker, piston, or open pipe.
- You are designing a Helmholtz resonator or estimating its damping.
- You are analyzing whistles, flutes, or other self-sustained oscillations.

## Core Pattern

1. Identify the source as monopole, dipole, or quadrupole; far-field pressure scales with 1/r.
2. For a compact source, use p(r,t) ≈ (ρ₀/4πr) ∂Q/∂t.
3. For a resonator, split volume into neck (mass) and cavity (spring): f₀ = (c/2π)√(S/(V L_eff)).
4. Include radiation resistance and viscothermal losses in the total damping.
5. For self-sustained oscillations, match acoustic feedback to the hydrodynamic instability timing.

## Quick Reference

| Quantity | Formula |
|----------|---------|
| Monopole far-field pressure | p ≈ (jωρ₀Q)/(4πr) e^{−jkr} |
| Piston radiation impedance | Z_rad ≈ ρ₀c [ (ka)²/2 + j (8ka)/(3π) ] (ka << 1) |
| Helmholtz resonance | f₀ = (c/2π) √(S/(V L_eff)) |
| Effective neck length | L_eff ≈ L + 0.6a (unflanged) or L + 0.85a (flanged) |
| Quality factor | Q = 2π f₀ E / P_diss |

## Common Mistakes / Red Flags
- Forgetting the radiation mass correction to neck length.
- Ignoring damping and predicting an infinitely sharp resonance.
- Using a simple monopole model for a dipole-like source.

## Rienstra Reference
- Chapter 3: Green’s functions, impedance, and evanescent waves
- Chapter 5: Resonators and self-sustained oscillations
- Chapter 6: Spherical waves and radiation
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/An_Introduction_to_Acoustics.md`
