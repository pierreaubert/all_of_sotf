---
name: sotf-plugin-host-dsp
description: "Use for SOTF plugin host and DSP work: sotf-plugins, sotf-host, automation, parameter registration, hot audio paths, STFT processing, channel layouts, plugin UI schemas, presets, and host/engine integration."
---

# SOTF Plugin Host DSP

## When To Use

Use this skill for work under `crates/sotf-plugins`, host automation, plugin process context, DSP parameter wiring, plugin review follow-ups, external plugin hosting, UI schemas for plugins, or audio-thread performance issues.

## Working Sequence

1. Use TokenSave to identify the plugin, host surface, and tests before opening source files.
2. Determine whether the change affects DSP behavior, parameter metadata, UI layout, presets, or host transport.
3. For DSP changes, audit allocation and locking in `process()` paths.
4. For parameters, update registration, setters, getters, cached metadata, and tests together.
5. Verify with focused crate tests before broader host or plugin checks.

## Hot-Path Rules

- No per-frame allocations in audio callbacks.
- Pre-allocate in build/setup paths and reuse buffers in process paths.
- Avoid locking plugin mutexes per frame.
- STFT plugins must return `context.num_frames` to avoid ring-buffer underrun unless the contract has intentionally changed.
- Preserve channel-count transitions between plugins.

## References

- Read `references/host-dsp-checklist.md` for parameter, preset, automation, and QA checklists.
