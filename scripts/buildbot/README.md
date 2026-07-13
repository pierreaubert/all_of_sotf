# SOTF Buildbot CI

Local cross-platform continuous integration for `gpui-toolkit`, `math-audio`,
`autoeq`, and `sotf`.

## Coverage policy

| Trigger | macOS | Linux | Windows | Android | iOS/tvOS |
| --- | --- | --- | --- | --- | --- |
| workspace commit | check/lint/full tests | check/lint/full tests | check/lint/full tests | — | — |
| nightly | tests + full `just qa` | tests + full `just qa` | tests + full `just qa` | supported target checks | simulator builds |
| force scheduler | any individual builder | any individual builder | any individual builder | any target builder | simulator or device build |

`math-audio` has no `just check`; its lint and nextest recipes compile its
supported surface. Device builds are force-only because they may need connected
hardware, signing, or provisioning. The exact matrix lives in `ci_matrix.py`
and has regression tests under `tests/`.

## Version and history tracking

Every builder records two Buildbot properties before executing work:

- `tested_revision`: the actual workspace `HEAD`, not merely the revision that
  caused the scheduler to run.
- `version_snapshot`: a JSON record containing UTC time, revision/describe,
  branch and dirty state, OS/release/architecture, and Python, Rust, Cargo,
  cargo-nextest, and just versions.

Buildbot stores builds, results, logs, and these properties in
`master/state.sqlite`, so the dashboard can compare results over time by
platform and tool/repository version. Back up the entire `master/` directory to
retain history. This local installation intentionally tests shared working
trees rather than checking out each sourcestamp; `tested_revision` is therefore
the authoritative version.

## Quick start

Buildbot 4.1 requires Python 3.9–3.12. The recipes default to `python3.12`; set
`HOST_PYTHON` to another supported interpreter when needed.

```bash
cd /Volumes/home_ext1/src_pierre/all_of_sotf/scripts/buildbot
just install
just validate
just master
just worker
just rebuild-linux
just start
```

Open <http://localhost:8010>. `just install` detects and rebuilds a virtualenv
whose interpreter or shebangs became stale after moving this directory.

Useful recipes:

- `just validate` — run matrix/version tests and Buildbot `checkconfig`.
- `just restart` — stop, upgrade, and start the local master and worker.
- `just rebuild-linux` — rebuild the Linux latent-worker image.
- `just logs-master` / `just logs-worker` — follow runtime logs.
- `just stop` — stop the local worker and master.

The force-only `buildbot-smoke-macos` and `buildbot-smoke-linux` builders
validate the configuration, latent worker, and version-property pipeline
without launching a workspace's long test suite.

## External workers

The macOS worker is local. Linux uses a Docker latent worker. Windows and
Android require separately prepared workers:

- `docs/windows-worker-setup.md`
- `docs/android-worker-setup.md`

The master does not discover or boot QEMU VMs/emulators. Workers connect to the
master on PB port 9989, and their checkout/mount must match the path documented
in the setup guide.

## Configuration and security

`master.cfg`, `ci_matrix.py`, and `version_snapshot.py` are canonical tracked
files. The recipes copy the master-side modules into `master/`; do not edit the
generated copies.

Bootstrap worker passwords default to local-development values. Override
`BUILDBOT_MACOS_PASSWORD`, `BUILDBOT_LINUX_PASSWORD`,
`BUILDBOT_WINDOWS_PASSWORD`, and `BUILDBOT_ANDROID_PASSWORD` before exposing
the service to a network. `BUILDBOT_DOCKER_MASTER` overrides the Docker
worker's default `host.docker.internal` master address.
