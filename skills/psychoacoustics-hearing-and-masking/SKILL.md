---
name: psychoacoustics-hearing-and-masking
description: Use when analyzing hearing thresholds, masking effects, or peripheral auditory processing.
---

# Hearing and Masking

## Overview
Predict audibility and masking using the hearing area, critical bands, and psychoacoustical tuning curves.

## When to Use
- You need the threshold in quiet for a frequency.
- You need to predict whether a tone is masked by noise or another tone.
- You are designing a masking model or audio codec psychoacoustic model.

## Core Pattern

1. Identify the signal level and frequency of the target and masker.
2. Convert frequencies to critical-band rate (Bark scale): z = 13 arctan(0.00076 f) + 3.5 arctan((f/7500)²).
3. Determine the masked threshold from the masker level and the excitation pattern.
4. Check if the target level exceeds the masked threshold; if not, it is inaudible.
5. Account for temporal effects: premasking, postmasking, and overshoot.

## Quick Reference

| Quantity | Formula / Rule |
|----------|----------------|
| Hearing range | 20 Hz – 20 kHz; threshold varies with frequency |
| Bark scale | z = 13 arctan(0.00076 f) + 3.5 arctan((f/7500)²) |
| Critical bandwidth | ≈ 100 Hz below 500 Hz; ≈ 0.2f above 500 Hz |
| Simultaneous masking | Masker raises threshold in nearby critical bands |
| Temporal masking | Premasking ~5 ms; postmasking ~100–200 ms |

## Common Mistakes / Red Flags
- Using a fixed dB threshold independent of frequency.
- Ignoring the upward spread of masking.
- Confusing excitation level with sound pressure level.

## Zwicker Reference
- Chapter 1: Stimuli and procedures
- Chapter 2: Hearing area
- Chapter 3: Information processing in the auditory system
- Chapter 4: Masking
- Source file: `/Volumes/home_ext1/src_pierre/all_of_sotf/books/Psycho_Acoustics-Zwicker_Fastl.md`
