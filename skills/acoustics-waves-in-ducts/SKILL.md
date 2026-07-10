---
name: acoustics-waves-in-ducts
description: Use when analyzing sound propagation in pipes, ducts, and one-dimensional waveguides, including reflection and transmission.
---

# Waves in Ducts

## Overview
Treat duct acoustics as 1D plane-wave propagation with reflection, transmission, and attenuation at boundaries and changes in cross-section.

## When to Use
- You are modeling pipes, ducts, horns, or vocal tracts.
- You need reflection/transmission coefficients at a junction.
- You need attenuation due to viscothermal boundary layers.

## Core Pattern

1. Assume plane waves if the wavelength is much larger than the duct cross-section.
2. Write forward and backward pressure waves: p(x,t) = A e^{j(ωt−kx)} + B e^{j(ωt+kx)}.
3. Apply boundary conditions (rigid wall, open end, impedance Z) to find A/B.
4. At a junction, enforce continuity of pressure and volume velocity.
5. Add thermoviscous attenuation for narrow ducts or long runs.

## Quick Reference

| Situation | Formula |
|-----------|---------|
| Plane wave | p = f(x − ct) + g(x + ct) |
| Reflection at rigid wall | R = 1 (pressure doubling at wall) |
| Reflection at open end | R ≈ −1 (low ka, unflanged) |
| Reflection coefficient from impedance | R = (Z − Z₀)/(Z + Z₀) |
| Transmission at area change | T = 2Z₂/(Z₁ + Z₂) (pressure) |
| Volume velocity | U = p S/(ρ₀c) for plane wave |

## Common Mistakes / Red Flags
- Using 3D spherical spreading formulas inside a duct.
- Assuming an open end is perfectly pressure-release without radiation correction.
- Ignoring higher-order duct modes at high frequency.

## Rienstra Reference
- Chapter 4: One dimensional acoustics
- Chapter 7: Duct acoustics
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/An_Introduction_to_Acoustics.md`
