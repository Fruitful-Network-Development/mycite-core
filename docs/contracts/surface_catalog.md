# Surface Catalog

The surface catalog is rooted only in `SYSTEM`, `NETWORK`, and `UTILITIES`.

## SYSTEM

First-class surfaces:

- `system.root`
- `system.operational_status`
- `system.tools.aws`
- `system.tools.aws_narrow_write`
- `system.tools.aws_csm_sandbox`
- `system.tools.aws_csm_onboarding`
- `system.tools.cts_gis`
- `system.tools.fnd_ebi`

Workspace file modes under `system.root`:

- `anthology`
- `activity`
- `profile_basics`
- authoritative sandbox/source documents by file key

`activity` and `profile_basics` are not first-class surfaces anymore.

## NETWORK

- `network.root`

## UTILITIES

- `utilities.root`
- `utilities.tool_exposure`
- `utilities.integrations`

## Tool Posture

- Tool work pages stay under `SYSTEM`.
- Tool registry defaults are interface-panel-led.
- Tool workbench visibility defaults to `false`.
- Tool configuration and exposure remain owned by `UTILITIES`.
