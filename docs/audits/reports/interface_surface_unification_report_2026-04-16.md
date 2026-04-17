# Interface Surface Unification Audit Report

Date: 2026-04-16  
Plan executed: `docs/audits/interface_surface_unification_audit_plan_2026-04-16.md` (sections 1–3 + section 4 matrix + section 5 backlog conversion)

## Scope and evidence base

Primary contract baselines:
- `docs/contracts/surface_catalog.md`
- `docs/contracts/route_model.md`
- `docs/contracts/portal_shell_contract.md`

Primary implementation evidence:
- `MyCiteV2/packages/state_machine/portal_shell/shell.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
- `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py`
- `MyCiteV2/instances/_shared/portal_host/static/portal.js`
- `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- `MyCiteV2/tests/contracts/test_contract_docs_alignment.py`
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`

---

## 1) Surface model checks (`surface_catalog.md`)

### 1.1 Canonical surface inventory

**Result: Pass with one guardrail gap (S2).**

Validated:
- First-class surface catalog in runtime includes exactly:
  - `system.root`
  - `system.tools.aws_csm`
  - `system.tools.cts_gis`
  - `system.tools.fnd_ebi`
  - `network.root`
  - `utilities.root`
  - `utilities.tool_exposure`
  - `utilities.integrations`
  - Evidence: `build_portal_surface_catalog` in `shell.py` lines 630–700.
- Retired `activity` / `profile_basics` are not first-class surfaces and remain file modes.
  - Evidence: contracts + `SYSTEM_ACTIVITY_FILE_KEY` / `SYSTEM_PROFILE_BASICS_FILE_KEY` usage as file tokens.

Gap G-07 (S2):
- **Invariant at risk:** retired naming drift prevention is primarily test-based; no runtime assertion directly rejects legacy route/surface aliases before normalization.
- **Evidence pointers:** architecture test is currently the main active guardrail (`test_active_repo_text_does_not_reference_retired_split_routes`), while runtime catalog simply omits old entries.
- **Impact:** nomenclature drift risk, low immediate runtime breakage.

### 1.2 Root-vs-tool posture defaults

**Result: Mostly pass; one behavioral hardening gap (S1).**

Validated:
- Tool registry defaults are interface-panel-led with workbench default hidden (`default_workbench_visible=False`).
  - Evidence: `build_portal_tool_registry_entries` and `PortalToolRegistryEntry.default_workbench_visible`.
- AWS/CTS/FND tool bundles currently set workbench `visible: False`.
  - Evidence: tool runtimes.

Gap G-01 (S1):
- **Invariant violated/risky:** contract requires posture semantics as a shell invariant, but composition builder does not enforce tool workbench-hidden default; it trusts incoming region payload.
- **Evidence pointers:**
  - `build_shell_composition_payload` sets `workbench_region.setdefault("visible", True)`.
  - `apply_surface_posture_to_composition` only sets `foreground_shell_region`, not region visibility normalization.
- **Impact:** future runtime drift can silently violate root/tool posture contract.

### 1.3 Tool-local behavior boundaries

**Result: Pass with one hardening gap (S1).**

Validated:
- AWS query model is runtime-owned (`view/domain/profile/section`) and canonicalized by `canonical_query_for_surface_query`.
- CTS-GIS tool-local state remains body-carried (`tool_state`) and not widened into shell URL query.
- Activity bar behavior is icon-first in chrome/template.

Gap G-04 (S1):
- **Invariant at risk:** CTS-GIS boundary is implemented across multiple layers (`shell.py`, shell runtime routing, CTS service) but without a single end-to-end guard that rejects accidental query widening at shell entry.
- **Evidence pointers:**
  - `canonical_query_for_surface_query` returns `{}` for CTS-GIS (good), but enforcement is indirect.
  - CTS-GIS request normalization and read flow rely on runtime/service paths.
- **Impact:** medium risk of regression when future query handling evolves.

---

## 2) Route/query consistency checks (`route_model.md`)

### 2.1 Canonical route set

**Result: Pass with no S0 breaks found.**

Validated:
- Canonical routes for system/network/utilities and utilities children are present.
- Tool route pattern `/portal/system/tools/<tool_slug>` is respected by concrete tool routes.
- Unknown surfaces fall back to `/portal/system` with explicit error code.

### 2.2 Query ownership boundaries

**Result: Pass with two consistency hardening gaps (S1/S2).**

Validated:
- Reducer-owned keys (`file/datum/object/verb`) emitted for reducer-owned surfaces.
- AWS keys are canonicalized and restricted.
- NETWORK keys are normalized to `view/contract/type/record`.
- CTS-GIS tool-local state is body-carried.

Gap G-05 (S1):
- **Invariant at risk:** NETWORK query normalization parity split between shell state machine and filesystem read-model adapter.
- **Evidence pointers:** duplicated normalization logic in:
  - `shell.py::canonical_query_for_surface_query`
  - `network_root_read_model.py::_normalize_surface_query`
- **Impact:** medium risk of divergence in accepted/ignored filter semantics.

Gap G-06 (S2):
- **Invariant at risk:** doc-contract terms are protected by tests, but wording compliance remains test-only and brittle to silent drift.
- **Evidence pointers:** contract-alignment tests assert terminology but no generated source-of-truth map.
- **Impact:** low immediate runtime risk; documentation drift risk.

### 2.3 Canonical URL projection rules

**Result: Partial pass; one drift gap (S1).**

Gap G-02 (S1):
- **Invariant at risk:** browser posture layer persists workbench/interface visibility preferences from local storage outside runtime canonical envelope, which can momentarily override canonical projection on non-tool compositions.
- **Evidence pointers:** `portal.js` `applyShellPostureFromDom` reads `WORKBENCH_OPEN_KEY` and conditionally reapplies local preference.
- **Impact:** medium risk of host/runtime posture mismatch during hydration/re-entry.

---

## 3) Shell behavior invariants (`portal_shell_contract.md`)

### 3.1 Ordered focus stack invariants

**Result: Pass.**

Validated:
- Focus ordering is canonicalized as `sandbox -> file -> datum -> object`.
- `back_out` behaves deterministically by truncating one level.
- SYSTEM mediate->navigate correction when mediation subject disappears is implemented.

### 3.2 Composition invariants

**Result: Pass with one compatibility hardening gap (S2).**

Validated:
- `inspector_collapsed` alias maintained.
- `interface_panel_collapsed` mirrors inspector alias.
- `workbench_collapsed` reflects visibility.
- `regions.interface_panel` mirrors `regions.inspector`.

Gap G-03 (S2):
- **Invariant at risk:** compatibility alias behavior is implemented via object copy; there is no explicit regression assertion that rejects future one-way drift between `regions.inspector` and `regions.interface_panel` across all surfaces.
- **Evidence pointers:** alias copy is runtime-generated in composition builder; tests validate specific scenarios rather than matrix-wide.
- **Impact:** low immediate risk; medium future compatibility risk.

### 3.3 Chrome/region invariants

**Result: Pass with one route-scope test-depth gap (S1).**

Validated:
- Menubar is sole shell header.
- Peer regions are present and splitters are scoped correctly.
- Tool lock is route-scoped in client chrome and represented through `data-tool-panel-lock` + route key.

Gap G-08 (S1):
- **Invariant at risk:** tool lock route-scoped/non-persistent behavior is implemented in client JS but not sufficiently defended by shell/state-machine-level contract tests across surface transitions.
- **Evidence pointers:** client-only lock state transitions in `portal.js` (`setToolPanelLock`, `syncToolPanelLockScope`, dblclick lock logic).
- **Impact:** medium consistency risk under future host-shell refactors.

---

## 4) Gap matrix (all surfaces / affordances)

Legend: `✓` = compliant in audit sample, `△` = compliant today but hardening gap validated, `✗` = contract drift.

| Affordance | Contract expectation | system.root | network.root | utilities.root | system.tools.aws_csm | system.tools.cts_gis | system.tools.fnd_ebi | Gap | Severity |
|---|---|---|---|---|---|---|---|---|---|
| Default panel posture | Root workbench-primary; tools interface-panel-led | ✓ | ✓ | ✓ | △ | △ | △ | G-01 | S1 |
| Interface Panel default | Collapsed on roots unless explicit detail/focus | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Workbench default visibility | Visible on roots; hidden on tools by default | ✓ | ✓ | ✓ | △ | △ | △ | G-01 | S1 |
| Query model ownership | Reducer vs runtime/tool-local boundaries respected | ✓ | △ | ✓ | ✓ | △ | ✓ | G-04, G-05 | S1 |
| Canonical routes | Only declared public routes present | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Control Panel context rows | Current context first, then lower-focus selections | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Activity Bar labels | Icon-only (labels via hover/a11y only) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Tool co-visible lock mode | Double-click lock, route-scoped, non-persistent | n/a | n/a | n/a | △ | △ | △ | G-08 | S1 |

---

## 5) Validated gaps -> prioritized backlog (P0 / P1 / P2)

> Backlog entries below retain the exact paths/functions/tests required by section 5 of the audit plan.

### P0 — Contract correctness blockers

1. **Surface/route drift corrections in shell state machine**  
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`  
   - Functions: `build_portal_surface_catalog`, `canonical_route_for_surface`, `resolve_portal_shell_request`, `canonical_query_for_surface_query`  
   - Gap links: G-02, G-05  
   - Acceptance criteria:
     - Runtime canonical URL projection is never overridden by local posture defaults on initial hydration.
     - Canonical query ownership remains explicit per surface with a single normalization strategy.

