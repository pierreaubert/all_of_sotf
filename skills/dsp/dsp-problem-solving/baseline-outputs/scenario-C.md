# Baseline Scenario C: Ambiguous mixed-domain prompt

**Prompt:** "I sampled a continuous cosine at 8 kHz and the reconstructed signal sounds wrong."

**Execution method:** Controller ran this via the `Agent` tool with `subagent_type: "coder"` and a plain system prompt that did not load or reference any DSP skill.

**Baseline response (full):**

The most likely explanation is **aliasing**: the cosine’s frequency is probably higher than the **Nyquist frequency** of your 8 kHz sampler, which is half the sample rate:

\[
f_N = \frac{f_s}{2} = \frac{8000}{2} = 4000\ \text{Hz}
\]

## Why this happens

The Nyquist–Shannon sampling theorem says a continuous signal must contain no energy above \(f_s/2\) to be reconstructable without loss. A cosine has a single spectral line at frequency \(f_0\). If:

- \(f_0 < 4000\ \text{Hz}\): sampling and ideal reconstruction should recover the original tone.
- \(f_0 \ge 4000\ \text{Hz}\): the sample values are indistinguishable from those of a lower-frequency cosine. This folded/aliased tone is what you hear on reconstruction.

## Computing the alias frequency

For a real cosine sampled at \(f_s\), aliases appear at:

\[
f_{\text{alias}} = \left| f_0 - k \cdot f_s \right|
\]

where \(k\) is any integer that puts the result in the range \([0, f_s/2]\).

With \(f_s = 8000\ \text{Hz}\), some common cases:

| Cosine freq \(f_0\) | Alias heard | Notes |
|---|---|---|
| 3 kHz | 3 kHz | No aliasing |
| 4 kHz | 4 kHz | Right at Nyquist limit |
| 5 kHz | 3 kHz | Folds around 4 kHz |
| 6 kHz | 2 kHz | |
| 7 kHz | 1 kHz | Very obvious pitch drop |
| 9 kHz | 1 kHz | Same as 7 kHz |
| 11 kHz | 3 kHz | Same as 5 kHz |

So a 7 kHz cosine sampled at 8 kHz comes out sounding like a 1 kHz tone.

## Why it “sounds wrong” rather than just noisy

Aliasing is not ordinary distortion or quantization noise — it is a **frequency-domain fold**. The reconstructed signal is a perfectly clean cosine, but at the wrong frequency. Human hearing is very sensitive to pitch, so a shifted tone is immediately noticeable.

## Other possible contributors

If the cosine is already below 4 kHz and still sounds wrong, check these practical issues:

1. **No anti-aliasing filter before the ADC.** Even if your intended tone is 2 kHz, any high-frequency noise or harmonics above 4 kHz will alias into the audible band.
2. **Non-ideal reconstruction.** A DAC usually outputs a zero-order-hold staircase, not impulses. Without a good low-pass reconstruction filter at \(f_s/2\), you hear high-frequency “image” tones.
3. **Clipping / gain staging.** If the cosine amplitude is too large, clipping adds harmonics that may alias or sound harsh.
4. **Sample-rate mismatch.** If the playback system assumes a different rate (e.g., you recorded at 8 kHz but played back at 44.1 kHz, or vice versa), the pitch shifts by the ratio of the rates.

## What would confirm it

If you tell me the original cosine frequency \(f_0\), I can compute the exact alias frequency you should expect. You can also verify experimentally:

- Sweep the cosine frequency upward. If you pass 4 kHz and the perceived pitch starts going *down*, that is aliasing.
- Add a steep analog low-pass filter before the ADC, cutoff just below 4 kHz. If the problem disappears, aliasing was the cause.

**Bottom line:** sampling an 8 kHz cosine at an 8 kHz sample rate, for example, would produce a DC alias; sampling a 7 kHz cosine would produce a 1 kHz alias. The “wrong” sound is almost certainly the result of the input signal containing energy above 4 kHz.
