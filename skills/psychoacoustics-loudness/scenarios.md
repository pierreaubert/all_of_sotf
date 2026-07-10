# Loudness Pressure Scenarios

## Scenario A
**Prompt:** Two steady sounds both measure 70 dBA-weighted SPL. Sound A is a 1 kHz pure tone. Sound B is a broadband noise covering 50 Hz–10 kHz. Which is likely louder in sones, and why? What must a loudness model do that the A-weighted SPL cannot?

**Expected with skill:**
- Sound B is likely louder because A-weighting is a simple frequency contour, whereas loudness depends on the distribution of specific loudness across critical bands (Bark scale).
- A 1 kHz tone concentrates all energy in one critical band; broadband noise excites many bands, so the summed specific loudness N = Σ N' Δz is larger.
- A loudness model must convert each band’s level to specific loudness N' (sone/Bark), account for threshold in quiet, and integrate over audible Bark bands. A-weighted SPL cannot distinguish spectral distribution or doubling of loudness (+10 phon ≈ ×2 sones).

## Subagent Response
> Sound B (broadband noise) is likely louder in sones. A-weighted SPL compresses everything into one number; the 1 kHz tone excites one critical band, while the broadband noise excites many bands. Loudness adds across critical bands, so more bands with audible specific loudness yield a larger total N.
>
> A loudness model must analyze the spectrum into critical/1/3-octave bands, convert each band level to specific loudness accounting for threshold in quiet and nonlinear level-to-loudness, and integrate across Bark bands. A-weighted SPL cannot do this.

## Verification
**PASS** — response matches expected key points (broadband noise louder, critical-band summation, specific loudness integration, A-weighting limitations).

