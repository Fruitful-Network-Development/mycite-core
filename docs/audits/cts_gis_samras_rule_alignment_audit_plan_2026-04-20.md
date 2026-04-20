# CTS-GIS SAMRAS Rule Alignment Audit Plan

Date: 2026-04-20

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-20`

## Purpose

Define a repeatable SAMRAS-focused audit that investigates structural and mutation rules,
then verifies all SAMRAS-related behavior is aligned with the current one-shell operation
conventions and modularization boundaries.

## Scope

Primary contract scope:

- `docs/contracts/cts_gis_samras_addressing.md`
- `docs/contracts/samras_structural_model.md`
- `docs/contracts/samras_validity_and_mutation.md`
- `docs/contracts/samras_engine_ui_boundary.md`

Primary implementation scope:

- `MyCiteV2/packages/core/structures/samras/**`
- `MyCiteV2/packages/modules/cross_domain/cts_gis/**`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`

Related data scope:

- `deployed/fnd/data/sandbox/cts-gis/tool.*.cts-gis.json`
- `deployed/fnd/data/sandbox/cts-gis/sources/*.json`
- `deployed/fnd/data/payloads/cache/*.msn-administrative.json`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/contracts/cts_gis_samras_addressing.md`
- `docs/contracts/samras_structural_model.md`
- `docs/contracts/samras_validity_and_mutation.md`
- `docs/contracts/samras_engine_ui_boundary.md`

## Rule Investigation Workstreams

### 1) Structural rule investigation

Validate and document rule behavior for:

- magnitude decode paths (canonical and compatibility)
- breadth-first namespace derivation
- root/child continuity and contiguity
- stop-address and value-stream invariants
- fail-closed conditions

Deliverable:

- structural rule matrix with `expected`, `observed`, `aligned`, `drift_class`.

### 2) Mutation rule investigation

Validate and document rule behavior for:

- add/remove/move branch operations
- canonical regeneration after mutation
- workspace reconstruction from row overlays
- compatibility mutation pathways vs canonical pathways

Deliverable:

- mutation invariants checklist with pass/fail evidence per operation family.

### 3) CTS-GIS mediation rule investigation

Validate and document:

- attention/intention normalization behavior
- navigation canvas decode states and diagnostics
- Garland coupling to selected SAMRAS node
- profile/geospatial count consistency under widened intentions

Deliverable:

- mediation + projection parity report for representative user flows.

## Paradigm Alignment Gates

All findings and proposed fixes must satisfy:

1. **Single authority gate**
   - SAMRAS structure authority remains unique and explicit.
2. **One-shell gate**
   - No SAMRAS fix may introduce parallel routing/state authority.
3. **Contract-first gate**
   - Rule changes must update contracts or be clearly marked as compatibility behavior.
4. **Fail-closed gate**
   - Invalid structure states must produce deterministic blocked/degraded outputs with diagnostics.

## Modularization Alignment Gates

1. Keep structural decode/mutation logic inside core SAMRAS package boundaries.
2. Keep CTS-GIS service as orchestrator/consumer, not structural-rule owner.
3. Keep adapter/runtime code from importing private SAMRAS internals without contract surfaces.
4. Consolidate repeated rule helpers into shared/core utilities where semantics are truly common.

## Evidence Requirements

For each investigated rule family:

- contract citation
- code-path citation
- fixture/data sample
- observed output snapshot
- drift classification (`preserved`, `narrowed`, `broken`, `obsolete`)
- remediation decision (`keep`, `restore`, `shim`, `retire`)

## Phases

1. **Phase 0 - Baseline capture**
   - freeze current contracts + representative fixture outputs.
2. **Phase 1 - Rule inventory and drift matrix**
   - produce structural/mutation/mediation rule matrices.
3. **Phase 2 - Targeted remediation**
   - apply highest-risk rule fixes with tests.
4. **Phase 3 - Hardening**
   - add architecture/contract guardrails for repeated drift risks.

## Exit Criteria

- Structural, mutation, and mediation rule matrices are complete.
- All high-severity SAMRAS rule drifts are resolved or explicitly waived.
- Contract, unit, and architecture tests covering SAMRAS flows are green.
- Findings include explicit modularization alignment outcomes and remaining debt list.

