# Portal Shell Contract

The repository owns one neutral portal shell contract.

Canonical public entry: `/portal` -> `/portal/system`

## Behavioral Model

- One request schema: `mycite.v2.portal.shell.request.v1`
- One shell state schema: `mycite.v2.portal.shell.state.v1`
- One shell composition schema: `mycite.v2.portal.shell.composition.v1`
- One runtime envelope schema: `mycite.v2.portal.runtime.envelope.v1`
- One entrypoint descriptor schema: `mycite.v2.portal.runtime_entrypoint_descriptor.v1`

The shell state is reducer-owned only for:

- `system.root`
- reducer-owned `SYSTEM` child tool surfaces such as `system.tools.cts_gis` and `system.tools.fnd_ebi`

`AWS-CSM` is a `SYSTEM` child tool surface, but it is runtime-owned and query-driven rather than reducer-owned.

`/portal/network` and `/portal/utilities*` stay in the same host shell, but they do not participate in focus-path reduction.

Non-reducer roots may still project canonical query state when the host needs a stable read-only detail lens inside the workbench. `NETWORK` uses raw `surface_query` projection keys for this purpose, while runtime remains the source of truth.

## Ordered Focus Stack

The canonical shell state carries an ordered focus stack, not a bag of optional ids.

Order:

1. `sandbox`
2. `file`
3. `datum`
4. `object`

The contract-level anchor-file invariant is:

- a fresh reducer-owned `SYSTEM` entry seeds `file=anthology`

`back_out` is exact and deterministic:

- `object -> datum`
- `datum -> file`
- `file -> sandbox`
- `sandbox -> no-op`

Query state mirrors runtime-owned state. Runtime computes canonical next state and canonical next route/query. The URL is a projection of canonical state, not the source of truth.

## SYSTEM Workspace

`SYSTEM` is the core datum-file workbench for the system sandbox.

- It is not a generic dashboard or home page.
- Its default active file is the system sandbox anchor file, `anthology.json`.
- The anchor file is rendered as a layered datum table grouped by `layer` and `value_group`.
- Datum rows carry structural coordinates: `layer`, `value_group`, and `iteration`.
- Selecting a datum opens a read-only detail lens inside the same workbench.
- `activity` and `profile_basics` are workspace file modes under `/portal/system`, not first-class pages.
- The control panel projects current context first, then the selectable options below the current focus.
- Canonical context rows are file-backed and may include:
  - sandbox
  - file
  - datum
  - object
  - mediation subject
- Canonical lower-focus selections may include:
  - files when the user is at sandbox level
  - datums when the user is at file level
  - datum aspects or objects when the user is at datum level
- Verb switching remains a compact tab row inside the same control panel.
- The interface panel is mediation-owned.
- On `system.root`, `verb=mediate` opens the interface panel and binds it to the current mediation subject.

## NETWORK Workspace

`NETWORK` is the portal-instance system-log workbench.

- It is not a tool and not a sandbox.
- It is read-only and non-reducer-owned.
- Its canonical operational document is `data/system/system_log.json`.
- Contract correspondence is a filter over the same canonical system-log document, not a peer tab or child surface.
- The control panel projects:
  - one base view: `system_logs`
  - contract filters
  - event-type filters
- The workbench projects a chronological log table sorted by canonical HOPS timestamps.
- The Interface Panel projects the selected log record and any linked contract summary.
- The interface panel stays collapsed until selected-record focus exists.
- Canonical query keys for the root are:
  - `view`
  - `contract`
  - `type`
  - `record`
- `NETWORK` has no canonical Messages/Hosted/Profile/Contracts tab set in V2.

## UTILITIES Workspace

`UTILITIES` is the section-led configuration surface for shared portal controls.

- It is section-led rather than focus-depth-led.
- It is not a fake sandbox/file/datum/object stack.
- Its control panel uses the same modular selection-panel shell shape as the other roots.
- Its canonical context rows are `Root: UTILITIES` and `Section: <active section>`.
- Its selectable material is grouped under `Sections`.
- Its interface panel stays collapsed until a utilities surface explicitly projects detail there.

## Shell Chrome

- The top-level shell is `ide-shell`.
- `ide-shell` is divided into `ide-menubar` and `ide-body`.
- The top menubar is the only shell header.
- There is no second workbench pagehead.
- `ide-body` is the peer-region window for shell chrome.
- The peer shell regions inside `ide-body` are the `Activity Bar`, `Control Panel`, `Workbench`, and `Interface Panel`.
- Only the `Control Panel` and `Interface Panel` have explicit splitters and persisted width state.
- The activity bar is icon-only.
- The left rail is the `Control Panel`.
- The center region is the `Workbench`.
- The right rail is the `Interface Panel`.
- The only persistent theme selector lives in the menubar.
- Surface labels are exposed through hover titles and accessibility labels, not persistent bar text.
- The control panel is the canonical textual navigation surface for current context and lower-focus selections.
- Shell static assets are versioned by `portal_build_id` through one embedded shell asset manifest.

### Shell Composition Compatibility

