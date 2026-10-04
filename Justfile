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

# Optional local developer recipes for the six workspaces listed below.
# Aggregate check, test, and QA recipes above remain Gitea-only.

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

workspaces := "autoeq gpui-toolkit math-audio sofa-reader sotf symphonia-add-ons"


# Show the recipes exposed by each workspace Justfile.
local-list:
	@for workspace in {{workspaces}}; do \
		echo "=== $workspace ==="; \
		just --justfile "$workspace/Justfile" --working-directory "$workspace" --list; \
	done

# Run the canonical test suite in every workspace. gpui-toolkit names its
# equivalent full workspace suite `ntest`; the other workspaces use `test`.
local-test: local-test-autoeq local-test-gpui-toolkit local-test-math-audio local-test-sofa-reader local-test-sotf local-test-symphonia-add-ons
	@echo "All workspace test suites passed."

local-test-autoeq:
	just --justfile autoeq/Justfile --working-directory autoeq test

local-test-gpui-toolkit:
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit ntest

local-test-math-audio:
	just --justfile math-audio/Justfile --working-directory math-audio test

local-test-sofa-reader:
	just --justfile sofa-reader/Justfile --working-directory sofa-reader test

local-test-sotf:
	just --justfile sotf/Justfile --working-directory sotf test

local-test-symphonia-add-ons:
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons test

# Run each workspace's check recipe. math-audio has no separate check recipe,
# so use its equivalent Cargo check command directly.
local-check: local-check-autoeq local-check-gpui-toolkit local-check-math-audio local-check-sofa-reader local-check-sotf local-check-symphonia-add-ons
	@echo "All workspace checks passed."

local-check-autoeq:
	just --justfile autoeq/Justfile --working-directory autoeq check

local-check-gpui-toolkit:
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit check

local-check-math-audio:
	cargo check --manifest-path math-audio/Cargo.toml --workspace --all-targets

local-check-sofa-reader:
	just --justfile sofa-reader/Justfile --working-directory sofa-reader check

local-check-sotf:
	just --justfile sotf/Justfile --working-directory sotf check

local-check-symphonia-add-ons:
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons check

local-fmt:
	just --justfile autoeq/Justfile --working-directory autoeq fmt
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit fmt
	just --justfile math-audio/Justfile --working-directory math-audio fmt
	just --justfile sofa-reader/Justfile --working-directory sofa-reader fmt
	just --justfile sotf/Justfile --working-directory sotf fmt
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons fmt

local-fmt-check:
	cargo fmt --manifest-path autoeq/Cargo.toml --all -- --check
	cargo fmt --manifest-path gpui-toolkit/Cargo.toml --all -- --check
	cargo fmt --manifest-path math-audio/Cargo.toml --all -- --check
	cargo fmt --manifest-path sofa-reader/Cargo.toml -- --check
	cargo fmt --manifest-path sotf/Cargo.toml --all -- --check
	cargo fmt --manifest-path symphonia-add-ons/Cargo.toml --all -- --check

local-lint:
	just --justfile autoeq/Justfile --working-directory autoeq lint
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit lint
	just --justfile math-audio/Justfile --working-directory math-audio lint
	just --justfile sofa-reader/Justfile --working-directory sofa-reader clippy
	just --justfile sotf/Justfile --working-directory sotf lint
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons lint

local-build:
	cargo build --manifest-path autoeq/Cargo.toml --workspace
	cargo build --manifest-path gpui-toolkit/Cargo.toml --workspace
	cargo build --manifest-path math-audio/Cargo.toml --workspace
	cargo build --manifest-path sofa-reader/Cargo.toml --release
	cargo build --manifest-path sotf/Cargo.toml --workspace
	cargo build --manifest-path symphonia-add-ons/Cargo.toml --workspace

local-clean:
	just --justfile autoeq/Justfile --working-directory autoeq clean
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit clean
	just --justfile math-audio/Justfile --working-directory math-audio clean
	just --justfile sofa-reader/Justfile --working-directory sofa-reader clean
	just --justfile sotf/Justfile --working-directory sotf clean
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons clean
