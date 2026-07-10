# Pitch, Timbre, and Roughness Pressure Scenarios

## Scenario A
**Prompt:** A complex tone contains energy only at 400, 600, 800, and 1000 Hz. What pitch does a listener perceive? If a second sound has the same spectral peaks but each partial starts 5 ms later than the previous one, which perceptual attribute changes, and what unit is used for the fast temporal modulation attribute?

**Expected with skill:**
- The perceived pitch corresponds to the missing fundamental / virtual pitch of 200 Hz, because the partials are harmonics of 200 Hz (2nd, 3rd, 4th, 5th harmonics) even though 200 Hz itself is absent. Pitch must not be estimated from the spectral peak alone.
- The 5 ms inter-partial onset delay changes the temporal envelope and therefore the timbre of the sound.
- Fast temporal modulation in the 20–200 Hz range produces roughness, measured in asper. Slower modulation (~0.5–20 Hz) would be fluctuation strength, measured in vacil; here 5 ms delay differences alter fine temporal structure, so the roughness/timbre dimension is affected.

## Subagent Response
> The perceived pitch is 200 Hz (missing-fundamental/virtual pitch), because 400, 600, 800, and 1000 Hz are the 2nd–5th harmonics of 200 Hz. When each partial is delayed by 5 ms relative to the previous one, timbre changes because timbre includes temporal envelope and onset asynchrony. The unit for fast temporal modulation (roughness) is the asper.

## Verification
**PASS** — response matches expected key points (200 Hz virtual pitch, timbre change, asper unit for roughness).

