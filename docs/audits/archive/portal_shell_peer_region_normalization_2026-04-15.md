# Portal Shell Peer-Region Normalization Audit

This follow-up audit records the terminology and posture normalization pass that made the portal shell describe the same peer-region model that the live shell already renders.

## Findings

- Public documentation still mixed the public `Interface Panel` term with legacy `inspector` wording, which blurred the difference between the shell's right rail and workbench-local detail projections.
- The shell composition payload exposed `inspector` fields only, even though the public contract had already moved to `Interface Panel` language.
- Root and tool postures were not documented as one centralized shell rule set, which left `AWS-CSM` looking like a workbench-visible exception instead of a standard interface-panel-led tool surface.
- The live shell had no first-class menubar workbench control, so the peer relationship between the `Workbench` and `Interface Panel` was harder to perceive in use.

## Corrections

- Public docs now define the top-level shell as `ide-shell` split into `ide-menubar` and `ide-body`, with `Activity Bar`, `Control Panel`, `Workbench`, and `Interface Panel` as the peer regions inside `ide-body`.
- `inspector` is now documented as a compatibility alias only. Public shell chrome documentation prefers `Interface Panel`, while workbench-local read-only detail is described as a `detail lens` or `detail view`.
- The shell composition payload now includes additive aliases:
  - `interface_panel_collapsed`
  - `workbench_collapsed`
  - `regions.interface_panel`
- Runtime posture defaults are now centralized and documented:
  - `SYSTEM`, `NETWORK`, and `UTILITIES` are workbench-primary by default.
  - The `Interface Panel` stays collapsed on root surfaces until mediation or explicit projected detail exists.
  - Tool surfaces default to interface-panel-led with `regions.workbench.visible=false`.
  - `AWS-CSM` now follows that same shared tool posture.
- The menubar now includes a `Workbench` toggle, and the shell layout preserves a peer two-surface posture when both the `Workbench` and `Interface Panel` are visible.

## Expected Stable State

- Public terminology consistently describes one shell with four peer regions.
- Compatibility consumers can keep reading `inspector` fields while new clients move to `interface_panel` aliases.
- Root surfaces stay workbench-primary by default without opening a blank right rail.
- Tool surfaces stay interface-panel-led by default while still allowing explicit secondary workbench evidence when a runtime projects it.
