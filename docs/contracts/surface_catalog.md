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

`anthology` is rendered as a layered datum table grouped by `layer` and `value_group`, with datum selection opening a detail lens inside `system.root`.

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
- Its default posture is interface-panel-led.
- Its workbench is runtime-owned, read-only, and hidden by default until secondary evidence is explicitly projected.
- Its canonical query keys are:
  - `view`
  - `domain`
  - `profile`
  - `section`
- Its default Interface Panel is the primary tool surface.
- Its domain gallery is secondary workbench content revealed when the workbench is explicitly shown.
- A selected domain may project:
  - a user email gallery
  - an onboarding section
  - a newsletter section
- Service-tool posture is determined by required capabilities and available peripheral employment, not by a separate portal type model.
- `AWS-CSM` is operational only when the active portal can employ the authenticated peripheral package. In the live topology that means FND alone can route those external operations.

## CTS-GIS

- `system.tools.cts_gis`

`CTS-GIS` is one `SYSTEM` child mediation tool surface.

- Its canonical route is `/portal/system/tools/cts-gis`.
- Its default posture is interface-panel-led.
- Its workbench is `tool_secondary_evidence` and stays hidden by default until secondary evidence is explicitly shown.
- Its dominant `Interface Panel` mounts one CTS-GIS-local body with:
  - `Diktataograph`
  - `Garland` geospatial pane
  - `Garland` profile pane
- `Diktataograph` is the CTS-GIS structural navigation canvas (`navigation_canvas`).
- `navigation_canvas.mode` defaults to `directory_dropdowns`.
- `navigation_canvas.source_authority` is `samras_magnitude`.
- `navigation_canvas.decode_state` blocks when magnitude decode or node bindings are invalid.
- `navigation_canvas.dropdowns` carries one dropdown per resolved structural depth.
- `navigation_canvas.active_path` carries the resolved lineage.
- `Garland` is the CTS-GIS correlated projection surface (`garland_split_projection`) with dominant `geospatial_projection` and secondary `profile_projection`.
- Garland remains visible and stateful once a structural selection exists.
- `profile_projection` may show the current selected node with blank values when no matching profile source has been resolved yet.
- `geospatial_projection` stays blank until the selected node resolves valid profile and HOPS evidence.
- Title fallback is blank-only when ASCII title decode is unavailable.
- In narrow posture, the CTS-GIS-local body may fall back to a vertical stack while preserving the same contract.
- CTS-GIS mediates on the selected anchor-file datum and projects correlated source-file evidence into the Interface Panel.
- CTS-GIS tool-local navigation does not widen the shared shell focus stack. The shell focus remains `sandbox -> file -> datum -> object`.
- Tool-local state is body-carried through CTS-GIS `tool_state`, not projected through new query keys.
- When a selected node is present and no explicit tool-local intention is supplied, CTS-GIS normalizes `Intention` to `self` so Garland reflects the current node.
- The `Control Panel` holds CTS-GIS-local directive, AITAS, and source-evidence controls.
- The workbench remains diagnostic or raw supporting evidence rather than a duplicate of Garland.
- v2.5.4 phase-B is canonical-only for CTS-GIS identifiers and storage anchors.
- Legacy CTS-GIS aliases are rejected at `POST /portal/api/v2/system/tools/cts-gis` with `400 legacy_maps_alias_unsupported`.

## NETWORK

- `network.root`

`network.root` is the read-only portal-instance system-log workbench.

- It is not a tool and not a sandbox.
- Its canonical operational document is `data/system/system_log.json`.
- Contract correspondence is a filter/lens over the same system-log workbench.
- Event-type filtering is projected through the same root workbench.
- Selected log rows open a read-only Interface Panel detail view with linked contract detail when applicable.
- The interface panel is collapsed by default until selected-record focus exists.
- `NETWORK` has no canonical Messages/Hosted/Profile/Contracts peer-tab model in V2.

The host shell activity bar remains icon-only across all root and tool entries. Labels belong to hover titles and accessibility metadata, not to persistent bar text.
The top menubar is the only shell header.

## UTILITIES

- `utilities.root`
- `utilities.tool_exposure`
- `utilities.integrations`

`UTILITIES` is section-led rather than focus-depth-led.

- Its control panel projects `Root` and `Section` context rows.
- Its grouped selections live under `Sections`.
- Its interface panel is collapsed by default until a utilities section explicitly projects detail there.
- It does not simulate sandbox/file/datum/object depth when that context does not exist.

## Tool Posture

- Tool work pages stay under `SYSTEM`.
- Tool registry defaults are interface-panel-led.
- Tool workbench visibility defaults to `false`.
- Tool surfaces use mutually exclusive single-click behavior between `Workbench` and `Interface Panel` by default.
- Double-clicking either tool toggle enables route-scoped lock mode that allows both panels to remain visible together.
- Tool lock is non-persistent and clears when leaving the current tool route or composition.
- Tool surfaces may still project secondary workbench content explicitly when lock mode is enabled.
- Tool configuration and exposure remain owned by `UTILITIES`.
- Service-tool posture is determined by configured capabilities and available peripherals or integrations, not by portal identity.
