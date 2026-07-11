---
name: dsp-z-transform
description: Use when analyzing discrete-time LTI systems or signals with the z-transform, including system functions, ROC, and stability.
---

# Z-Transform

## Overview
Move a discrete-time problem to the z-domain, solve algebraically, then interpret the result through the region of convergence.

## When to Use
- You have a difference equation or discrete-time LTI system.
- You need the system function H(z), impulse response, or stability.
- You need to solve a discrete-time convolution problem more easily.

## Core Pattern

1. Write the difference equation in terms of x[n] and y[n].
2. Take the z-transform of both sides, using the time-shift property: y[n-k] ↔ z^{-k}Y(z).
3. Solve for the system function H(z) = Y(z)/X(z).
4. Determine the ROC from causality / stability requirements.
5. Use partial-fraction expansion to invert H(z) to h[n].
6. Verify stability: causal system is stable iff all poles are inside the unit circle (|z| < 1).

## Quick Reference

### Pairs
| Signal | Z-transform | ROC |
|--------|-------------|-----|
| δ[n] | 1 | all z |
| u[n] | 1/(1 - z^{-1}) | \|z\| > 1 |
| a^n u[n] | 1/(1 - az^{-1}) | \|z\| > \|a\| |
| -a^n u[-n-1] | 1/(1 - az^{-1}) | \|z\| < \|a\| |

### Properties
| Property | Formula |
|----------|---------|
| Time shift | x[n-k] ↔ z^{-k}X(z) |
| Convolution | x[n] * h[n] ↔ X(z)H(z) |
| Initial value | x[0] = lim_{z→∞} X(z) if x[n] causal |

## Common Mistakes / Red Flags
- Forgetting the ROC; the same algebraic H(z) can represent different sequences.
- Assuming causality without checking.
- Declaring stability without verifying poles are inside the unit circle.
- Using CT stability rules (left half-plane) for a DT system.

## Oppenheim Reference
- Chapter 10: The z-Transform
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/Signals_and_Systems_2nd_Edition_by_Oppen.md`
