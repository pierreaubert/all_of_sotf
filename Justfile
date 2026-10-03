# Aggregate QA runs only on the Gitea macOS and Linux runners.
default:
    @just --list

_ci_only:
    @echo 'Aggregate checks run through Gitea Actions. Dispatch the aggregate-qa workflow with phase=metadata|check|tests|qa.' >&2
    @exit 2

dependencies: _ci_only

check: _ci_only

test: _ci_only

qa: _ci_only

qa-release: _ci_only
