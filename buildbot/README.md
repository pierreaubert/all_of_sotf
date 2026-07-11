# SOTF Buildbot CI

Local continuous integration for the six Rust workspaces under this repository.

## Security note

`master.cfg` contains plaintext bootstrap passwords for the workers. These are fine for local development, but they should be rotated before the Buildbot master is exposed to any network.

## Quick start

```bash
cd /Volumes/home_ext1/src_pierre/all_of_sotf/buildbot
make install
make master
make worker
make start
```

Open the dashboard at http://localhost:8010.

## Stop

```bash
make stop
```

## Adding a new workspace builder

1. Add a workspace entry to `master.cfg` in the `WORKSPACES` list.
2. Ensure the workspace directory has a `Justfile` with `check`, `lint`, and `test` targets.
3. Run `make check` and restart the master.

## Cross-platform workers

See:
- `docs/windows-worker-setup.md`
- `docs/android-worker-setup.md`

> **Note:** Windows and Android builders require a manual VM/emulator setup before they will run. The Buildbot workers themselves only connect to the master; the underlying QEMU/Android emulator environment must be prepared and started separately.