2. **Shell composition alias/state parity**  
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`  
   - Functions: `build_shell_composition_payload`, `apply_surface_posture_to_composition`  
   - Gap links: G-01, G-03  
   - Acceptance criteria:
     - Tool posture is enforced in composition even when upstream bundle data drifts.
     - `inspector` and `interface_panel` aliases are provably mirrored across all surfaces.

3. **Root/tool runtime posture contract parity**  
   - Path: `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`  
   - Tests: `test_aws_tool_runtime_matches_shared_interface_panel_led_posture`, `test_network_root_projects_system_log_workbench_without_reducer_ownership`, `test_system_root_shell_composition_uses_logo_as_the_only_system_activity_entry`  
   - Gap links: G-01, G-02  
   - Acceptance criteria:
     - Posture defaults are explicitly asserted for every root/tool surface class.
     - Activity-bar/system-logo semantics remain contract-stable.

### P1 — Query/tool-state boundary hardening

4. **CTS-GIS body-carried state enforcement (no query widening)**  
   - Paths/functions:
     - `MyCiteV2/packages/state_machine/portal_shell/shell.py` → `canonical_query_for_surface_query`, `resolve_portal_shell_request`
     - `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py` → `build_mediation_surface`, `read_surface`
   - Gap link: G-04  
   - Acceptance criteria:
     - Any CTS-GIS query widening attempt is ignored or rejected with deterministic diagnostics.

5. **NETWORK read-model query normalization parity**  
   - Path: `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py`  
   - Functions: `_normalize_surface_query`, `read_surface` filter flow  
   - Gap link: G-05  
   - Acceptance criteria:
     - Shell canonical query and read-model normalization share one canonical contract helper or equivalent invariants.

6. **Doc-contract alignment guardrail**  
   - Path: `MyCiteV2/tests/contracts/test_contract_docs_alignment.py`  
   - Tests: `test_contract_docs_use_one_shell_routes`, `test_surface_catalog_describes_one_aws_csm_tool`, `test_route_model_uses_detail_lens_and_interface_panel_terms`  
   - Gap links: G-06, G-07  
   - Acceptance criteria:
     - Contract language and route/surface claims fail fast when drift is introduced.

### P2 — Affordance consistency and containment polish

7. **Tool lock affordance consistency across tool surfaces**  
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`  
   - Functions: `foreground_region_for_surface`, `shell_composition_mode_for_surface`  
   - Gap link: G-08  
   - Acceptance criteria:
     - Composition metadata and client behavior agree on lock semantics for all tool surfaces.