- `shell_composition.inspector_collapsed` remains valid as the compatibility alias for the public `Interface Panel`.
- `shell_composition.interface_panel_collapsed` mirrors `inspector_collapsed`.
- `shell_composition.workbench_collapsed` reports whether the workbench is currently hidden.
- `shell_composition.regions.inspector` remains valid during the compatibility phase.
- `shell_composition.regions.interface_panel` mirrors `regions.inspector`.

## Tool Contract

- Tool work pages are `SYSTEM` child surfaces.
- `AWS-CSM` is the canonical AWS service tool surface under `SYSTEM`.
- `CTS-GIS` is the canonical structural/spatial mediation tool surface under `SYSTEM`.
- `AWS-CSM` has one public route: `/portal/system/tools/aws-csm`.
- `CTS-GIS` has one public route: `/portal/system/tools/cts-gis`.
- `AWS-CSM` uses runtime-owned query keys: `view`, `domain`, `profile`, `section`.
- `CTS-GIS` does not widen shell query. Its tool-local navigation and projection state is body-carried in the tool request/runtime payload.
- `AWS-CSM` control-panel context is file-backed and projects:
  - `Sandbox: AWS-CSM`
  - `File: tool.<msn>.aws-csm.json`
  - `Mediation: spec.json`
- `CTS-GIS` control-panel context is file-backed and projects:
  - `Sandbox: CTS-GIS`
  - `File: tool.<msn>.cts-gis.json` when the canonical anchor exists, otherwise the active compatibility anchor file
  - `Mediation: spec.json`
- Tool configuration, enabling, exposure, integration state, vault, peripherals, and control surfaces belong under `UTILITIES`.
- Every tool registry entry defaults to `interface_panel_primary`.
- Every tool composition defaults to `regions.workbench.visible=false`.
- Secondary-evidence workbench content is explicit opt-in per tool runtime.
- Tool surfaces may project both the `Workbench` and the `Interface Panel` at the same time when secondary evidence is explicitly shown; enabling the workbench does not automatically close the Interface Panel.
- A service tool may remain visible while `operational=false` when an external integration or required capability is missing.
- Service-tool posture comes from peripheral and integration availability, not from portal identity or portal "types".
- All tools attach to the same interface surface. Service-tool behavior is distinguished by whether the tool can employ the portal's authenticated peripheral package, not by a separate class of portal.

This is an interface-panel-led tool model, not a generic workbench page model.

### CTS-GIS Tool-Local State

- `CTS-GIS` remains reducer-owned only at the shell level. The shared shell focus stack stays:
  - `sandbox`
  - `file`
  - `datum`
  - `object`
- CTS-GIS-local structural navigation does not add a new shell depth below `object`.
- The canonical CTS-GIS request body may carry `tool_state`:
  - `tool_state.nimm_directive`
  - `tool_state.aitas.attention_node_id`
  - `tool_state.aitas.intention_rule_id`
  - `tool_state.aitas.time_directive`
  - `tool_state.aitas.archetype_family_id`
  - `tool_state.source.attention_document_id`
  - `tool_state.selection.selected_row_address`
  - `tool_state.selection.selected_feature_id`
- Legacy compatibility inputs remain accepted during the compatibility phase:
  - `mediation_state.attention_node_id`
  - `mediation_state.intention_token`
  - top-level `selected_row_address`
  - top-level `selected_feature_id`

### CTS-GIS NIMM/AITAS Crosswalk

- Shared shell AITAS stays minimal and unchanged.
- CTS-GIS adds a richer tool-local AITAS layer without widening the shared shell validator.
- CTS-GIS tool-local labels are:
  - `Attention` = current tool-local navigation root
  - `Intention` = current tool-local projection rule
  - `Time` = tool-local temporal directive
  - `Archetype` = tool-local structure-family directive
- CTS-GIS uses `nimm_directive` as a tool-local directive label inside the request/runtime payload. This is additive tool runtime state, not a widened shared shell directive contract.

### CTS-GIS Interface Body

- The dominant `tool_mediation_panel` mounts one CTS-GIS-local interface body.
- The CTS-GIS-local section titles are:
  - `Diktataograph`
  - `Garland`
- `Diktataograph` is the structural navigation section. It projects the current SAMRAS-defined address space and may overlay correlated names through the ASCII lens.
- `Garland` is the correlated profile section. It projects the current node’s profile and spatial evidence with respect to the supporting source file, preferably through the GeoJSON lens or equivalent runtime cache.
- These are not separate mediation operations. They are two CTS-GIS-local projections of one active mediation posture.
- In narrow posture, the same CTS-GIS-local sections fall back to a vertical stack with a compact CTS-GIS context strip above them.

### CTS-GIS Evidence Precedence

- Tool governance file: `private/utilities/tools/cts-gis/spec.json`
- Tool anchor file: `data/sandbox/cts-gis/tool.<msn>.cts-gis.json`
- Structural seed: registrar payload or payload cache
- Label evidence: supporting administrative payload cache through the ASCII lens
- Spatial evidence: GeoJSON lens or equivalent cache derived from payload/payload-cache material
- Legacy `maps` paths remain loadable as compatibility aliases, but `CTS-GIS` / `cts_gis` / `cts-gis` are the canonical public forms.
