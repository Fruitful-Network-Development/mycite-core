# Portal Shell Boundary Map And System/Workbench UI Split

Date: 2026-04-23

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## 1. Purpose

Freeze the exact ownership boundaries for shell authority, runtime bundle assembly, runtime payload generation, region-family render hosts, compatibility adapters, and the remaining tool-local UI seams.

This plan exists separately because every later slice touches the same files. Without one canonical boundary map, follow-on agents will keep fixing only one layer and then reintroducing shell/runtime/client drift.

## 2. In-Scope vs Out-of-Scope

### In scope

- file-by-file ownership for the shell, runtime, and client host files that participate in one-shell delivery
- the explicit `SYSTEM` versus `workbench_ui` split
- architecture and unit-test hardening that enforces those boundaries before refactor work lands

### Out of scope

- feature delivery inside AWS-CSM, CTS-GIS, FND-DCM, or FND-EBI
- changing the reducer-owned versus runtime-owned surface model unless a contract file is updated on purpose
- removing the public `inspector` compatibility alias in this sequence
- adding new shell regions, new shell-level renderer kinds, or a second posture authority path

## 3. Exact Repo Evidence

- `MyCiteV2/packages/state_machine/portal_shell/shell.py`
  - `REDUCER_OWNED_SURFACE_IDS` keeps reducer ownership limited to `system.root`, `system.tools.cts_gis`, and `system.tools.fnd_ebi`.
  - `canonical_query_for_surface_query()` owns runtime-owned query normalization for `network.root`, `system.tools.aws_csm`, `system.tools.fnd_dcm`, and `system.tools.workbench_ui`.
  - `build_shell_composition_payload()` is already the first-load posture authority and already carries the `workbench_ui` `workbench_primary` exception.
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `_tool_bundle_for_surface()` still dispatches with open-coded `if surface_id == ...` branches.
  - `_bundle_for_surface()` still mixes surface selection, root/tool assembly, and inline payload generation for `NETWORK` and `UTILITIES`.
  - verified on 2026-04-23: `run_portal_shell_entry()` ignores incoming `surface_query` for `system.tools.workbench_ui` because `_tool_bundle_for_surface()` does not forward it to `build_portal_workbench_ui_surface_bundle()`.
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `build_system_workspace_bundle()` builds the reducer-owned datum-file workbench, including `anthology` presentation and mediation-panel content.
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `build_portal_workbench_ui_surface_bundle()` builds the runtime-owned SQL authority inspector with `document`, `row`, grouping, lens, source, and overlay query handling.
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - emits `aws_csm_workspace` and `aws_csm_inspector`.
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - emits `tool_mediation_surface`, `tool_mediation_panel`, `tool_secondary_evidence`, and `cts_gis_interface_body`.
- `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - emits `tool_mediation_surface` and `tool_mediation_panel`.
- `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - emits `tool_mediation_surface`, `tool_secondary_evidence`, and `tool_mediation_panel`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
  - top-level control-panel host still special-cases CTS-GIS through `region.surface_label === "CTS-GIS"` and `region.state_directive_compact`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  - top-level workbench host still branches on `surfacePayload.kind` and on `surfacePayload.tool_id === "cts_gis"` for secondary evidence.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - top-level interface-panel host still branches on `region.kind` and on `region.interface_body.kind === "cts_gis_interface_body"`.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - already centralizes readiness, warning, loading, error, empty, and unsupported wrappers; this is the correct compatibility layer to shrink rather than bypass.
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`
  - already stays shell-shaped: it validates the envelope, applies chrome, and calls the family hosts without inspecting tool identity.
- `MyCiteV2/instances/_shared/portal_host/static/portal.js`
  - still owns layout persistence, legacy `inspector` storage aliases, and route-scoped tool-lock behavior; it is not a payload or query authority.
- verified on 2026-04-23 by running:
  - `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
  - `python3 -m unittest MyCiteV2.tests.architecture.test_portal_shell_stabilization_matrix`
  - `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_contract`
  - `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`

## 4. Target State

### Placement rule

- If the change affects first-load visibility, surface posture, reducer/runtime ownership, or canonical query ownership, it belongs in `shell.py`.
- If the change affects how a selected surface becomes a runtime bundle or envelope, it belongs in runtime bundle assembly.
- If the change affects wrapper states, markup consumption, widget/layout rendering, or module registration, it belongs in client compatibility rendering.

### Canonical `SYSTEM` versus `workbench_ui` split

