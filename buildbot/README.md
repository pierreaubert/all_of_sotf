# SOTF Buildbot CI

Local continuous integration for the six Rust workspaces under this repository.

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
