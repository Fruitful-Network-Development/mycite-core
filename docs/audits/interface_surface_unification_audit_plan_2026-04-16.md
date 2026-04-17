# Interface Surface Unification Audit Plan

Date: 2026-04-16

## Objective

Run a contract-first audit that verifies root surfaces and tool surfaces all conform to one-shell interface semantics, then produce a prioritized backlog of unification deltas with exact implementation targets.

## Inputs

- `docs/contracts/surface_catalog.md`
- `docs/contracts/route_model.md`
- `docs/contracts/portal_shell_contract.md`

---

## 1) Surface model checks against `docs/contracts/surface_catalog.md`

### 1.1 Canonical surface inventory

Verify code/runtime expose **only** these first-class surfaces:

- `system.root`
- `system.tools.aws_csm`
- `system.tools.cts_gis`
- `system.tools.fnd_ebi`
- `network.root`
- `utilities.root`
- `utilities.tool_exposure`
- `utilities.integrations`

Reject/flag:

- Retired first-class `activity` and `profile_basics` surfaces
- Split AWS surface variants (e.g., onboarding/sandbox/narrow-write as top-level surfaces)

### 1.2 Root-vs-tool posture defaults

Validate posture defaults are consistent with catalog contract:

- Root surfaces (`SYSTEM`, `NETWORK`, `UTILITIES`) are workbench-primary with Interface Panel collapsed by default unless explicit focus/detail exists.
- Tool surfaces are interface-panel-led with workbench hidden by default.
- Tool workbench content is secondary evidence only.

### 1.3 Tool-local behavior boundaries

Validate:

- `AWS-CSM` query-driven model (`view`, `domain`, `profile`, `section`) remains runtime-owned.
- `CTS-GIS` tool-local navigation remains body-carried (`tool_state`) and does not widen shell focus stack.
- Activity bar remains icon-only for both root and tool entries.

---

## 2) Route/query consistency checks against `docs/contracts/route_model.md`

### 2.1 Canonical route set

Validate host/runtime only expose:

- `/portal` (redirects to `/portal/system`)
- `/portal/system`
- `/portal/system/tools/<tool_slug>`
- `/portal/network`
- `/portal/utilities`
- `/portal/utilities/tool-exposure`
- `/portal/utilities/integrations`

Flag any retired split-shell/split-tool route drift.

### 2.2 Query ownership boundaries

Validate query/state ownership:

- Reducer-owned SYSTEM queries: `file`, `datum`, `object`, `verb`.
- AWS-CSM runtime-owned queries: `view`, `domain`, `profile`, `section`.
- NETWORK surface-query keys: `view`, `contract`, `type`, `record`.
- CTS-GIS tool-local state remains in request body (`tool_state`), not URL query.

### 2.3 Canonical URL projection rules

Validate runtime returns canonical route/query and browser history is updated only from runtime canonical URL projections.

---

## 3) Shell behavior invariants from `docs/contracts/portal_shell_contract.md`

### 3.1 Ordered focus stack invariants

Validate exact shared shell order and back-out behavior:

- `sandbox -> file -> datum -> object`
- `back_out`: `object->datum`, `datum->file`, `file->sandbox`, `sandbox->no-op`

### 3.2 Composition invariants

Validate composition payload semantics:

- `inspector_collapsed` compatibility alias remains valid.
- `interface_panel_collapsed` mirrors `inspector_collapsed`.
- `workbench_collapsed` accurately reflects current hidden state.
- `regions.interface_panel` mirrors `regions.inspector`.

### 3.3 Chrome/region invariants

Validate:

- Menubar is the only shell header.
- Peer regions remain: Activity Bar, Control Panel, Workbench, Interface Panel.
- Only Control Panel and Interface Panel have explicit splitters/persisted widths.
- Tool lock behavior is route-scoped, non-persistent, and published via `data-tool-panel-lock`.

---

## 4) Gap matrix for inconsistent affordances across root and tool surfaces

Use the matrix below during audit execution.

