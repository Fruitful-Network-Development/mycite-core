# Package Modularization Audit Report

Date: 2026-04-16  
Based on plan: `docs/audits/package_modularization_audit_plan_2026-04-16.md`

## Current status note — 2026-04-20 foundation-first pass

- **Closed in code / no longer reproducing:** the filesystem-adapter boundary failures called out in section 2 are historical; the active `test_filesystem_adapter_boundaries` suite is green in the current repo.
- **Still active and worth doing now:** low-cost boundary cleanup such as dead imports and other verified noise that does not widen the refactor scope.
- **Deferred:** the broader runtime/domain facade work and deeper package-boundary redesign remain outside this pass.
- **Maintenance-pass note (2026-04-20):** the local shell environment currently has no `pytest` binary/module, so this update records static import evidence and keeps full architecture-suite re-run as an explicit follow-up gate.
- **Closure update (2026-04-20, follow-up):** a dedicated architecture guardrail test now enforces that runtime modules do not import `MyCiteV2.packages.modules.domains.*.service` directly (`MyCiteV2/tests/architecture/test_runtime_package_boundary_contracts.py`).

## 1) Scope and Method

Scoped paths audited:

- `MyCiteV2/packages/**`
- `MyCiteV2/instances/_shared/runtime/**`

Execution method:

1. Ran architecture boundary test suite under `MyCiteV2/tests/architecture/`.
2. Parsed in-scope Python imports to build module and package dependency inventories.
3. Applied boundary checks from the plan:
   - contract-first imports
   - forbidden dependency enforcement
   - domain leakage detection
4. Ranked remediation proposals with score formula:
   - `Priority Score = (Impact × 2) + Blast Radius - Migration Cost`

Execution evidence timestamp: **2026-04-16T02:33:47Z (UTC)**.

---

## 2) Required Evidence Pointers (Architecture Tests)

Historical command run (original audit evidence):

- `pytest MyCiteV2/tests/architecture -q` (2026-04-16 baseline)

Current environment status (maintenance pass):

- `pytest` unavailable in shell (`command not found`)
- `python3 -m pytest` unavailable (`No module named pytest`)

Result summary:

- **Historical baseline:** 34 passed, 2 failed (kept for traceability).
- **Current pass:** runtime verification pending until test environment is provisioned.

Evidence pointers:

| Test file | Rule / test case identifier | Status | Notes |
|---|---|---:|---|
| `MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py` | `FilesystemAdapterBoundaryTests::test_imports_remain_adapter_side_without_module_semantics` | HISTORICAL FAIL / CURRENT REPORTED GREEN | Historical failure retained as original evidence; foundation-first status marks this as closed in active repo. |
| `MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py` | `FilesystemAdapterBoundaryTests::test_source_contains_no_local_audit_semantic_knowledge` | HISTORICAL FAIL / CURRENT REPORTED GREEN | Historical failure retained as original evidence; foundation-first status marks this as closed in active repo. |
| `MyCiteV2/tests/architecture/test_datum_recognition_domain_boundaries.py` | `DatumRecognitionDomainBoundaryTests::test_imports_remain_inward_and_adapter_free` | PASS | Domain boundary import direction preserved for datum recognition package. |
| `MyCiteV2/tests/architecture/test_publication_domain_boundaries.py` | `PublicationDomainBoundaryTests::test_imports_remain_inward_and_adapter_free` | PASS | Publication domain boundary direction preserved. |
| `MyCiteV2/tests/architecture/test_ports_audit_log_boundaries.py` | `AuditLogPortBoundaryTests::test_imports_remain_port_only_and_adapter_free` | PASS | Port contract separation holds for audit log. |
| `MyCiteV2/tests/architecture/test_datum_store_port_boundaries.py` | `DatumStorePortBoundaryTests::test_imports_remain_port_only` | PASS | Port-only boundary expectation holds for datum store package. |
| `MyCiteV2/tests/architecture/test_state_machine_boundaries.py` | `StateMachineBoundaryTests::test_imports_remain_inward_core_or_state_machine_only` | PASS | Layering for state machine package preserved. |
| `MyCiteV2/tests/architecture/test_local_audit_boundaries.py` | `LocalAuditBoundaryTests::test_imports_remain_inward_and_adapter_free` | PASS | Cross-domain local audit service remains inward-facing. |

