# SOTF Buildbot CI

Local continuous integration for the six Rust workspaces under this repository.

## Security note

`master.cfg` contains plaintext bootstrap passwords for the workers. These are fine for local development, but they should be rotated before the Buildbot master is exposed to any network.

## Quick start

```bash
cd /Volumes/home_ext1/src_pierre/all_of_sotf/buildbot
just install
just master
just worker
just check
just start
```

Open the dashboard at http://localhost:8010.

Useful recipes:

- `just check` — validate `master.cfg`.
- `just restart` — stop and start the master and worker.
- `just rebuild-linux` — rebuild the Linux Docker worker image.

## Configuration

`buildbot/master.cfg` is the canonical tracked configuration. The `just master`, `just start`, and `just check` recipes copy it into `buildbot/master/master.cfg` (creating `buildbot/master/` if necessary), so the live config is always refreshed from the canonical file. Do not edit `buildbot/master/master.cfg` directly; it will be overwritten on the next sync.

## Stop

```bash
just stop
```

## Adding a new workspace builder

1. Add a workspace entry to `master.cfg` in the `WORKSPACES` list.
2. Ensure the workspace directory has a `Justfile` with `check`, `lint`, and `test` targets.
3. Run `just check` and restart the master.

## Cross-platform workers

See:
- `docs/windows-worker-setup.md`
- `docs/android-worker-setup.md`

> **Note:** Windows and Android builders require a manual VM/emulator setup before they will run. The Buildbot workers themselves only connect to the master; the underlying QEMU/Android emulator environment must be prepared and started separately.

## Current limitations

- **No commit-level source checkout:** builders run commands against the currently checked-out working tree on the host/VM. They do not fetch or check out the triggering commit. This is acceptable for this local CI instance, but it means the dashboard may report builds for a commit that is not exactly what exists on disk.
- **Windows and Android workers require the repo at the host path:** the Windows and Android builders use absolute host paths (`/Volumes/home_ext1/src_pierre/all_of_sotf`) as `workdir`. The VM or emulator must expose the repository at that same path, or the builder configuration must be adjusted for the worker environment.
- **Linux Docker latent worker assumes Docker Desktop on macOS:** the worker uses `host.docker.internal` to reach the master's PB port. This address is provided by Docker Desktop on macOS; on a Linux Docker host you will need to change `masterFQDN` in `master.cfg` to the host's IP address or a custom bridge name.
- **Root QA builders run only on macOS:** `root-qa-macos` (align-crates and quality-matrix-collect) writes artifacts back into the repo tree. The Linux container user does not match the host macOS user, so a Linux root QA builder is intentionally not provided.
