# One-Shell Portal Refactor

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Objective

Aggressively drive the portal back to a stable one-shell operating model where extension happens through canonical state and widget contracts, not shell branching.

## Canonical Anchors

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/tool_operating_contract.md`

## Non-Negotiable Freeze Rules

Effective immediately for active refactor work:

- no new shell regions
- no new shell-level renderer kinds for single tools
- no new parallel posture authority outside `build_shell_composition_payload()`
- no query widening for CTS-GIS tool-local navigation
- no feature PR that bypasses canonical request/query normalization

If a change needs an exception, it must include:

- explicit contract delta
- compatibility window
- retirement gate

## Stability Program (Aggressive Sequence)

### Wave 0 (48 hours): Stop drift now

Goal:

- stop new divergence while migration lands

Required actions:

- enforce PR checklist gate against the freeze rules above
- require every tool-facing shell edit to cite `tool_operating_contract.md`
- flag any new `surface_payload.kind` shell branch as a blocking review issue
- freeze terminology to `Interface Panel` public naming, with alias usage only where compatibility requires it

Exit:

- no net-new shell branch families added during the wave

### Wave 1 (Week 1): Centralize shell authority

Goal:

- make shell composition the single authority for first-load posture

Required actions:

- enforce first-load visibility/posture only in `build_shell_composition_payload()`
- remove or neutralize competing first-load posture decisions in runtime bundle paths
- assert `workbench_ui` as the only approved `workbench_primary` exception
- ensure non-`workbench_primary` tools normalize to hidden workbench on first composition

Suggested verification targets:

- composition tests in shell runtime path
- route matrix spot checks for `/portal/system`, `/portal/system/tools/cts-gis`, `/portal/system/tools/workbench-ui`

Exit:

- one posture authority path for first composition

### Wave 2 (Week 2): Unify normalization boundary

Goal:

- remove request/query drift caused by duplicated normalization logic

Required actions:

- route shell request/query normalization through one shared helper layer
- remove duplicate per-surface normalization branches where possible
- enforce runtime-owned query ownership for runtime-owned surfaces
- enforce reducer-owned projection keys for reducer-owned surfaces
- enforce CTS-GIS anti-query-widening centrally

Exit:

- one normalization path is exercised for all shell routes

### Wave 3 (Week 3): Normalize region payload families

Goal:

- make region dispatch generic across tools

Required actions:

- adapt existing region payloads to:
  - `reflective_workspace`
  - `directive_panel`
  - `presentation_surface`
- keep compatibility adapters for legacy payload structures during cutover
- remove direct coupling between tool identity and shell dispatcher branching

Exit:

- shell dispatch keyed by region family, not tool identity

### Wave 4 (Week 4): Stabilize universal widget host

Goal:

- keep interface richness while eliminating composition drift

Required actions:

- establish one interface widget registry with stable widget ids
- standardize layout containers and slot rules in the interface panel
- normalize wrapper states (`loading`, `error`, `empty`, `unsupported`) through shared adapters
- keep tool-local semantics in runtime payloads, not in shell branch logic

Exit:

- new interface features land as widget additions, not shell renderer variants

## 30-Day Deliverables

- one shell posture authority path
- one normalization path for request/query handling
- three canonical region payload families active in shell dispatch
- one interface widget registry and wrapper policy
- shell-boundary contract matrix tests for canonical routes

## Contract Matrix (Must Pass)

For each canonical route:

- canonical URL and query projection
- canonical state owner (`reducer-owned` vs `runtime-owned`)
- first-load visible regions
- expected region family per region
- allowed directive actions

Initial required route set:

- `/portal/system`
- `/portal/system/tools/aws-csm`
- `/portal/system/tools/cts-gis`
- `/portal/system/tools/fnd-dcm`
- `/portal/system/tools/workbench-ui`
- `/portal/network`
- `/portal/utilities`

## Execution Discipline

- run this plan as a stability-first sequence, not a parallel feature stream
- treat drift regressions as blocking defects, not polish
- prefer additive compatibility adapters during migration, then retire on explicit gates
- every merged refactor change updates contract docs and tests in the same PR

## Open Task Notes

### CTS-GIS environment/data-sensitive failures

Status:

- known and tracked during stabilization waves

Observed:

- portions of `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py` fail intermittently or context-sensitively depending on CTS-GIS supporting evidence and compiled-state conditions
- representative mismatch pattern: readiness/decoded navigation expectations (`ready`) versus runtime fallback states (`compiled_state_invalid`, `blocked_invalid_magnitude`)

Immediate handling:

- treat these as tracked environment/data-sensitive failures, not as blockers for shell posture/normalization hardening
- keep Wave 1 and Wave 2 regression gates focused on shell-composition authority and normalization invariants

Follow-up task:

- create a dedicated CTS-GIS fixture hardening pass to make data/compiled prerequisites explicit and deterministic for workspace-runtime behavior tests
- do not relax shell contracts to satisfy unstable CTS-GIS fixture assumptions

## Result Target

The portal remains unique in state model (HANUS + interface-surface mediation + NIMM-AITAS) while becoming operationally predictable:

- shell is narrow and fixed
- runtime is canonical state authority
- widgets provide expressive extensibility

This restores stability without sacrificing the state-machine vision.