---

## 3) Inventory Outputs

### 3.1 Current module dependency map

In-scope Python modules scanned: **103**  
In-scope imports (internal/runtime/package-relevant): **75**

#### Package-level directed dependency map

| From | To | Edge count | Boundary annotation |
|---|---|---:|---|
| adapters | core | 3 | Allowed by `packages/adapters/allowed_dependencies.md` |
| adapters | ports | 13 | Allowed by `packages/adapters/allowed_dependencies.md` |
| modules | core | 4 | Allowed by `packages/modules/allowed_dependencies.md` |
| modules | ports | 13 | Allowed by `packages/modules/allowed_dependencies.md` and domain sub-rules |
| state_machine | core | 1 | Allowed by `packages/state_machine/allowed_dependencies.md` |
| sandboxes | adapters | 1 | Indirect orchestration dependency; review in next sandbox audit cycle |
| runtime | state_machine | 7 | Runtime composition dependency |
| runtime | ports | 3 | Runtime composition dependency |
| runtime | adapters | 4 | Runtime concrete adapter wiring |
| runtime | modules | 8 | **Boundary risk: direct runtime → module service coupling** |
| runtime | instances | 11 | Runtime-local composition imports (not scored as package forbidden edge) |

Cycle check (package-level): **No bidirectional cycles detected**.

#### Module-level violation annotations (selected)

| Source module | Import edge | Check impacted | Annotation |
|---|---|---|---|
| `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py` | `MyCiteV2.packages.core.structures.hops.chronology` | Contract-first / adapter boundary | Deep concrete core-structure import from adapter. |
| `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py` | `MyCiteV2.packages.core.structures.hops.time_address` | Contract-first / adapter boundary | Deep concrete core-structure import from adapter. |
| `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py` | `MyCiteV2.packages.core.structures.hops.time_address_schema` | Contract-first / adapter boundary | Deep concrete core-structure import from adapter. |
| `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py` | `MyCiteV2.packages.modules.domains.datum_recognition.service` | Contract-first / domain leakage | Runtime imports concrete domain service implementation directly. |

### 3.2 Candidate split/merge proposals

| Proposal | Type | Rationale | Suggested owner |
|---|---|---|---|
| Extract event classification helpers (e.g., `_event_type`) from `adapters/filesystem/fnd_ebi_read_only.py` into a module-domain service surface or port contract helper | Split | Reduces semantic ownership leakage in adapters and aligns with architecture boundary tests. | Modules + Adapters owners |
| Introduce a published domain contract facade for datum workbench reads (consumed by runtime) and move runtime imports to that facade | Split + boundary realignment | Removes runtime reach-through into domain `.service` internals and improves contract-first composition. | Runtime + Modules owners |
| Consolidate HOPS transformation calls behind a port-level mapper consumed by `network_root_read_model` adapter | Merge/consolidate | Reduces deep core-structure import fan-out and stabilizes adapter API usage. | Ports + Adapters owners |

### 3.3 Anti-pattern list

- Deep-import coupling into core internals from adapters (`core.structures.hops.*`).
- Runtime-to-domain implementation reach-through (`runtime -> modules.domains.*.service`).
- Adapter semantic drift via domain token ownership in filesystem adapter (`event_type`).
- Contract drift risk where runtime composition bypasses explicit domain contract facades.

---

## 4) Boundary Check Results

### 4.1 Contract-first imports

**Status: CLOSED FOR REPORTED RISK ITEMS / CONTINUOUS GUARDRAILS ACTIVE**

Findings:

1. No active direct runtime import of `modules.domains.*.service` remains in the audited runtime path.
2. No active adapter import of `core.structures.hops` remains in the audited filesystem adapter path.
3. Remaining work is proactive boundary hygiene, not remediation of active report-era violations.

Evidence pointers:

- Static import scan and architecture guard test confirm the original contract-first violations are absent.
- Follow-up architecture guardrail: `MyCiteV2/tests/architecture/test_runtime_package_boundary_contracts.py`.

