# Top-level orchestration for the six sibling workspaces.
# Install Just with: cargo install just

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

workspaces := "autoeq gpui-toolkit math-audio sofa-reader sotf symphonia-add-ons"

default:
	@just --list

# Show the recipes exposed by each workspace Justfile.
list:
	@for workspace in {{workspaces}}; do \
		echo "=== $workspace ==="; \
		just --justfile "$workspace/Justfile" --working-directory "$workspace" --list; \
	done

# Run the canonical test suite in every workspace. gpui-toolkit names its
# equivalent full workspace suite `ntest`; the other workspaces use `test`.
test: test-autoeq test-gpui-toolkit test-math-audio test-sofa-reader test-sotf test-symphonia-add-ons
	@echo "All workspace test suites passed."

test-autoeq:
	just --justfile autoeq/Justfile --working-directory autoeq test

test-gpui-toolkit:
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit ntest

test-math-audio:
	just --justfile math-audio/Justfile --working-directory math-audio test

test-sofa-reader:
	just --justfile sofa-reader/Justfile --working-directory sofa-reader test

test-sotf:
	just --justfile sotf/Justfile --working-directory sotf test

test-symphonia-add-ons:
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons test

# Run each workspace's check recipe. math-audio has no separate check recipe,
# so use its equivalent Cargo check command directly.
check: check-autoeq check-gpui-toolkit check-math-audio check-sofa-reader check-sotf check-symphonia-add-ons
	@echo "All workspace checks passed."

check-autoeq:
	just --justfile autoeq/Justfile --working-directory autoeq check

check-gpui-toolkit:
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit check

check-math-audio:
	cargo check --manifest-path math-audio/Cargo.toml --workspace --all-targets

check-sofa-reader:
	just --justfile sofa-reader/Justfile --working-directory sofa-reader check

check-sotf:
	just --justfile sotf/Justfile --working-directory sotf check

check-symphonia-add-ons:
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons check

fmt:
	just --justfile autoeq/Justfile --working-directory autoeq fmt
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit fmt
	just --justfile math-audio/Justfile --working-directory math-audio fmt
	just --justfile sofa-reader/Justfile --working-directory sofa-reader fmt
	just --justfile sotf/Justfile --working-directory sotf fmt
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons fmt

fmt-check:
	cargo fmt --manifest-path autoeq/Cargo.toml --all -- --check
	cargo fmt --manifest-path gpui-toolkit/Cargo.toml --all -- --check
	cargo fmt --manifest-path math-audio/Cargo.toml --all -- --check
	cargo fmt --manifest-path sofa-reader/Cargo.toml -- --check
	cargo fmt --manifest-path sotf/Cargo.toml --all -- --check
	cargo fmt --manifest-path symphonia-add-ons/Cargo.toml --all -- --check

lint:
	just --justfile autoeq/Justfile --working-directory autoeq lint
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit lint
	just --justfile math-audio/Justfile --working-directory math-audio lint
	just --justfile sofa-reader/Justfile --working-directory sofa-reader clippy
	just --justfile sotf/Justfile --working-directory sotf lint
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons lint

build:
	cargo build --manifest-path autoeq/Cargo.toml --workspace
	cargo build --manifest-path gpui-toolkit/Cargo.toml --workspace
	cargo build --manifest-path math-audio/Cargo.toml --workspace
	cargo build --manifest-path sofa-reader/Cargo.toml --release
	cargo build --manifest-path sotf/Cargo.toml --workspace
	cargo build --manifest-path symphonia-add-ons/Cargo.toml --workspace

clean:
	just --justfile autoeq/Justfile --working-directory autoeq clean
	just --justfile gpui-toolkit/Justfile --working-directory gpui-toolkit clean
	just --justfile math-audio/Justfile --working-directory math-audio clean
	just --justfile sofa-reader/Justfile --working-directory sofa-reader clean
	just --justfile sotf/Justfile --working-directory sotf clean
	just --justfile symphonia-add-ons/Justfile --working-directory symphonia-add-ons clean
