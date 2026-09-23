# Hearing and Masking Pressure Scenarios

## Scenario A
**Prompt:** A 1 kHz pure tone at 30 dB SPL is played together with a broadband noise at 50 dB SPL. A student says, "The tone is 20 dB below the noise, so it is masked." Explain why this reasoning is incomplete and state the additional psychoacoustic factors needed to judge audibility.

**Expected with skill:**
- Raw level difference is not enough. Audibility depends on the masked threshold at 1 kHz, not on the overall noise level.
- Convert signal and masker frequencies to critical-band rate (Bark scale): z = 13 arctan(0.00076 f) + 3.5 arctan((f/7500)²). At 1 kHz, z ≈ 8.5 Bark.
- The masker’s excitation pattern spreads upward in frequency (upward spread of masking), so energy from lower and adjacent critical bands contributes to the threshold at 1 kHz.
- Use the selected auditory filter and noise spectrum level to estimate effective
  masker excitation. A rectangular bandwidth approximation is not a hard cutoff:
  filter skirts and level-dependent spreading can contribute. Overall noise SPL
  without its spectral distribution is insufficient for a numerical verdict.
- Temporal effects and the listener’s absolute threshold in quiet must also be considered; if the masked threshold at 1 kHz is above 30 dB SPL, then the tone is inaudible.

## Subagent Response

Historical response, retained for provenance. The "only"-in-band claim and
20–25 dB band-level estimate below are not justified without a noise spectrum
and filter model; the original PASS is superseded by this correction, not a
newly executed test.
> The student’s reasoning is incomplete because masking is not a whole-spectrum power comparison; it happens inside auditory filters (critical bands). A 50 dB SPL broadband noise spreads energy across many critical bands, so only the noise in the ~200 Hz band centered on 1 kHz matters. That band level may be only ~20–25 dB SPL, so the 30 dB tone may still be audible.
>
> Additional factors needed: critical-band analysis, Bark-scale excitation pattern, noise spectrum level/bandwidth, upward spread of masking, absolute threshold in quiet, and temporal effects (premasking, postmasking, overshoot).

## Verification
**Historical result: needs correction** — broad masking reasoning is useful,
but the numerical band level and hard bandwidth cutoff are unsupported.

## Scenario B: Sub-band resonance and listener variability

**Prompt:** "A narrow speaker resonance vanishes after 1/3-octave smoothing.
Everyone on our panel has a normal audiogram. Can we declare it inaudible?"

**Expected:** No. Preserve adequate spectral resolution; assess Q, prominence,
stimulus, level and repeatability. Critical bandwidth is not a hard discrimination
limit, and a normal audiogram does not establish identical suprathreshold or
binaural performance. Do not diagnose hearing impairment from disagreement.

**Status:** Review case added; not independently executed.
