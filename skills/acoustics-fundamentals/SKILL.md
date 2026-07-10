---
name: acoustics-fundamentals
description: Use when solving free-field acoustics problems involving wave propagation, speed of sound, acoustic energy, or sound sources.
---

# Acoustics Fundamentals

## Overview
Model small-amplitude sound in fluids using the linearized wave equation and interpret energy, speed, and source terms.

## When to Use
- You need the speed of sound in air, water, or an ideal gas.
- You are setting up or verifying a wave equation simulation.
- You need acoustic intensity, energy density, or source power.

## Core Pattern

1. Verify linear acoustics applies: small perturbations, no shocks, compact region.
2. Write the wave equation for the medium:
   - Uniform stagnant fluid: ∇²p − (1/c²) ∂²p/∂t² = 0.
3. Pick the speed of sound c for the medium and conditions.
4. For sources, identify monopole (mass injection), dipole (momentum), or quadrupole (Lighthill) terms.
5. Compute acoustic energy density E = (1/2)ρ₀(u² + p²/(ρ₀²c²)) and intensity I = p u.

## Quick Reference

| Quantity | Formula | Typical value |
|----------|---------|---------------|
| Speed of sound in air (ideal gas) | c = √(γRT/M) | ~343 m/s at 20 °C |
| Speed of sound in water | c ≈ 1480 m/s | depends on temp/salinity |
| Plane wave impedance | Z = ρ₀c | ~415 Pa·s/m in air |
| Acoustic intensity | I = p²/(ρ₀c) = p u | W/m² |
| Sound pressure level | L_p = 20 log₁₀(p/p_ref), p_ref = 20 µPa | dB |

## Common Mistakes / Red Flags
- Using c = 340 m/s without noting temperature.
- Confusing acoustic pressure amplitude with total pressure.
- Applying plane-wave intensity formula to spherical waves without 1/r² correction.

## Rienstra Reference
- Chapter 1: Some fluid dynamics
- Chapter 2: Wave equation, speed of sound, and acoustic energy
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/An_Introduction_to_Acoustics.md`
