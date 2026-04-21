# Surface Catalog

The surface catalog is rooted only in `SYSTEM`, `NETWORK`, and `UTILITIES`.

## SYSTEM

First-class surfaces:

- `system.root`
- `system.tools.workbench_ui`
- `system.tools.aws_csm`
- `system.tools.cts_gis`
- `system.tools.fnd_dcm`
- `system.tools.fnd_ebi`

Workspace file modes under `system.root`:

- `anthology` - the canonical system anchor file and default SYSTEM datum-file workbench
- `activity`
- `profile_basics`
- authoritative sandbox/source documents by file key

`activity` and `profile_basics` are not first-class surfaces anymore.

`anthology` is rendered as a layered datum table grouped by `layer` and `value_group`, with datum selection opening a detail lens inside `system.root`.

For migrated portals, authoritative `SYSTEM` datum/workbench/profile/grant posture is SQL-backed while preserving the same file/workbench outward shapes.

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
- Its runtime may project workbench content, but the first server composition still keeps that workbench hidden.
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

## Workbench UI

- `system.tools.workbench_ui`

`Workbench UI` is one `SYSTEM` child read-only two-pane SQL authority inspector surface.

- Its canonical route is `/portal/system/tools/workbench-ui`.
- Its default posture is workbench-primary.
- Its workbench is the primary spreadsheet-like SQL datum grid and stays visible on first composition.
- It does not replace the reducer-owned `/portal/system` anthology workspace.
- It inspects authoritative SQL-backed documents only; retained host-bound/private assets and `NETWORK` derived materializations remain outside its corpus unless separately ported.
- Its `Interface Panel` shows selected-row semantic identity plus additive directive overlay summaries.
- Its canonical query keys are:
  - `document`
  - `document_filter`
  - `document_sort`
  - `document_dir`
  - `filter`
  - `sort`
  - `dir`
  - `group`
  - `workbench_lens`
  - `source`
  - `overlay`
  - `row`
- Its document-table columns are:
  - `document_name`
  - `document_id`
  - `source_kind` when source metadata is visible
  - `version_hash` with short identity badges plus full value text
  - `row_count`
- Its interpreted row-grid columns are:
  - `datum_address`
  - `layer`
  - `value_group`
  - `iteration`
  - `labels`
  - `relation`
  - `object_ref`
  - `hyphae_hash` with short identity badges plus full value text
- Its raw row-grid lens swaps interpreted row-summary cells for the canonical raw payload preview while keeping the same structural coordinates and selected-row identity.
- Its document table is keyed by `version_hash`, while its selected-document row grid is keyed by `hyphae_hash`.
- Fresh entry deliberately prefers the first available CTS-GIS authoritative document in the current document ordering and falls back to the first available authoritative document when no CTS-GIS document is present.
- Its document and datum panes both carry sticky-header intent and explicit selected-document / selected-datum-row markers.
- Its datum grid may be grouped as `flat`, `layer`, or `layer_value_group` while preserving canonical structural order inside each group.
- Its source and overlay visibility remain query-driven.
- Its keyboard navigation stays query-driven through runtime-owned document/row selection actions rather than new canonical navigation keys.
- It is read-only in v1.
- It must never mutate authoritative datum rows.
- Any directive overlay is additive only and may be hidden without changing authoritative row content.

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
- `geospatial_projection` stays blank until the selected node or its widened intention scope resolves valid profile and HOPS evidence.
- node-focused widened intention keeps the selected node as the active profile while Garland may overlay multiple in-scope projectable source documents.
- Title fallback is blank-only when ASCII title decode is unavailable.
- In narrow posture, the CTS-GIS-local body may fall back to a vertical stack while preserving the same contract.
- CTS-GIS mediates on the selected anchor-file datum and projects correlated source-file evidence into the Interface Panel.
- CTS-GIS tool-local navigation does not widen the shared shell focus stack. The shell focus remains `sandbox -> file -> datum -> object`.
- Tool-local state is body-carried through CTS-GIS `tool_state`, not projected through new query keys.
- When a selected node is present and no explicit tool-local intention is supplied, CTS-GIS normalizes `Intention` to `self` so Garland reflects the current node.
- The `Control Panel` holds CTS-GIS-local directive, `AITAS`, and source-evidence controls.
- Node-focused Intention actions live inside `AITAS`; `Projection Rules` is shown only for sandbox-wide attention without a selected node.
- The workbench remains diagnostic or raw supporting evidence rather than a duplicate of Garland.
- v2.5.4 phase-B is canonical-only for CTS-GIS identifiers and storage anchors.
- Legacy CTS-GIS aliases are rejected at `POST /portal/api/v2/system/tools/cts-gis` with `400 legacy_maps_alias_unsupported`.

## FND-DCM

- `system.tools.fnd_dcm`

`FND-DCM` is one `SYSTEM` child service tool surface.

- Its canonical route is `/portal/system/tools/fnd-dcm`.
- Its default posture is interface-panel-led.
- Its workbench is hidden by default and reserved for secondary workbench content only.
- Its canonical query keys are:
  - `site`
  - `view`
  - `page`
  - `collection`
- It normalizes hosted-site manifests into one shared read model with fixed buckets:
  - `site`
  - `navigation`
  - `footer`
  - `pages`
  - `collections`
  - `issues`
  - `extensions`
- The `Control Panel` selects site and high-level view.
- The `Interface Panel` is the primary surface for overview, pages, collections, and issue projections.
- The workbench remains raw manifest JSON, collection-file metadata, and normalization evidence.
- `FND-DCM` is read-only in v1.
- It may remain visible while non-operational when `webapps_root` or required capabilities are missing.

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
- `workbench_ui` is the approved workbench-primary exception.
- Tool registry posture metadata is descriptive only; shell composition remains authoritative for first-load tool posture.
- Tool workbench visibility defaults to `false`.
- `workbench_ui` defaults to `true` because its primary surface is the SQL-backed datum grid.
- Tool surfaces use mutually exclusive single-click behavior between `Workbench` and `Interface Panel` by default.
- Double-clicking either tool toggle enables route-scoped lock mode that allows both panels to remain visible together.
- Tool lock is non-persistent and clears when leaving the current tool route or composition.
- Tool surfaces may still project secondary workbench content explicitly when lock mode is enabled.
- Tool configuration and exposure remain owned by `UTILITIES`.
- Service-tool posture is determined by configured capabilities and available peripherals or integrations, not by portal identity.
