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

- `anthology` - the canonical system anchor file and default SYSTEM datum-file workbench
- `activity`
- `profile_basics`
- authoritative sandbox/source documents by file key

`activity` and `profile_basics` are not first-class surfaces anymore.

`anthology` is rendered as a layered datum table grouped by `layer` and `value_group`, with datum selection opening an inspector lens inside `system.root`.

## NETWORK

- `network.root`

`network.root` is the read-only portal-instance system-log workbench.

- It is not a tool and not a sandbox.
- Its canonical operational document is `data/system/system_log.json`.
- Contract correspondence is a filter/lens over the same system-log workbench.
- Event-type filtering is projected through the same root workbench.
- Selected log rows open a read-only inspector with linked contract detail when applicable.
- `NETWORK` has no canonical Messages/Hosted/Profile/Contracts peer-tab model in V2.

## UTILITIES

- `utilities.root`
- `utilities.tool_exposure`
- `utilities.integrations`

## Tool Posture

- Tool work pages stay under `SYSTEM`.
- Tool registry defaults are interface-panel-led.
- Tool workbench visibility defaults to `false`.
- Tool configuration and exposure remain owned by `UTILITIES`.
- Service-tool posture is determined by configured capabilities and available peripherals or integrations, not by portal identity.