- `/portal/system` remains the reducer-owned datum-file workbench. It keeps the sandbox/file/datum/object focus stack, the `anthology` anchor-file invariant, and mediation-owned interface-panel behavior.
- `/portal/system/tools/workbench-ui` remains a runtime-owned SQL authority inspector. Its query vocabulary stays `document`, `document_filter`, `document_sort`, `document_dir`, `filter`, `sort`, `dir`, `group`, `workbench_lens`, `source`, `overlay`, and `row`.
- `workbench_ui` stays the only approved `workbench_primary` tool exception. That posture exception belongs in `build_shell_composition_payload()`, not in the workbench payload or in client code.
- `workbench_ui` may prefer CTS-GIS authoritative documents as a tool-local inspection default, but it must not replace the reducer-owned `SYSTEM` anthology workspace or import `SYSTEM` file/workbench responsibilities into its own query model.

### File-by-file map

| Bucket | File | Allowed to decide | Must not decide | What later agents commonly get wrong |
|---|---|---|---|---|
| shell authority | `MyCiteV2/packages/state_machine/portal_shell/shell.py` | surface catalog, reducer/runtime ownership, canonical route and query projection, first-load posture, `workbench_ui` posture exception | tool-local payload markup, client module choice, secondary evidence rendering | adding a new surface-specific renderer kind or a posture override outside `build_shell_composition_payload()` |
| shell authority | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js` | envelope validation, chrome application, family-renderer invocation, history sync from canonical runtime URL | tool-specific render branching, canonical query rewriting, tool-local body semantics | moving payload dispatch logic into shell core because it is convenient to reach all regions there |
| runtime composition / bundle assembly | `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py` | request normalization, selection resolution, shared bundle assembly orchestration, runtime envelope assembly, shared root helpers while they remain there | first-load posture, tool-local rendering details, silent omission of runtime-owned query inputs | extending `_tool_bundle_for_surface()` and `_bundle_for_surface()` with more per-surface branches instead of tightening the shared assembly contract |
| runtime payload generators | `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py` | reducer-owned `SYSTEM` workbench, directive context, `anthology` table projection, mediation-panel content for `SYSTEM` | SQL-inspector query ownership, tool-posture authority, client module registration | treating `SYSTEM` as a generic home page or as a SQL document browser |
| runtime payload generators | `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py` | SQL-backed authoritative document and datum-grid payloads, runtime-owned `workbench_ui` query interpretation, additive overlay summaries | reducer-owned `SYSTEM` focus stack, anchor-file behavior, shell posture authority | treating `workbench_ui` as a replacement for `/portal/system`, or letting shell-route assembly drop its `surface_query` |
| runtime payload generators | `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py` | AWS-CSM control-panel, workbench evidence, and interface-panel payload content | shell posture, shell query ownership beyond canonical runtime normalization | encoding AWS renderer decisions into shell/runtime entry selection |
| runtime payload generators | `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py` | CTS-GIS tool-local `tool_state`, compiled-state handling, directive-panel payload, interface-panel body content, secondary evidence payload | widening shared shell query, shell posture, client host dispatch | moving CTS-GIS navigation into shell query or into `shell.py` because CTS-GIS is reducer-owned |
| runtime payload generators | `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py` | FND-DCM runtime-owned query handling and payload generation | shell posture, shell renderer selection | turning FND-DCM evidence posture into a second workbench-primary exception |
| runtime payload generators | `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py` | FND-EBI reducer-owned tool payloads and interface-panel content | shell posture, shell query widening, renderer selection | assuming FND-EBI should follow the AWS/FND-DCM runtime-owned query path just because it is a tool route |
| region-family render hosts | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js` | directive-panel host rendering and binding | deciding tool identity from `surface_label`, inventing new directive-panel families | keeping CTS-GIS as a top-level special case in the family host |
| region-family render hosts | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js` | reflective-workspace host rendering and binding | treating `surfacePayload.kind` as the permanent top-level authority | adding one more `if (surfacePayload.kind === ...)` branch for each new workspace variation |
| region-family render hosts | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js` | presentation-surface host rendering and binding | making `region.kind` or `interface_body.kind` the permanent interface-panel API | keeping CTS-GIS, AWS, and NETWORK as hard-coded top-level inspector branches |
| region-family render hosts | `MyCiteV2/instances/_shared/portal_host/app.py` | shell asset manifest order, shell-module export contracts, endpoint wiring | payload semantics, posture, or query normalization | adding a new tool-only shell module to avoid fixing the family host contract |
| compatibility adapters to shrink over time | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js` | shared loading/error/empty/unsupported wrappers, readiness/warning collection, direct-query request building | surface-specific orchestration or shell-region choice | bypassing the adapter and re-implementing wrappers inside each renderer branch |
| compatibility adapters to shrink over time | `MyCiteV2/instances/_shared/portal_host/static/portal.js` | layout persistence, legacy `inspector` storage aliases, route-scoped tool lock, splitter behavior | payload content, canonical query, runtime composition | mixing compatibility layout state into runtime payload or using it as first-load authority |
| specialized tool-local UI logic still awaiting migration | `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py` | CTS-GIS-local directive and presentation content while migration is incomplete | top-level shell family choice | claiming CTS-GIS is already region-family generic because the file only changed names |
| specialized tool-local UI logic still awaiting migration | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js` | temporary CTS-GIS directive-panel compatibility path | permanent directive-panel authority | leaving `renderCtsGisDirectivePanel()` in place after the family contract exists |
| specialized tool-local UI logic still awaiting migration | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js` | temporary CTS-GIS secondary-evidence compatibility path | permanent reflective-workspace authority | treating `tool_secondary_evidence` plus `tool_id` branches as the end-state |
| specialized tool-local UI logic still awaiting migration | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js` | temporary CTS-GIS Diktataograph/Garland host while the presentation-surface contract is being normalized | permanent presentation-surface authority | assuming moving helpers around inside the same 1500-line file counts as unification |

