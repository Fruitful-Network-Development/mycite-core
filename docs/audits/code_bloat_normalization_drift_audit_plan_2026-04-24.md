# Code Bloat Normalization Drift Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-006`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Find duplicated request, route, query, renderer, lens, and action-normalization
helpers that create code bloat, behavioral drift, and security ambiguity.

## Goes Further Than Diagnosis

The diagnosis calls out inconsistent normalization. This plan requires a
contract-linked helper inventory, equivalence fixtures, compatibility alias
review, and consolidation ownership rules before recommending shared helpers.

## Evidence Targets

- `docs/contracts/route_model.md`
- `docs/contracts/mutation_contract.md`
- `docs/contracts/tool_operating_contract.md`
- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/`
- `MyCiteV2/packages/state_machine/`
- `MyCiteV2/instances/_shared/portal_host/static/`

## Audit Procedure

1. Search for normalization, canonicalization, query parsing, action mapping,
   renderer adaptation, and lens/value transformation helpers.
2. Group helpers by input contract, output shape, authority layer, and owning
   tool/domain.
3. Build equivalence fixtures for helpers that claim similar behavior.
4. Identify duplicates that are safe to consolidate, aliases that must remain,
   and divergences that are intentionally domain-specific.
5. Review security/correctness implications of current drift, including route
   widening, action authorization, and secret-bearing value handling.
6. Define canonical helper ownership and regression gates for each consolidation
   candidate.

## Acceptance Criteria

- Audit output maps duplicate helpers to contracts and authority owners.
- Consolidation recommendations include fixtures and compatibility posture.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-006` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
