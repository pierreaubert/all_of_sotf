# Hearing and Masking Pressure Scenarios

## Scenario A
**Prompt:** A 1 kHz pure tone at 30 dB SPL is played together with a broadband noise at 50 dB SPL. A student says, "The tone is 20 dB below the noise, so it is masked." Explain why this reasoning is incomplete and state the additional psychoacoustic factors needed to judge audibility.

**Expected with skill:**
- Raw level difference is not enough. Audibility depends on the masked threshold at 1 kHz, not on the overall noise level.
- Convert signal and masker frequencies to critical-band rate (Bark scale): z = 13 arctan(0.00076 f) + 3.5 arctan((f/7500)²). At 1 kHz, z ≈ 8.5 Bark.
- The masker’s excitation pattern spreads upward in frequency (upward spread of masking), so energy from lower and adjacent critical bands contributes to the threshold at 1 kHz.
- Critical bandwidth at 1 kHz is about 0.2f ≈ 200 Hz, so only the noise inside that band is the effective masker, not the full broadband level.
- Temporal effects and the listener’s absolute threshold in quiet must also be considered; if the masked threshold at 1 kHz is above 30 dB SPL, then the tone is inaudible.

## Subagent Response
> The student’s reasoning is incomplete because masking is not a whole-spectrum power comparison; it happens inside auditory filters (critical bands). A 50 dB SPL broadband noise spreads energy across many critical bands, so only the noise in the ~200 Hz band centered on 1 kHz matters. That band level may be only ~20–25 dB SPL, so the 30 dB tone may still be audible.
>
> Additional factors needed: critical-band analysis, Bark-scale excitation pattern, noise spectrum level/bandwidth, upward spread of masking, absolute threshold in quiet, and temporal effects (premasking, postmasking, overshoot).

## Verification
**PASS** — response matches expected key points (critical-band level, Bark scale, upward spread of masking, absolute threshold, temporal effects).

