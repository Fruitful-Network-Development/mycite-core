# CTS-GIS Datum Handling Alignment Audit Plan

Date: 2026-04-20

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-20`

## Purpose

Define the highest-priority audit for datum handling end-to-end: datum files,
source files, ordering/editing behavior, MSS form interactions, hyphae/address
semantics, and cross-surface consistency with current operation conventions and
modularized architecture boundaries.

## Scope

Data and artifact scope:

- `deployed/fnd/data/system/anthology.json`
- `deployed/fnd/data/system/system_log.json`
- `deployed/fnd/data/sandbox/cts-gis/tool.*.cts-gis.json`
- `deployed/fnd/data/sandbox/cts-gis/sources/*.json`
- `deployed/fnd/data/sandbox/cts-gis/sources/precincts/*.json`
- `deployed/fnd/data/payloads/cache/*.json`

Core implementation scope:

- `MyCiteV2/packages/ports/datum_store/**`
- `MyCiteV2/packages/adapters/filesystem/live_system_datum_store.py`
- `MyCiteV2/packages/modules/domains/datum_recognition/**`
- `MyCiteV2/packages/modules/cross_domain/cts_gis/**`
- `MyCiteV2/packages/core/datum_refs.py`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/contracts/cts_gis_samras_addressing.md`
- `docs/contracts/cts_gis_hops_profile_sources.md`
- `docs/contracts/samras_structural_model.md`
- `docs/contracts/samras_validity_and_mutation.md`

## Rule Investigation Workstreams

### 1) Datum identity and addressing rules

Investigate and validate:

- canonical datum identity shape vs aliases
- hyphae/delimiter normalization and canonical write format
- MSS form interactions and transformations
- node/document reference qualification rules

Deliverable:

- datum identity rule matrix with canonical/compatibility paths and ambiguity risks.

### 2) Datum file and source file handling rules

Investigate and validate:

- precedence between `tool` file, `sources` files, and payload cache
- source-document selection and pin behavior
- reconciliation rules when sources conflict
- fallback behavior when source records are missing/invalid

Deliverable:

- source precedence and reconciliation policy map with evidence fixtures.

### 3) Ordering and editing rules

Investigate and validate:

- deterministic ordering for datum rows and projection outputs
- edit path consistency for add/update/remove flows
- write-read parity across adapters and module projections
- no hidden reordering that changes semantic meaning

Deliverable:

- ordering/editing invariants checklist with pass/fail and counterexample records.

### 4) Projection and runtime consistency rules

Investigate and validate:

- file-level changes propagate deterministically into runtime projections
- Garland/geospatial/profile projections stay count-consistent
- diagnostics are explicit when data is degraded or blocked

Deliverable:

- runtime parity report for representative datum editing and navigation flows.

## Paradigm Alignment Gates

1. **One-shell authority**
   - Datum-handling changes cannot introduce alternate route/state authorities.
2. **Contract-first behavior**
   - Normative datum handling rules must be contract-linked and test-backed.
3. **Deterministic operation**
   - Same input files and commands produce same ordering/projection outputs.
4. **Compatibility containment**
   - Legacy forms (including MSS compatibility paths) are explicitly isolated and warning-instrumented.

## Modularization Alignment Gates

1. Datum semantics remain domain/core-owned; adapters only marshal I/O.
2. Cross-domain service modules consume contracts, not adapter internals.
3. Shared normalization helpers are centralized; no repeated local rule forks.
4. Boundary tests enforce no runtime reach-through into private domain implementation paths.

## Verification Matrix

For every rule finding, include:

- severity: `critical|high|medium|low`
- drift class: `preserved|narrowed|broken|obsolete`
- evidence pointer:
  - contract section
  - code path
  - data fixture
  - test path/result
- remediation type: `keep|restore|shim|retire`
- owner and target phase

## Phases

1. **Phase 0 - Baseline and inventory**
   - catalog datum/source file classes and current edit/read pathways.
2. **Phase 1 - Rule drift analysis**
   - complete identity, source, ordering/editing, and projection matrices.
3. **Phase 2 - Critical remediation**
   - close critical/high drifts with focused tests.
4. **Phase 3 - Modular hardening**
   - enforce boundaries and helper consolidation to prevent re-drift.

## Exit Criteria

- All critical/high datum-handling drifts are closed or explicitly waived.
- Canonical datum identity/order/editing rules are documented and test-backed.
- Compatibility paths for MSS/historical forms are explicit, bounded, and warning-instrumented.
- Contracts/adapters/architecture suites touching datum handling are green.
- Remaining technical debt has named owners and closure timeline.

