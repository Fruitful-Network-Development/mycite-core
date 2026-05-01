# Desktop DM-02 + DM-04 Reconciliation Plan

Date: 2026-04-20

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-20`

## Purpose

Deliver a comprehensive implementation plan for the remaining high-priority desktop drift
items from the desktop report:

- `DM-02`: deep-link startup translation into one canonical shell request
- `DM-04`: scoped shell-state persistence policy for deterministic multi-window/session behavior

This plan focuses on rule clarity, execution sequencing, and modularized boundary ownership.

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/contracts/tool_mediation_surface_archetype.md`

## Source Evidence

- `docs/audits/reports/desktop_access_historical_drift_report_2026-04-16.md`
  - `DM-02` (deep-link startup translation)
  - `DM-04` (scoped persistence policy)

## Scope

Implementation scope:

- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`
- `MyCiteV2/instances/_shared/portal_host/static/portal.js`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- host integration boundaries where desktop startup context is injected

Test scope:

- `MyCiteV2/tests/contracts/**`
- `MyCiteV2/tests/integration/test_portal_host_one_shell.py`
- new desktop parity and shell-state persistence tests (to be added)

Out-of-scope for this plan:

- native accelerator ownership reconciliation (`DM-07`)
- integration process-health parity (`CI-09`)

## Rule Investigation Track (Required First)

### A) Startup deep-link rule investigation (`DM-02`)

For each startup entry mode (plain `/portal`, `/portal/system`, tool route with query):

1. Determine raw startup URL and host payload shape.
2. Define canonical translation to one shell request body.
3. Confirm translated request resolves to same canonical surface/query projection as web.
4. Confirm first render runs from translated shell request without intermediate non-canonical state.

Deliverable:

- startup translation matrix (`startup_input -> canonical shell request -> expected envelope`)

### B) Scoped persistence rule investigation (`DM-04`)

For each persisted shell-chrome value:

- panel widths/open state
- theme and display choices
- interface/workbench/control-panel collapse state

Define:

1. Scope key dimensions (`host`, `portal_instance_id`, `window/session`, `route group` as applicable)
2. Conflict policy (`last writer wins` with deterministic timestamp ordering)
3. Fallback policy when scoped persistence is unavailable
4. Migration policy from current unscoped localStorage keys

Deliverable:

- persistence policy table (`state_key`, `scope`, `conflict_rule`, `fallback_behavior`, `migration_rule`)

## Target Architecture

### 1) Deep-link translation shim

- Introduce a startup translator boundary that converts desktop bootstrap URL/context into a canonical shell request.
- Keep translation host-side or runtime-adapter-side; do not fork core state-machine semantics.
- Enforce one request authority: translated startup request must flow through existing shell endpoint/envelope path.

### 2) Scoped shell-state persistence provider

- Add a persistence abstraction in `portal.js` so storage read/write does not call global localStorage keys directly.
- Provider responsibilities:
  - compute scoped key namespace
  - read/write with graceful failure
  - expose migration read for legacy keys
  - apply deterministic conflict resolution metadata

## Phased Implementation Plan

### Phase 0 - Baseline and fixture capture

- Capture current startup and persistence behavior fixtures.
- Freeze expected canonical URL/query behavior for representative routes.
- Add baseline tests for current web behavior to avoid accidental semantic drift.

### Phase 1 - DM-02 implementation (translation shim)

- Implement startup translator for desktop launch context.
- Add contract/integration parity tests:
  - tool deep-link startup
  - system deep-link with query
  - plain `/portal` startup
- Validate same canonical `surface_id` and canonical query projection as web path.

### Phase 2 - DM-04 implementation (scoped persistence provider)

- Implement provider and migrate `portal.js` persistence call sites.
- Add deterministic conflict metadata and last-writer policy.
- Add tests for:
  - scoped isolation across sessions/windows
  - migration from legacy unscoped keys
  - unavailable storage fallback behavior

### Phase 3 - Hardening and documentation handoff

- Add architecture guard tests for no second routing/state authority.
- Update docs/contracts references where behavior was clarified.
- Publish closure notes in the desktop report.

## Validation Gates

1. **Contract parity gate**
   - canonical route/query projection parity between web and translated desktop startup requests.
2. **Persistence determinism gate**
   - concurrent/session-scoped write-read tests must produce deterministic outcomes.
3. **No second authority gate**
   - no new parallel startup routing logic bypassing canonical shell request resolution.
4. **Regression gate**
   - existing contract, adapters, and architecture suites remain green.

## Risks and Mitigations

1. **Host payload variability risk**
   - Mitigation: strict translator schema + explicit fallback to canonical system root.
2. **State migration regression risk**
   - Mitigation: dual-read migration window and compatibility tests.
3. **Persistence unavailability risk**
   - Mitigation: memory fallback with explicit degraded diagnostics.
4. **Cross-window nondeterminism risk**
   - Mitigation: scoped keys + deterministic timestamp and write ordering semantics.

## Exit Criteria

- `DM-02` translation matrix is implemented and test-backed.
- `DM-04` scoped persistence policy is implemented and test-backed.
- Desktop and web startup paths resolve through one canonical shell request authority.
- Desktop report is updated with closure evidence, remaining open items, and next follow-on scope.