### 4.2 Forbidden dependency enforcement

**Status: PASS AT PACKAGE RULE LEVEL (with targeted module-level concerns)**

Findings:

- No explicit package-level forbidden edges detected under current markdown-deny constraints for packages (`core/modules/ports/adapters/state_machine/tools/sandboxes`).
- Existing architecture suite still catches module-level policy breaks (not all represented in package-level deny lists), notably in filesystem adapters.

Evidence pointers:

- `pytest MyCiteV2/tests/architecture -q` output: 34 pass / 2 fail.
- Failures isolated to filesystem adapter boundary tests.

### 4.3 Domain leakage detection

**Status: CLOSED FOR REPORTED RISK ITEMS / MONITORING CONTINUES**

Findings:

1. The prior filesystem-adapter semantic-token leak (`event_type`) is absent in active adapter sources.
2. Runtime domain-service reach-through is absent and now guarded by an explicit architecture test.

Evidence pointers:

- Import-shape evidence in scoped runtime/adapter modules.
- Targeted guardrail check passes via `python3 -m unittest MyCiteV2.tests.architecture.test_runtime_package_boundary_contracts -q`.

---

## 5) Ranked Remediation Table

Scoring formula: `Priority Score = (Impact × 2) + Blast Radius - Migration Cost`

### High Priority

| ID | Finding | Impact (1-5) | Migration Cost (1-5) | Blast Radius (1-5) | Priority Score | Owner | Suggested phase |
|---|---|---:|---:|---:|---:|---|---|
| R1 | Runtime/domain service-import guardrail enforcement | 4 | 1 | 2 | **9** | Runtime team + Architecture steward | Completed (guardrail added) |
| R2 | Preserve filesystem-adapter boundary no-leak posture | 4 | 1 | 2 | **9** | Adapters team + CI/test owners | In monitoring (existing boundary tests) |

### Medium Priority

| ID | Finding | Impact (1-5) | Migration Cost (1-5) | Blast Radius (1-5) | Priority Score | Owner | Suggested phase |
|---|---|---:|---:|---:|---:|---|---|
| R3 | Codify runtime import boundary policy in architecture tests/docs | 3 | 2 | 3 | **7** | Runtime team + Architecture steward | Phase 2 (policy codification) |
| R4 | Runtime import fan-out across modules/state machine/adapters without explicit runtime boundary contract doc | 3 | 2 | 4 | **8** | Runtime team + Architecture steward | Phase 2 (dependency policy codification) |

### Low Priority

| ID | Finding | Impact (1-5) | Migration Cost (1-5) | Blast Radius (1-5) | Priority Score | Owner | Suggested phase |
|---|---|---:|---:|---:|---:|---|---|
| R5 | Sandbox→adapter single edge review for long-term modular clarity | 2 | 2 | 2 | **4** | Sandboxes team | Phase 3 (backlog hygiene) |

---

## 6) Explicit Waivers

Current waiver register:

- **No approved waivers recorded as of 2026-04-16.**

Proposed waiver candidates:

- **None proposed in this report.**

Rationale:

- Remaining findings are mostly consolidation/drift-risk hardening work and are small enough to avoid formal waivers.

---

## 7) Recommended Execution Phasing

1. **Phase 1 (complete):** apply import-surface cleanup and add runtime boundary guardrail test against direct domain-service imports.
2. **Phase 2:** introduce/standardize facades for deep core structure usage and formalize runtime dependency rules as test-enforced contracts.
3. **Phase 3:** cleanup lower-risk dependency hygiene items (sandbox edge review, additional anti-pattern guards) and publish a brief closeout delta.

## 8) Exit Criteria for Re-audit

- Runtime boundary guardrail test passes: `python3 -m unittest MyCiteV2.tests.architecture.test_runtime_package_boundary_contracts -q`.
- Local environment can execute `pytest MyCiteV2/tests/architecture -q` and returns all pass (pending environment setup).
- No contract-first violations in runtime import scan.
- No domain semantic token leakage in adapters.
- Updated inventory map shows reduced deep-import edges and explicit contract surfaces for runtime composition.
