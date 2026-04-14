# Portal Shell Contract

The repository owns one neutral portal shell contract.

## Behavioral Model

- One request schema: `mycite.v2.portal.shell.request.v1`
- One shell state schema: `mycite.v2.portal.shell.state.v1`
- One shell composition schema: `mycite.v2.portal.shell.composition.v1`
- One runtime envelope schema: `mycite.v2.portal.runtime.envelope.v1`
- One entrypoint descriptor schema: `mycite.v2.portal.runtime_entrypoint_descriptor.v1`

The shell state is reducer-owned only for:

- `system.root`
- `system.tools.*`

`/portal/system/operational-status`, `/portal/network`, and `/portal/utilities*` stay in the same host shell, but they do not participate in focus-path reduction.

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
- The control panel is a stacked focus panel:
  - sandbox
  - file
  - datum/object
  - current intention
- The interface panel is mediation-owned.
- On `system.root`, `verb=mediate` opens the interface panel and binds it to the current mediation subject.

## Tool Contract

- Tool work pages are `SYSTEM` child surfaces.
- Tool configuration, enabling, exposure, integration state, vault, peripherals, and control surfaces belong under `UTILITIES`.
- Every tool registry entry defaults to `interface_panel_primary`.
- Every tool composition defaults to `regions.workbench.visible=false`.
- Secondary-evidence workbench content is explicit opt-in per tool runtime.
- A service tool may remain visible while `operational=false` when an external integration or required capability is missing.
- Service-tool posture comes from peripheral and integration availability, not from portal identity or portal "types".

This is an interface-panel-led tool model, not a generic workbench page model.
