# Psychoacoustics Router Pressure Scenarios

## Toole-derived review case: choose the experiment, not just the metric

**Prompt:** "Preset A has lower room-response RMS error and wins a sighted stereo
demo. Prove its excess-phase FIR improves timbre for all listeners. Can we test
mono by feeding the same signal to L and R?"

**Expected:** Neither metric error nor a sighted preference establishes the claim.
Separate detection, preference and attribution; control level, magnitude, playback
mode and order. Single-source mono can help diagnose timbre, while L+R coherent
playback adds summation and is a different condition. Test spatial performance
in the intended format and report listener/programme variation rather than a
universal conclusion. Route timbre analysis to the attribute skill and matching
to loudness guidance as needed.

**Status:** Review case added; not independently executed. Historical routing
results below predate this addition.

## Scenario A: Masking in a codec
**Prompt:** "A 1 kHz tone at 50 dB SPL is masked by broadband noise at 60 dB SPL. Is it audible?"
**Expected:** Agent loads `psychoacoustics-hearing-and-masking`.

## Scenario B: Loudness meter
**Prompt:** "I need to implement a loudness meter for streaming audio. Which model should I use?"
**Expected:** Agent loads `psychoacoustics-loudness` and mentions Zwicker/ISO 532-1.

## Scenario C: Roughness estimation
**Prompt:** "How do I estimate the roughness of an amplitude-modulated tone for a timbre analysis tool?"
**Expected:** Agent loads `psychoacoustics-pitch-timbre-roughness`.

# Subagent Routing Tests

**Method:** The `Agent` tool with `subagent_type: "coder"` was not available in this environment, so each scenario was run via the `kimi -p` CLI prompt mode as a fallback. Each prompt loaded the full `psychoacoustics-problem-solving/SKILL.md` content as the router instructions and asked the model to return exactly one sub-skill name with a brief justification.

## Scenario A Result
**Chosen sub-skill:** `psychoacoustics-hearing-and-masking`
**Status:** ✅ PASS
**Subagent response:**
> `psychoacoustics-hearing-and-masking`
>
> The task involves a tone being masked by broadband noise and asks about audibility, which falls under masking and peripheral hearing thresholds.

## Scenario B Result
**Chosen sub-skill:** `psychoacoustics-loudness`
**Status:** ✅ PASS
**Subagent response:**
> `psychoacoustics-loudness`
>
> The task is a loudness/level problem: implementing a loudness meter for streaming audio. The routing rules direct loudness meters and partial-masking level estimation to the loudness sub-skill.

## Scenario C Result
**Chosen sub-skill:** `psychoacoustics-pitch-timbre-roughness`
**Status:** ✅ PASS
**Subagent response:**
> `psychoacoustics-pitch-timbre-roughness`
>
> Roughness is a timbre-related perceptual attribute explicitly covered by that sub-skill.

## Summary
All three scenarios routed to the expected sub-skills. No `SKILL.md` patch was required.
