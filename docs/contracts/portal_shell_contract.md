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

Non-reducer roots may still project canonical query state when the host needs a stable read-only workbench lens. `NETWORK` uses raw `surface_query` projection keys for this purpose, while runtime remains the source of truth.

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
- Selecting a datum opens a read-only inspector lens inside the same workbench.
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
- The inspector projects the selected log record and any linked contract summary.
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

- The top menubar is the only shell header.
- There is no second workbench pagehead.
- The activity bar is icon-only.
- The left rail is the `Control Panel`.
- The right rail is the `Interface Panel`.
- The only persistent theme selector lives in the menubar.
- Surface labels are exposed through hover titles and accessibility labels, not persistent bar text.
- The control panel is the canonical textual navigation surface for current context and lower-focus selections.
- Shell static assets are versioned by `portal_build_id` through one embedded shell asset manifest.

## Tool Contract

- Tool work pages are `SYSTEM` child surfaces.
- `AWS-CSM` is the canonical AWS service tool surface under `SYSTEM`.
- `AWS-CSM` has one public route: `/portal/system/tools/aws-csm`.
- `AWS-CSM` uses runtime-owned query keys: `view`, `domain`, `profile`, `section`.
- `AWS-CSM` control-panel context is file-backed and projects:
  - `Sandbox: AWS-CSM`
  - `File: tool.<msn>.aws-csm.json`
  - `Mediation: spec.json`
- Tool configuration, enabling, exposure, integration state, vault, peripherals, and control surfaces belong under `UTILITIES`.
- Every tool registry entry defaults to `interface_panel_primary`.
- Every tool composition defaults to `regions.workbench.visible=false`.
- Secondary-evidence workbench content is explicit opt-in per tool runtime.
- A service tool may remain visible while `operational=false` when an external integration or required capability is missing.
- Service-tool posture comes from peripheral and integration availability, not from portal identity or portal "types".
- All tools attach to the same interface surface. Service-tool behavior is distinguished by whether the tool can employ the portal's authenticated peripheral package, not by a separate class of portal.

This is an interface-panel-led tool model, not a generic workbench page model.
