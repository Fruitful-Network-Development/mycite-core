# Tool Operating Contract

## Status

Canonical

## Purpose

Define one stable operating contract for all portal tools so extension remains possible without shell-level drift.

This contract preserves HANUS, interface-surface mediation, and NIMM-AITAS by constraining where each concern is allowed to live.

## Fixed Shell Model

The shell is one host layout with four peer regions inside `ide-body`:

- `Activity Bar`
- `Control Panel`
- `Workbench`
- `Interface Panel`

Tools do not create parallel shells.

`inspector` remains a compatibility alias for `Interface Panel` until schema alias retirement.

## Region Families

Shell region dispatch is constrained to three canonical payload families:

- `reflective_workspace`
- `directive_panel`
- `presentation_surface`

These families are shell-level contracts. Tool-specific semantics must be expressed as content inside these families, not as new shell dispatcher branches.
Retired scoped fallback keys are outside this operating contract.

### `reflective_workspace`

The workbench is the reflective plane for backing documents and structural evidence.

Required shape:

- canonical document set metadata
- selected document identity
- selected row/object identity
- structural coordinates for rows/objects
- optional additive overlays as explicit evidence

The workbench must remain read-focused unless a separate mutation contract explicitly allows writes.

### `directive_panel`

The control panel is the state recap plus legal-transition plane.

Required shape:

- current canonical context rows
- available directives for current state
- next legal selections
- dispatchable request payloads for every actionable entry

The control panel does not infer transitions client-side.

### `presentation_surface`

The interface panel is a presentation host for free-form tool-local views built from shared widget contracts.

Required shape:

- layout container intent
- widget descriptors with stable type ids
- canonical widget props and action descriptors
- normalized loading/error/empty wrappers

Tool-local richness is allowed here, but composition rules and wrapper behavior must remain uniform.

## Authority Boundaries

### Shell owns

- route/state synchronization
- region orchestration
- directive dispatch
- first-load region visibility/posture application

### Runtime owns

- canonical state calculation
- canonical query and URL projection
- region payload generation
- tool-local normalization and boundary enforcement

### Widgets own

- presentation only
- local interaction state that does not change canonical shell/runtime state

## Posture and Visibility Invariant

`build_shell_composition_payload()` is the sole authority for region posture and first-response visibility.

Rules:

- tool registry posture metadata is descriptive, not authoritative
- non-`workbench_primary` tools default to hidden workbench on first composition
- `workbench_ui` remains the approved `workbench_primary` exception
- runtime bundles may project secondary workbench evidence but must not override first-load posture authority

## Request and Query Normalization Invariant

All shell request/query normalization must pass through one shared normalizer layer before runtime handling.

Rules:

- no duplicated normalization branches per surface
- reducer-owned surfaces preserve shared focus-stack projection keys
- runtime-owned surfaces preserve canonical query ownership
- CTS-GIS tool-local state stays body-carried; shell query is not widened for tool-local navigation
- anti-query-widening is enforced by runtime normalization, not by renderer convention

## Universal Tool Surface Invariant

Every tool surface must be executable through one universal operating path:

- canonical route under `/portal/system/tools/<tool_slug>`
- canonical shell request through `POST /portal/api/v2/shell`
- optional direct tool endpoint for tool-specific actions
- one runtime envelope with shell state, shell composition, and region payloads
- region payloads confined to `reflective_workspace`, `directive_panel`, and `presentation_surface`

## Extension Rule

To add capability, prefer one of:

- add a widget type in the interface widget registry
- extend reflective workspace document/row schema additively
- extend directive panel action descriptor vocabulary additively

Do not add:

- a new shell region
- a new shell-level renderer kind for one tool
- a second posture authority path

## Migration Program

### Phase 1: Lock shell authority

- enforce first-load region posture only in shell composition
- remove posture overrides from runtime bundles

### Phase 2: Unify region contracts

- adapt current tool payloads into the three canonical region families
- retire compatibility adapters once the family-first hosts are green and retired scoped fallback keys no longer appear in runtime or client code

### Phase 3: Unify normalization

- route all shell request/query normalization through one helper
- enforce CTS-GIS anti-query-widening and runtime-owned query boundaries centrally

### Phase 4: Build shared widget registry

- host interface panel content through stable widget descriptors and layout containers
- normalize fallback wrappers (`loading`, `error`, `empty`, `unsupported`) through shared adapters

### Phase 5: Remove legacy specialization

- delete per-tool shell dispatcher branches replaced by canonical families
- retire compatibility aliases after documented cutover gates

## Contract Test Matrix

Each canonical route must be covered by shell-boundary matrix tests asserting:

- canonical URL and query projection
- canonical state owner (reducer-owned vs runtime-owned)
- visible regions on first composition
- region payload family for each region
- allowed directive action set

This matrix is the regression guard against drift between shell, runtime, and tool renderers.