| Affordance | Contract expectation | system.root | network.root | utilities.root | system.tools.aws_csm | system.tools.cts_gis | system.tools.fnd_ebi | Gap | Severity |
|---|---|---|---|---|---|---|---|---|---|
| Default panel posture | Root workbench-primary; tools interface-panel-led |  |  |  |  |  |  |  |  |
| Interface Panel default | Collapsed on roots unless explicit detail/focus |  |  |  |  |  |  |  |  |
| Workbench default visibility | Visible on roots; hidden on tools by default |  |  |  |  |  |  |  |  |
| Query model ownership | Reducer vs runtime/tool-local boundaries respected |  |  |  |  |  |  |  |  |
| Canonical routes | Only declared public routes present |  |  |  |  |  |  |  |  |
| Control Panel context rows | Current context first, then lower-focus selections |  |  |  |  |  |  |  |  |
| Activity Bar labels | Icon-only (labels via hover/a11y only) |  |  |  |  |  |  |  |  |
| Tool co-visible lock mode | Double-click lock, route-scoped, non-persistent | n/a | n/a | n/a |  |  |  |  |  |

Severity scale:

- `S0` = contract breakage, user-visible/navigation correctness risk
- `S1` = behavioral drift/high inconsistency
- `S2` = nomenclature/diagnostic drift without immediate breakage

---

## 5) Required output: prioritized backlog of unification deltas (exact paths/functions)

### P0 — Contract correctness blockers

1. **Surface/route drift corrections in shell state machine**
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`
   - Functions:
     - `build_portal_surface_catalog`
     - `canonical_route_for_surface`
     - `resolve_portal_shell_request`
     - `canonical_query_for_surface_query`

2. **Shell composition alias/state parity**
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`
   - Functions:
     - `build_shell_composition_payload`
     - `apply_surface_posture_to_composition`

3. **Root/tool runtime posture contract parity**
   - Path: `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
   - Tests to update/extend:
     - `test_aws_tool_runtime_matches_shared_interface_panel_led_posture`
     - `test_network_root_projects_system_log_workbench_without_reducer_ownership`
     - `test_system_root_shell_composition_uses_logo_as_the_only_system_activity_entry`

### P1 — Query/tool-state boundary hardening

4. **CTS-GIS body-carried state enforcement (no query widening)**
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`
   - Functions:
     - `canonical_query_for_surface_query`
     - `resolve_portal_shell_request`
   - Path: `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py`
   - Functions:
     - `build_mediation_surface`
     - `read_surface`

5. **NETWORK read-model query normalization parity**
   - Path: `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py`
   - Functions:
     - `_normalize_surface_query`
     - `read_surface` flow where `view/contract/type/record` filters are applied

6. **Doc-contract alignment guardrail**
   - Path: `MyCiteV2/tests/contracts/test_contract_docs_alignment.py`
   - Tests to update/extend:
     - `test_contract_docs_use_one_shell_routes`
     - `test_surface_catalog_describes_one_aws_csm_tool`
     - `test_route_model_uses_detail_lens_and_interface_panel_terms`

### P2 — Affordance consistency and containment polish

7. **Tool lock affordance consistency across tool surfaces**
   - Path: `MyCiteV2/packages/state_machine/portal_shell/shell.py`
   - Functions:
     - `foreground_region_for_surface`
     - `shell_composition_mode_for_surface`

8. **Architecture boundary regression checks for retired route/surface language**
   - Path: `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
   - Tests to update/extend:
     - `test_host_and_runtime_use_only_canonical_shell_routes`
     - `test_shell_contracts_enforce_workspace_and_tool_behavior`
     - `test_active_repo_text_does_not_reference_retired_split_routes`

---

## Execution notes

- Audit must be contract-led: docs contracts define expected behavior; code/tests are validated against that truth.
- Every gap entry must cite: affected surface(s), exact violated invariant, exact function/test touchpoints, and severity.
- Final deliverable from this plan is a sequenced implementation backlog grouped by P0/P1/P2 with measurable acceptance criteria per item.
