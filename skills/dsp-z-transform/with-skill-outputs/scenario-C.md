# With-Skill Scenario C: Stability vs ROC confusion

**Prompt:** "A system has a pole at z = 2 and is causal. Is it stable?"

**Skill loaded:** `dsp-z-transform`

**Execution method:** Controller ran this via the `Agent` tool with `subagent_type: "coder"`. The system prompt included the full content of `skills/dsp/dsp-z-transform/SKILL.md` (SHA-256: `d54316dbef450934a679d296888cd8dd8e59341a0c3f3117758bf2840f41a7db`) followed by the user prompt below.

**Agent response (full):**

## Applying the z-transform stability pattern

1. **System function form**
   A pole at \(z = 2\) means \(H(z)\) has a denominator factor \((1 - 2z^{-1})\) (or \(z - 2\)).

2. **Find the ROC from causality**
   For a causal system, the ROC is the exterior of the outermost pole:
   \[
   |z| > 2
   \]

3. **Stability condition**
   A discrete-time LTI system is BIBO stable if and only if its ROC contains the unit circle \(|z| = 1\).

4. **Check**
   The ROC \(|z| > 2\) does **not** include \(|z| = 1\). Equivalently, the pole at \(z = 2\) lies outside the unit circle.

## Answer

No — the system is **unstable**. A causal system is stable only if all poles are inside the unit circle (\(|z| < 1\)); the pole at \(z = 2\) violates that condition.
