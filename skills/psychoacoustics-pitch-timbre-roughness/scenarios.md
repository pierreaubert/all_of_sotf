# Pitch, Timbre, and Roughness Pressure Scenarios

## Scenario A
**Prompt:** A complex tone contains energy only at 400, 600, 800, and 1000 Hz. What pitch does a listener perceive? If a second sound has the same spectral peaks but each partial starts 5 ms later than the previous one, which perceptual attribute changes, and what unit is used for the fast temporal modulation attribute?

**Expected with skill:**
- The perceived pitch corresponds to the missing fundamental / virtual pitch of 200 Hz, because the partials are harmonics of 200 Hz (2nd, 3rd, 4th, 5th harmonics) even though 200 Hz itself is absent. Pitch must not be estimated from the spectral peak alone.
- The 5 ms inter-partial onset delay changes the temporal envelope and therefore the timbre of the sound.
- Roughness is commonly expressed in asper and fluctuation strength in vacil,
  but their rate dependence is gradual and model-dependent. One-time 5 ms onset
  offsets do not establish periodic modulation or increased roughness. Predict
  onset/envelope changes conditionally on the signal duration and waveform.

## Subagent Response
> The perceived pitch is 200 Hz (missing-fundamental/virtual pitch), because 400, 600, 800, and 1000 Hz are the 2nd–5th harmonics of 200 Hz. When each partial is delayed by 5 ms relative to the previous one, timbre changes because timbre includes temporal envelope and onset asynchrony. The unit for fast temporal modulation (roughness) is the asper.

## Verification
**Historical result: qualified** — 200 Hz is the expected virtual-pitch candidate
for appropriate audible sustained partials, not an unconditional percept for
every listener/stimulus. Asper names the roughness unit; it does not establish
that onset staggering produces roughness. This qualification is not a rerun.

## Scenario B: Phase and crossover preference

**Prompt:** "Toole says phase is hard to hear. Can we ignore the sub polarity?
Our phase-corrected preset also has a flatter magnitude response and is preferred."

**Expected:** Separate phase-only/absolute-polarity audibility from relative-source
summation. Sub polarity can change crossover magnitude strongly. The comparison
does not isolate a phase-only benefit; control magnitude, level, latency and
spatial conditions before attributing the preference.

**Status:** Review case added; not independently executed.