8. **Architecture boundary regression checks for retired route/surface language**  
   - Path: `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`  
   - Tests: `test_host_and_runtime_use_only_canonical_shell_routes`, `test_shell_contracts_enforce_workspace_and_tool_behavior`, `test_active_repo_text_does_not_reference_retired_split_routes`  
   - Gap links: G-07, G-08  
   - Acceptance criteria:
     - Retired split-route/surface language cannot re-enter active repo text without test failure.

---

## 6) Dependency + rollout notes (for `shell.py` and related tests)

### Dependency notes

- **Primary dependency chain:**
  1. `shell.py` canonicalization behavior (surface catalog, query normalization, composition posture)
  2. Runtime surface bundles (`portal_shell_runtime.py` + tool-specific runtimes)
  3. Client layout/lock behavior (`portal.js`)
  4. Tests spanning unit/contracts/architecture

- **High-coupling risk points:**
  - Posture defaults currently split across shell composition + runtime bundle visibility + client storage restoration.
  - Query ownership invariants split across shell and downstream adapters/services.

### Rollout plan

1. **Phase A (P0 code-first):**
   - Normalize posture and composition parity in `shell.py` first.
   - Update unit tests immediately to lock behavior.
2. **Phase B (P1 boundaries):**
   - Consolidate query normalization paths and CTS-GIS no-widening checks.
   - Extend contract alignment tests.
3. **Phase C (P2 containment):**
   - Strengthen architecture + tool-lock regression coverage.
   - Run full contract + architecture suite.

### Test rollout guardrails

- Run unit behavior tests after each P0/P1 slice.
- Run contract-doc and architecture tests before merge.
- Block release if any canonical route/query regression appears in shell envelope output.

---

## 7) Top blockers, sequencing, and closure criteria

### Top blockers

1. **Split authority for posture application** (runtime bundle + shell composition + client persisted toggles).
2. **Duplicated query normalization logic** between shell and network adapter.
3. **Incomplete end-to-end CTS-GIS anti-query-widening assertion path.**

### Estimated sequencing

- **P0:** 1–2 implementation iterations (shell + runtime behavior tests).
- **P1:** 1 iteration (boundary hardening + alignment tests).
- **P2:** 1 iteration (polish + architecture guards).

### Acceptance criteria for audit closure

Audit is closed when all are true:
1. No S0/S1 gaps remain open in this report.
2. Tool posture invariants are centrally enforced in `shell.py` composition assembly.
3. CTS-GIS query widening is explicitly rejected/ignored with deterministic tests.
4. NETWORK query normalization source of truth is unified (or guaranteed equivalent by shared tests).
5. Contract-doc and architecture regression suites pass with no retired route/surface drift.
