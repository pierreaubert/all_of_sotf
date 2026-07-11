# GPUI Product UI Checklist

## Common Areas

- `crates/app-gpui`
- `crates/app-gpui/components/room_eq`
- `crates/app-gpui/app/state`
- `crates/gpui-toolkit/gpui-ui-kit`
- `crates/gpui-toolkit/gpui-design`
- `crates/sotf-plugins/crates/sotf-host/src/layout_solver.rs`

## Frequent Checks

- `cargo check -p sotf-gpui`
- `cargo test -p sotf-gpui room_eq`
- `cargo test -p gpui-ui-kit`
- `cargo test -p sotf-host layout`
- `just qa-gpui-obvious` when available and relevant.

## Review Focus

- Theme fields should not be duplicated or drift from design-system state.
- Accordions, panes, and plugin panels need horizontal and narrow-width behavior checked.
- Plugin controls should use the intended selector/stepper/toggle pattern for the parameter type.
- Remote server UI should keep discovery, manual URL state, token storage, and reachability states separate.
- Avoid duplicating business logic in UI components.

## Manual Verification Prompts

- Does the panel fit at narrow widths?
- Are long labels clipped, wrapped, or given stable space?
- Does collapsed/expanded state preserve layout?
- Does state come from the app model rather than transient widget guesses?
