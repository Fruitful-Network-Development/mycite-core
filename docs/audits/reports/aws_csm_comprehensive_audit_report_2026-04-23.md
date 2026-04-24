# AWS-CSM Comprehensive Audit Report

Date: 2026-04-23

Doc type: `audit-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Initiative and Task Mapping

- Initiative: `INIT-AWS-CSM-ALIGNMENT`
- Task IDs:
  - `TASK-AWS-CSM-ALIGN-001`
  - `TASK-AWS-CSM-ALIGN-002`
  - `TASK-AWS-CSM-ALIGN-003`
  - `TASK-AWS-CSM-ALIGN-004`

## Scope and Method

This report captures the comprehensive 2026-04-23 audit of AWS-CSM against the
portal operating model (authority separation, route/query contracts, posture,
and mutation boundaries), plus cross-tool parity expectations for adapters,
fallback semantics, navigation behavior, and performance posture.

## Conformance Confirmed

1. **Authority separation is largely intact**
   - Shell controls route/posture/regions.
   - Runtime owns authoritative state and action dispatch.
   - UI renderers remain mostly projection-only and invoke action endpoints for mutation.
2. **Canonical route/query and action contracts are in use**
   - Route and query keys (`view`, `domain`, `profile`, `section`) align with current contract documentation.
   - Action execution remains isolated to explicit action contracts and service modules.
3. **Interface-panel-primary posture is respected**
   - AWS-CSM workbench remains hidden by default while inspector/control surfaces remain active.
4. **Onboarding widget and grouped domain/profile views are present**
   - Domain, mailbox, onboarding, and newsletter surfaces are rendered with canonical query-driven navigation.

## Material Misalignments

1. **NIMM/AITAS gap for AWS-CSM actions**
   - AWS-CSM onboarding actions remain bespoke service calls rather than directive-driven NIMM scripts with explicit AITAS context.
2. **Duplicate projection logic in renderer**
   - AWS renderer recomputes profile/newsletter fact rows client-side instead of consuming normalized runtime projections.
3. **Shared adapter and fallback parity drift**
   - Tool-specific helpers and inconsistent empty/loading/error semantics introduce cross-tool behavior drift and testing overhead.
4. **Reducer ownership and navigation-path asymmetry**
   - AWS-CSM remains reducer-unowned and depends on direct shell load patterns, diverging from reducer-owned tool transition semantics.
5. **Cross-domain user grouping contract is incomplete**
   - Current model centers selection under one domain and does not yet define top-level cross-domain user grouping semantics.
6. **Monolithic renderer performance pressure**
   - Full-fragment rerenders/event rebinding and utility duplication align with known performance backlog risks.

## Task-Aligned Remediation Plan

### `TASK-AWS-CSM-ALIGN-001` (in progress)

Publish canonical stream assets and synchronize contextual + compatibility YAML
surfaces (manifest, task board, README entrypoints, and report anchors).

### `TASK-AWS-CSM-ALIGN-002` (done)

Define AWS-CSM NIMM/AITAS mutation contract:

- canonical directive grammar for onboarding operations
- envelope/context requirements
- route and operating-contract deltas
- validation scope for unit/integration/contract tests

Delivered draft:

- Canonical directive mapping documented in `docs/contracts/route_model.md`
  and `docs/contracts/tool_operating_contract.md`.
- Canonical action envelope posture defined as:
  `mycite.v2.nimm.envelope.v1` + `directive.target_authority=aws_csm` +
  `directive.payload.action_kind/action_payload` + required AITAS fields.

### `TASK-AWS-CSM-ALIGN-003` (done)

Define cross-domain user grouping model:

- top-level query semantics (for example `view=users`)
- runtime-projected grouped user rows and selection contracts
- preservation of read-only navigation + action-contract-only mutation

Delivered draft:

- Cross-domain grouping query keys (`view=users`, `user_group`, `user`) are now
  documented in `docs/contracts/route_model.md`.
- Runtime projection shape and read-only navigation posture are documented in
  `docs/audits/aws_csm_operating_alignment_audit_plan_2026-04-23.md`.

### `TASK-AWS-CSM-ALIGN-004` (done)

Execute parity hardening:

- remove duplicate AWS projection helpers in favor of shared adapter-fed projections
- align fallback/loading/error semantics to shell wrappers
- unify selection/navigation request construction behavior
- add regression checks for query-state parity and renderer parity

Delivered:

- AWS workspace renderer now reports shared wrapped-surface empty-state posture via
  adapter `resolveSurfaceState` with explicit `hasContent` checks.
- AWS inspector renderer now uses parity-aligned no-selection empty-state handling
  instead of forcing content mode for every payload.
- Query-state navigation continues through canonical `buildDirectSurfaceRequest`
  helper with explicit domain/profile/section clear semantics.
- Regression guard added in
  `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py` to enforce
  adapter parity tokens and canonical query-clear request wiring.

## Lifecycle and Consolidation Notes

- Decision: **new stream added**, not a supersession of existing active streams.
- Existing reports remain retained for historical and cross-stream traceability.
- No historical artifact was deleted; previous anchors remain available.

## Evidence Targets

- `docs/audits/aws_csm_operating_alignment_audit_plan_2026-04-23.md`
- `docs/audits/reports/tools_ui_implementation_mismatch_report_2026-04-16.md`
- `docs/audits/reports/performance_weight_speed_report_2026-04-16.md`
- `docs/contracts/route_model.md`
- `docs/contracts/tool_operating_contract.md`

## Validation Log

Validation commands executed for this system update:

- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_aws_route_sync`

Results:

- `test_contract_docs_alignment`: pass (13 tests)
- `test_state_machine_boundaries`: pass (2 tests)
- `test_portal_aws_route_sync`: pass
