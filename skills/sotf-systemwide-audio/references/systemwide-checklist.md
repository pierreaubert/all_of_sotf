# Systemwide Audio Checklist

## Core Files

- `crates/systemwide/ARCHITECTURE.md`
- `crates/systemwide/README.md`
- `crates/systemwide/CLAUDE.md`
- `crates/systemwide/crates/daemon`
- `crates/systemwide/crates/driver-hal`
- `/Users/pierre/.codex/memories/sotf-systemwide-architecture.md`

## Invariants

- Do not route systemwide playback into the virtual output device.
- HAL readiness should remain alive while idle when that is the documented behavior.
- Shared-memory and socket runtime paths must be bounded to the selected runtime dir.
- Key rotation and cipher recovery must not leave audio handoff silently broken.
- Toolbar state should reflect daemon status, not stale local guesses.

## Frequent Commands

- `just systemwide-lab`
- `just prod-hal-driver`
- `cargo check -p sotf-daemon`
- `cargo test -p sotf-daemon`
- `cargo test -p driver-hal`
- `xcodebuild` or HAL-specific build/test commands when Swift driver code changes.

## Documentation Rule

When architecture, state ownership, runtime flows, debugging strategy, installer behavior, or operational recovery procedures change, update `crates/systemwide/ARCHITECTURE.md` and any nearby README/changelog material in the same change.
