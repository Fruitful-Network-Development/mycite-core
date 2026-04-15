# Surface Catalog

The surface catalog is rooted only in `SYSTEM`, `NETWORK`, and `UTILITIES`.

## SYSTEM

First-class surfaces:

- `system.root`
- `system.tools.aws_csm`
- `system.tools.cts_gis`
- `system.tools.fnd_ebi`

Workspace file modes under `system.root`:

- `anthology` - the canonical system anchor file and default SYSTEM datum-file workbench
- `activity`
- `profile_basics`
- authoritative sandbox/source documents by file key

`activity` and `profile_basics` are not first-class surfaces anymore.

`anthology` is rendered as a layered datum table grouped by `layer` and `value_group`, with datum selection opening an inspector lens inside `system.root`.

`SYSTEM` control-panel behavior is canonicalized as:

- current context rows first
- verb tabs in a compact navigation strip
- file, datum, or object selections below the current focus level

## AWS-CSM

- `system.tools.aws_csm`

`AWS-CSM` is one `SYSTEM` child service tool surface.

- It is not four separate public tools.
- Its canonical route is `/portal/system/tools/aws-csm`.
- Its control-panel context rows are:
  - `Sandbox: AWS-CSM`
  - `File: tool.<msn>.aws-csm.json`
  - `Mediation: spec.json`
- Its workbench is runtime-owned and read-only.
- Its canonical query keys are:
  - `view`
  - `domain`
  - `profile`
  - `section`
- Its default workbench is a domain gallery.
- A selected domain may project:
  - a user email gallery
  - an onboarding section
  - a newsletter section
- Service-tool posture is determined by required capabilities and available peripheral employment, not by a separate portal type model.
- `AWS-CSM` is operational only when the active portal can employ the authenticated peripheral package. In the live topology that means FND alone can route those external operations.

## NETWORK

- `network.root`

`network.root` is the read-only portal-instance system-log workbench.

- It is not a tool and not a sandbox.
- Its canonical operational document is `data/system/system_log.json`.
- Contract correspondence is a filter/lens over the same system-log workbench.
- Event-type filtering is projected through the same root workbench.
- Selected log rows open a read-only inspector with linked contract detail when applicable.
- `NETWORK` has no canonical Messages/Hosted/Profile/Contracts peer-tab model in V2.

The host shell activity bar remains icon-only across all root and tool entries. Labels belong to hover titles and accessibility metadata, not to persistent bar text.

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
