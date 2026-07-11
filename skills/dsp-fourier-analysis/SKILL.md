---
name: dsp-fourier-analysis
description: Use when finding or using frequency-domain representations of continuous-time or discrete-time signals and systems.
---

# Fourier Analysis

## Overview
Choose the right Fourier tool, apply it, and interpret the result in the correct domain.

## When to Use
- You need a frequency representation of a signal or system.
- You are computing spectra, frequency response, or output via the convolution theorem.
- You must decide between Fourier series and Fourier transform.

## Core Pattern

1. Identify the signal domain: CT (t) or DT (n).
2. Decide periodic vs aperiodic:
   - CT periodic → CT Fourier series.
   - CT aperiodic → CT Fourier transform.
   - DT periodic → DT Fourier series.
   - DT aperiodic → DTFT.
3. Apply the transform using standard pairs and properties.
4. Use the convolution theorem for LTI outputs: Y = X · H.
5. State convergence conditions (Dirichlet for CT, absolute summability for DT).

## Quick Reference

### CT Fourier transform pairs
| Signal | Transform |
|--------|-----------|
| δ(t) | 1 |
| e^{-at}u(t), a > 0 | 1/(a + jω) |
| e^{jω₀t} | 2π δ(ω - ω₀) |
| rect(t/τ) | τ sinc(ωτ/2) |

### DTFT pairs
| Signal | Transform |
|--------|-----------|
| δ[n] | 1 |
| a^n u[n], \|a\| < 1 | 1/(1 - ae^{-jω}) |
| e^{jω₀n} | 2π δ(ω - ω₀) (periodic impulse train) |

### Key properties
| Property | CT | DT |
|----------|----|----|
| Convolution | x(t) * h(t) ↔ X(jω)H(jω) | x[n] * h[n] ↔ X(e^{jω})H(e^{jω}) |
| Modulation | x(t)e^{jω₀t} ↔ X(j(ω-ω₀)) | x[n]e^{jω₀n} ↔ X(e^{j(ω-ω₀)}) |

## Common Mistakes / Red Flags
- Using Fourier series for an aperiodic signal.
- Forgetting that DTFT is periodic in ω with period 2π.
- Ignoring convergence / ROC before applying inverse transforms.
- Confusing CT and DT transform pairs.

## Oppenheim Reference
- CT Fourier series: Chapter 3
- CT Fourier transform: Chapter 4
- DT Fourier analysis: Chapter 5, Sections 5.1–5.7
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/Signals_and_Systems_2nd_Edition_by_Oppen.md`