## 5. Staged Execution Slices

### Stage 1: Freeze the boundary in tests before refactor work

- Exact files expected to change:
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_shell_contract.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- Exact behavior expected to change:
  - no user-visible behavior change
  - the test suite starts failing when `SYSTEM` and `workbench_ui` are blurred, when shell authority leaks into runtime/client files, or when client family hosts gain new tool-identity branches
- Compatibility adapters or temporary aliases required:
  - none beyond existing `inspector` compatibility aliases already in contract
- Retirement gate:
  - these tests must land and stay green before runtime or renderer unification starts

### Stage 2: Apply the boundary map in runtime bundle assembly

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
- Exact behavior expected to change:
  - runtime bundle assembly becomes shared and explicit
  - `workbench_ui` shell-path query handling matches its direct endpoint behavior
  - shell posture and route/query authority remain in `shell.py`
- Tests to add or update:
  - `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Compatibility adapters or temporary aliases required:
  - existing bundle keys remain until the renderer migration retires them
- Retirement gate:
  - no runtime assembly path still decides both surface selection and tool-local payload shape in the same branch table

### Stage 3: Apply the boundary map in region-family rendering

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - `MyCiteV2/instances/_shared/portal_host/app.py`
- Exact behavior expected to change:
  - top-level hosts stop treating tool identity as primary dispatch authority
  - compatibility adapters consume legacy fields while the runtime and client contracts converge on `directive_panel`, `reflective_workspace`, and `presentation_surface`
- Tests to add or update:
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Compatibility adapters or temporary aliases required:
  - `surfacePayload.kind`, `region.kind`, `state_directive_compact`, `tool_secondary_evidence`, and `cts_gis_interface_body` remain only as documented compatibility inputs
- Retirement gate:
  - the top-level family hosts no longer branch on `surface_label`, `surfacePayload.kind`, or `region.kind` in their primary path

## 6. Risks And Anti-Patterns

- Treating `workbench_ui` as a soft rename of `SYSTEM` because both live under `/portal/system`.
- Moving first-load visibility or posture rules out of `build_shell_composition_payload()`.
- Letting client code rewrite canonical query or `tool_state` because it already binds click handlers.
- Fixing the shell-path `workbench_ui` query gap inside the renderer instead of the runtime assembly path.
- Collapsing every tool payload into one generic blob with no family-specific contract, which only hides drift rather than removing it.
- Removing `inspector` compatibility aliases during this sequence and turning a unification pass into a schema-revision pass.

## 7. Definition Of Done

- The boundary tests explicitly defend the `SYSTEM` versus `workbench_ui` split.
- Later implementation slices can answer, file by file, whether a change belongs in `shell.py`, runtime bundle assembly, runtime payload generation, or client compatibility rendering.
- `portal_shell_runtime.py` no longer acts as an undocumented second source of product semantics.
- Top-level client hosts no longer need tool-identity branches to remain functional.
- No plan or implementation slice in this sequence adds a new shell region, a new shell-level renderer kind, or a second posture authority path.
