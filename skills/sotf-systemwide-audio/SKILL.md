---
name: sotf-systemwide-audio
description: "Use for SOTF systemwide audio work: daemon, HAL driver, virtual output invariants, shared memory, encrypted handoff, runtime state ownership, installer lifecycle, recovery flows, channel patching, and systemwide docs."
---

# SOTF Systemwide Audio

## When To Use

Use this skill for `crates/systemwide`, `sotf-daemon`, HAL driver code, virtual output behavior, systemwide toolbar state, runtime sockets/shared memory, installer scripts, audio handoff encryption, and device recovery.

## Working Sequence

1. Start with TokenSave for the daemon, driver, state owner, or UI intent named in the request.
2. Read the current architecture doc before changing ownership or runtime flows.
3. Preserve the virtual output invariant: systemwide playback must not accidentally open the virtual output as the real output device.
4. Keep daemon state, toolbar intent state, and HAL readiness behavior synchronized.
5. Update architecture docs, README, or changelog when changing runtime flows or recovery behavior.

## Operational Bias

- Prefer explicit fault states over silent fallback.
- Treat idle readiness as part of correctness, not merely UI status.
- Keep recovery paths deterministic after device resurrection, key rotation, or daemon restart.
- For audio safety, check sample-rate, channel map, and shared-memory bounds before UI symptoms.

## References

- Read `references/systemwide-checklist.md` for files, commands, and invariant checks.
