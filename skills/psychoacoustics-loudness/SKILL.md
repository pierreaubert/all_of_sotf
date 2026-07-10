---
name: psychoacoustics-loudness
description: Use when calculating or estimating loudness, loudness level, or designing loudness meters.
---

# Loudness

## Overview
Estimate the perceived loudness of a sound by converting level and spectrum into specific loudness across critical bands and summing.

## When to Use
- You need a loudness estimate for a sound or audio file.
- You are implementing a loudness meter (e.g., ISO 532-1 / Zwicker model).
- You need to compare loudness of sounds with different spectra.

## Core Pattern

1. Measure or compute the 1/3-octave or FFT-based sound pressure level per critical band.
2. Convert each band level to specific loudness N' (sone/Bark), accounting for threshold in quiet.
3. Sum specific loudness over all audible Bark bands: N = Σ N' Δz.
4. For time-varying sounds, apply temporal integration (attack/release time constants).
5. Convert to loudness level in phon if needed: equal-loudness contours at 1 kHz.

## Quick Reference

| Quantity | Unit | Note |
|----------|------|------|
| Loudness | sone | Perceived magnitude; doubles every ~10 phon |
| Loudness level | phon | Matched level of a 1 kHz tone |
| Specific loudness | sone/Bark | Loudness density per critical band |
| 1 sone | 40 phon at 1 kHz | Reference point |
| Doubling loudness | +10 phon | Approximate rule of thumb |

## Common Mistakes / Red Flags
- Using A-weighted SPL as a proxy for loudness.
- Ignoring spectral distribution and critical bands.
- Forgetting temporal integration for time-varying signals.

## Zwicker Reference
- Chapter 8: Loudness
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/Psycho_Acoustics-Zwicker_Fastl.md`
