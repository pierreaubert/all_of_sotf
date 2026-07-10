---
name: psychoacoustics-pitch-timbre-roughness
description: Use when analyzing pitch, timbre, roughness, fluctuation strength, sharpness, or subjective duration.
---

# Pitch, Timbre, and Roughness

## Overview
Map spectral and temporal signal properties to the corresponding perceptual attributes: pitch, timbre, roughness, fluctuation, sharpness, and subjective duration.

## When to Use
- You need to estimate pitch or pitch salience of a tone or complex sound.
- You are analyzing timbre, dissonance, or sensory pleasantness.
- You need roughness, fluctuation strength, or sharpness metrics.

## Core Pattern

1. Identify the attribute:
   - Pitch → spectral periodicity or fundamental frequency.
   - Timbre → spectral envelope and temporal envelope (everything besides pitch/loudness).
   - Roughness → rapid amplitude or frequency modulation (~20–200 Hz).
   - Fluctuation strength → slower modulation (~0.5–20 Hz).
   - Sharpness → high-frequency energy concentration.
2. Choose the appropriate model (e.g., virtual pitch, Terhardt model; roughness model; DIN 45692 sharpness).
3. Compute the feature from the excitation pattern or spectrogram.
4. Report units where defined (e.g., vacil for fluctuation, asper for roughness, acum for sharpness).

## Quick Reference

| Attribute | Typical model / cue | Unit |
|-----------|---------------------|------|
| Pure tone pitch | Matches fundamental frequency | mel / Hz |
| Virtual pitch | Terhardt / autocorrelation of resolved harmonics | Hz |
| Roughness | Modulation depth × frequency separation | asper |
| Fluctuation strength | Slow modulation depth and frequency | vacil |
| Sharpness | Weighted centroid of specific loudness | acum |
| Subjective duration | Temporal integration ~100–200 ms | — |

## Common Mistakes / Red Flags
- Estimating pitch from spectral peak alone for missing-fundamental sounds.
- Confusing roughness (fast modulation) with fluctuation strength (slow modulation).
- Treating timbre as a single number; it is multidimensional.

## Zwicker Reference
- Chapter 5: Pitch and pitch strength
- Chapter 9: Sharpness and sensory pleasantness
- Chapter 10: Fluctuation strength
- Chapter 11: Roughness
- Chapter 12: Subjective duration
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/Psycho_Acoustics-Zwicker_Fastl.md`
