# DSP Skills Family — Design

## Goal
Build a personal skill family that helps coding agents solve signal-and-systems problems by routing them to the right technique and giving them a concise, Oppenheim-grounded reference.

## Source Material
- `/Volumes/home_ext1/src_pierre/all_of_sotf/books/Signals_and_Systems_2nd_Edition_by_Oppen.md` (Oppenheim & Willsky, 2nd Ed.)
- ~39k lines, 76k characters; not embedded in skills.

## Architecture

All skills live under `~/.agents/skills/dsp/`.

### Main router skill
- `dsp-problem-solving/SKILL.md`
- Loaded when an agent faces a signal/system analysis task.
- Contains a small decision flowchart keyed on:
  - Continuous-time vs discrete-time
  - Known system equation vs signal-only
  - Target domain (time, frequency, s, z)
- Names the sub-skill to load next.
- Fallback rule: if classification is unclear or the problem mixes CT and DT, start with `dsp-fourier-analysis`.

### Sub-skills (focused problem-solving techniques)
Each sub-skill teaches one method and includes distilled reference tables.

| Skill | Topic | Oppenheim chapters |
|-------|-------|-------------------|
| `dsp-continuous-time-lti` | Differential equations, impulse response, convolution, CT Fourier series/transform | 1–5 |
| `dsp-discrete-time-lti` | Difference equations, impulse response, convolution sums, DTFT | 6–7 |
| `dsp-fourier-analysis` | Fourier series vs transform, CT vs DT, properties, theorems | 3–5, 7 |
| `dsp-laplace-transform` | ROC, inverse transforms, solving ODEs, H(s) | 9 |
| `dsp-z-transform` | ROC, inverse transforms, solving difference equations, H(z), stability | 10 |
| `dsp-sampling` | Nyquist, reconstruction, aliasing, up/downsampling | 7 |

## Skill File Format

Each `SKILL.md` has:

1. YAML frontmatter (`name`, `description` starting with "Use when...").
2. **Overview** — one-sentence core principle.
3. **When to Use** — triggers/symptoms; small inline flowchart if the method choice is non-obvious.
4. **Core Pattern** — numbered step-by-step technique.
5. **Quick Reference** — inline tables of transforms, properties, ROC rules, common pairs.
6. **Common Mistakes / Red Flags** — e.g. ignoring ROC, forgetting initial conditions, pole-zero cancellation edge cases.
7. **Oppenheim Reference** — chapter/section numbers and path to the local markdown for deeper lookup.

## Source Material Handling

- Skills are self-contained: inline reference tables only.
- The full Oppenheim markdown is referenced by absolute path for deeper reading.
- PDF is not used.

## First Implementation Pass

Build and test in this order:

1. `dsp-problem-solving` (router)
2. `dsp-fourier-analysis`
3. `dsp-z-transform`

Remaining sub-skills are out of scope for the first cycle.

## Testing Approach

Follow the TDD-for-skills process from `superpowers:writing-skills`:

1. Write 2–3 pressure scenarios for each skill before authoring it.
2. Run a subagent through each scenario without the skill; document baseline behavior and rationalizations.
3. Write the minimal skill that addresses those failures.
4. Re-run the scenarios with the skill loaded and verify compliance.
5. Close loopholes and re-test.

No skill is considered deployed until it passes its pressure scenarios.
