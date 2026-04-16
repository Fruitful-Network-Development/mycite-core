# Tools UI Implementation Mismatch Report (2026-04-16)

## Executive summary

- **Canonical tool slugs audited:** 3 (`aws-csm`, `cts-gis`, `fnd-ebi`).
- **Coverage status:** complete (all canonical tool slugs from `TOOL_SLUG_TO_SURFACE_ID` mapped end-to-end).
- **Mismatch counts by category:**
  - Contract: 2
  - Projection: 2
  - Renderer: 2
  - Mode: 2
  - Fallback: 3
- **Top consolidation opportunities:**
  1. Introduce a shared shell-side tool state adapter for `tool_mediation_surface` and `tool_secondary_evidence` payload families.
  2. Centralize loading/error/empty/fallback rendering semantics in shell-core region wrappers (before delegating to tool renderers).
  3. Normalize direct-query tool state updates (`aws-csm`, `network`) and reducer-owned transition dispatch (`cts-gis`, `fnd-ebi`) behind a single navigation/selection helper.

---

## Phase A–B coverage matrix (one row per canonical tool slug)

| tool_slug | runtime_entry_path | runtime_entry_symbol | state_projection_path | state_projection_symbol | ui_renderer_path | ui_renderer_symbol | route_or_mount_path | fallback_renderer_path | notes |
|---|---|---|---|---|---|---|---|---|---|
| aws-csm | `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py` + `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py` | `_tool_bundle_for_surface` (canonical in shell runtime) + `build_portal_aws_surface_bundle` | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js` + `.../v2_portal_aws_workspace.js` | `PortalShellWorkbenchRenderer.render` dispatch + `buildSurfaceRequest`/inline projection helpers (`profileFactRows`, `newsletterRows`) | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_aws_workspace.js` | `PortalAwsCsmWorkspaceRenderer.render` + `PortalAwsCsmInspectorRenderer.render` | GET `/portal/system/tools/aws-csm` (slug map) + POST `/portal/api/v2/shell` (primary shell path) + POST `/portal/api/v2/system/tools/aws-csm` (direct runtime endpoint) | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js::renderGenericSurface` and `.../v2_portal_inspector_renderers.js` default stack | Tool is configured as interface-panel-primary but still has workbench renderer module; runtime sets `workbench.visible=false` while inspector is always visible. |
| cts-gis | `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py` + `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py` | `_tool_bundle_for_surface` (canonical) + `build_portal_cts_gis_surface_bundle` | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js` + `.../v2_portal_workbench_renderers.js` | `PortalShellInspectorRenderer.render` → `renderCtsGisInspector`; workbench inline branch for `tool_secondary_evidence` | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js` | `renderCtsGisInspector` (via `PortalShellInspectorRenderer.render`) | GET `/portal/system/tools/cts-gis` + POST `/portal/api/v2/shell` (primary shell path) + POST `/portal/api/v2/system/tools/cts-gis` (direct runtime endpoint) | Inspector default branch in `PortalShellInspectorRenderer.render`; workbench generic `tool_secondary_evidence` branch when `tool_id !== "cts_gis"` | Most specialized tool UI path; request contract includes legacy aliases while renderer assumes normalized interface body. |
| fnd-ebi | `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py` + `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py` | `_tool_bundle_for_surface` (canonical) + `build_portal_fnd_ebi_surface_bundle` | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js` + `.../v2_portal_workbench_renderers.js` | Generic projection only (`PortalShellInspectorRenderer.render` default stack + `renderGenericSurface`) | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js` | `PortalShellInspectorRenderer.render` (default branch; no FND-specific renderer symbol) | GET `/portal/system/tools/fnd-ebi` + POST `/portal/api/v2/shell` (primary shell path) + POST `/portal/api/v2/system/tools/fnd-ebi` (direct runtime endpoint) | Generic inspector/workbench renderers only (`renderRows`, default “Interface Panel” card, `renderGenericSurface`) | Tool is interface-panel-primary in registry but has no dedicated renderer; relies entirely on generic shell panel/table rendering. |

---

## Phase C mismatch inventory

### Contract mismatches

1. **Dual request contracts in runtime vs renderer invocation shape**
   - `aws-csm` and `network` renderer helpers build shell requests with `surface_query` only, while reducer-owned tools depend on richer `shell_state`/`transition` envelopes.
   - **Impacted paths/symbols:**
     - `v2_portal_aws_workspace.js::buildSurfaceRequest`
     - `v2_portal_network_workspace.js::buildSurfaceRequest`
     - `portal_shell_runtime.py::run_portal_shell_entry` / reducer-owned `resolve_portal_shell_request` flow.

2. **Legacy CTS-GIS alias support present in runtime contract but not represented in UI helpers**
   - Runtime advertises `legacy_aliases` and consumes legacy mediation keys; inspector click handlers emit only normalized `shell_request` blobs from runtime-produced entries.
   - **Impacted paths/symbols:**
     - `portal_cts_gis_runtime.py::build_portal_cts_gis_surface_bundle` (`request_contract.legacy_aliases`)
     - `v2_portal_inspector_renderers.js::bindShellRequestEntries`.

### Projection mismatches

1. **Duplicate projection logic in AWS renderer vs runtime workspace model**
   - Renderer re-derives profile/newsletter fact rows (`profileFactRows`, `newsletterRows`) instead of consuming already-normalized runtime fact rows.
   - **Impacted:** `v2_portal_aws_workspace.js::{profileFactRows,newsletterRows}`.

2. **Tool-specific projection in CTS-GIS split across runtime interface body and shell inline workbench evidence block**
   - Workbench branch manually unpacks `source_evidence.readiness` and file hints independent of inspector’s richer `interface_body` semantics.
   - **Impacted:** `v2_portal_workbench_renderers.js` CTS-GIS `tool_secondary_evidence` branch + `portal_cts_gis_runtime.py::_cts_gis_interface_body`.

### Renderer mismatches

1. **Tool posture says interface-panel-primary for all tools, but renderer specialization exists for only AWS/CTS paths**
   - `fnd-ebi` lacks dedicated inspector/workbench module and falls through generic renderer path.
   - **Impacted:** `portal_shell/shell.py::build_portal_tool_registry_entries`, `v2_portal_inspector_renderers.js::PortalShellInspectorRenderer.render`.

2. **Workbench module dispatch keyed by `surface_payload.kind` (AWS/system/network) while tool registry keyed by `tool_id`/surface_id**
   - Routing contract mixes two identifiers (`kind` vs `tool_id/surface_id`), increasing drift risk for new tools.
   - **Impacted:** `v2_portal_workbench_renderers.js::PortalShellWorkbenchRenderer.render`, runtime `surface_payload.kind` assignments in tool runtimes.

### Mode mismatches

1. **Reducer-owned mode diverges by tool (`aws-csm` false; `cts-gis` and `fnd-ebi` true)**
   - UI behavior differs: transition dispatcher only active when envelope is reducer-owned.
   - **Impacted:** `portal_aws_runtime.py::run_portal_aws_csm`, `portal_cts_gis_runtime.py::run_portal_cts_gis`, `portal_fnd_ebi_runtime.py::run_portal_fnd_ebi`, `v2_portal_shell_core.js::dispatchTransition`.

2. **Workbench visibility semantics inconsistent with renderer investment**
   - AWS/FND/CTS bundles set `workbench.visible=false`, but dedicated workbench renderers still exist for AWS and secondary evidence for CTS/FND.
   - **Impacted:** tool runtime `workbench` blocks + `v2_portal_workbench_renderers.js`.

### Fallback mismatches

1. **No unified per-tool loading state**
   - Shell fatal covers request failure globally; tool renderers independently return empty/no-data content without shared loading skeleton.
   - **Impacted:** `v2_portal_shell_core.js::{loadShell,loadRuntimeView,showFatal}` and tool renderers.

2. **Inconsistent empty-state messaging patterns**
   - `No entries`, `No items available`, `Select...`, and domain-specific text vary by renderer without shared thresholds/wording policy.
   - **Impacted:** `v2_portal_workbench_renderers.js`, `v2_portal_inspector_renderers.js`, `v2_portal_aws_workspace.js`, `v2_portal_network_workspace.js`.

3. **Fallback renderer selection tied to weak predicates**
   - Generic fallback often triggered by missing `kind`/module globals rather than explicit unsupported-state handling with telemetry.
   - **Impacted:** `PortalShellWorkbenchRenderer.render`, `PortalShellInspectorRenderer.render`.

---

## Phase D drift checklist (items 1–10 for each tool)

Legend: **Parity** = aligned with shell-wide pattern; **Non-parity** = divergence/drift risk.

### aws-csm

| # | Checklist item | Result | Evidence note |
|---|---|---|---|
| 1 | Loading semantics parity | Non-parity | Uses direct `ctx.loadShell` on selection changes; no local loading/stale indicator in renderer. |
| 2 | Error semantics parity | Non-parity | Relies on shell fatal only; no tool-local timeout/empty vs error distinction. |
| 3 | Selection/context semantics parity | Parity | Query-driven selection (`domain/profile/section`) consistently mapped in `buildSurfaceRequest`. |
| 4 | Projection semantics parity | Non-parity | Renderer recomputes profile/newsletter detail rows from raw payload. |
| 5 | Capability gating parity | Parity | Runtime `tool.operational/missing_capabilities` displayed directly in inspector. |
| 6 | Navigation semantics parity | Parity | Uses shell request dispatch path and canonical surface query updates. |
| 7 | Empty-state parity | Non-parity | Domain-specific no-data copy differs from generic shell copy conventions. |
| 8 | Telemetry/instrumentation parity | Non-parity | No shared event emission for selection actions beyond shell request POSTs. |
| 9 | Utility reuse parity | Non-parity | Reimplements info-row/fact derivation helpers instead of shared formatters. |
| 10 | Fallback renderer parity | Non-parity | Falls back to generic workbench/inspector behavior if module globals unavailable, without explicit tool fallback contract. |

### cts-gis

| # | Checklist item | Result | Evidence note |
|---|---|---|---|
| 1 | Loading semantics parity | Non-parity | Entry clicks trigger `ctx.loadShell` immediately; no intermediate mediation loading state UI. |
| 2 | Error semantics parity | Non-parity | Warnings/readiness rendered, but no standardized shell error region mapping for tool-level failures. |
| 3 | Selection/context semantics parity | Parity | Runtime emits canonical `shell_request` per lineage/navigation/intention/row entry; renderer reuses them. |
| 4 | Projection semantics parity | Parity | Primary projection authored in runtime (`interface_body`) and consumed directly by specialized inspector renderer. |
| 5 | Capability gating parity | Parity | Runtime computes configured/enabled/missing capability posture and exposes via control/inspector sections. |
| 6 | Navigation semantics parity | Parity | Reducer-owned flow + shell dispatch/state URL synchronization maintained. |
| 7 | Empty-state parity | Non-parity | CTS-specific placeholder copy and pane composition differs from generic empty-state conventions. |
| 8 | Telemetry/instrumentation parity | Non-parity | No shared event schema for entry-click actions. |
| 9 | Utility reuse parity | Mixed / Non-parity | Reuses generic `renderRows`, but still has specialized button list/summary rendering logic duplicated from other panels. |
| 10 | Fallback renderer parity | Non-parity | Tool-secondary evidence fallback differs between CTS-specific and generic branches. |

### fnd-ebi

| # | Checklist item | Result | Evidence note |
|---|---|---|---|
| 1 | Loading semantics parity | Non-parity | No tool-local loading state; inherits global shell behavior only. |
| 2 | Error semantics parity | Non-parity | Missing webapps/capability is rendered as prerequisite rows, not standardized error states. |
| 3 | Selection/context semantics parity | Parity | Reducer-owned shell_state mediation/focus subject semantics remain canonical. |
| 4 | Projection semantics parity | Parity | Uses runtime-provided sections with minimal shell-side transformation. |
| 5 | Capability gating parity | Parity | Runtime applies configured/enabled/missing capability checks via shared exposure helpers. |
| 6 | Navigation semantics parity | Parity | Routed through canonical shell entry with reducer-owned URL/query synchronization. |
| 7 | Empty-state parity | Non-parity | Generic inspector defaults and sparse workbench evidence copy differ from other tool surfaces. |
| 8 | Telemetry/instrumentation parity | Non-parity | No tool-specific or shared interaction events in generic renderer path. |
| 9 | Utility reuse parity | Parity | Leverages shared control-panel builder and generic inspector/workbench renderers. |
| 10 | Fallback renderer parity | Non-parity | Entire tool relies on generic fallback renderer path despite interface-panel-primary posture. |

---

## Phase E remediation and consolidation proposals

Migration order is **low-risk first**.

### 1) Add shell-side `ToolSurfaceAdapter` (read-only adapter layer)
- **Target:** Introduce a small adapter utility in shell static bundle that normalizes common tool payload facets (`tool`, `request_contract`, readiness/warnings, empty-state descriptors).
- **Effort:** Medium.
- **Risk:** Low (additive; can preserve existing payload contract).
- **First moves:**
  1. Add adapter and unit tests for current payload families (`aws_csm_workspace`, `tool_mediation_surface`, `tool_secondary_evidence`).
  2. Switch AWS and FND generic inspector paths to adapter-fed rows.
  3. Collapse duplicate fact-row logic in AWS renderer.

### 2) Standardize fallback/loading/error shell wrappers around region render calls
- **Target:** Wrap `workbench` and `inspector` dispatch in shared shell-core fallback policy that distinguishes `loading`, `error`, `empty`, and `unsupported`.
- **Effort:** Medium.
- **Risk:** Medium (touches global rendering entrypoints).
- **First moves:**
  1. Add non-breaking wrapper in `PortalShellWorkbenchRenderer.render` / `PortalShellInspectorRenderer.render`.
  2. Preserve existing tool renderers behind feature flag.
  3. Enable standardized copy and CSS for one tool at a time (start with FND-EBI generic path).

### 3) Unify navigation request construction across direct-query and reducer-owned tools
- **Target:** Shared helper to construct shell requests from current envelope (`requested_surface_id`, `portal_scope`, optional `surface_query`, optional transition).
- **Effort:** Medium.
- **Risk:** Medium.
- **First moves:**
  1. Extract current request building logic from AWS/Network JS modules into shared static utility.
  2. Add CTS/FND optional adapter path for request entry generation where runtime does not already provide `shell_request`.
  3. Add contract tests asserting query-state parity and canonical URL behavior.

### 4) Clarify registry posture vs actual renderer strategy
- **Target:** Either (a) provide dedicated FND renderer modules to match interface-panel-primary strategy, or (b) reclassify FND posture as generic mediation panel until specialization exists.
- **Effort:** Low-to-medium.
- **Risk:** Low.
- **First moves:**
  1. Short-term docs + metadata update to avoid architectural ambiguity.
  2. Optionally add lightweight FND inspector specialization if product intent is parity with AWS/CTS.

### 5) Add drift tests for checklist-sensitive areas
- **Target:** Automated assertions for fallback and projection parity.
- **Effort:** Medium.
- **Risk:** Low.
- **First moves:**
  1. Add tests that verify every tool slug resolves to expected renderer branch.
  2. Add tests for empty/error/loading placeholder consistency.
  3. Add tests that prohibit duplicate projection helpers across tool renderers when shared adapter exists.

---

## Exit criteria verification

1. **Every discovered tool slug has full mapping row:** ✅ (`aws-csm`, `cts-gis`, `fnd-ebi`).
2. **Every mismatch has owner candidate and remediation direction:** ✅ (categories + impacted paths + remediation sequence above).
3. **Duplicate shell/tool logic clusters identified with consolidation targets:** ✅ (adapter, wrapper, nav helper, posture alignment, drift tests).
4. **Top consolidation opportunities identified:** ✅ (top 3 listed in executive summary).

---

## Appendix A — canonical tool slug normalization map

| Canonical slug | Surface ID | Tool ID | Notes |
|---|---|---|---|
| `aws-csm` | `system.tools.aws_csm` | `aws_csm` | Legacy aliases redirected: `aws`, `aws-narrow-write`, `aws-csm-sandbox`, `aws-csm-onboarding` -> `/portal/system/tools/aws-csm`. |
| `cts-gis` | `system.tools.cts_gis` | `cts_gis` | Runtime request contract advertises legacy tool-state aliases for compatibility. |
| `fnd-ebi` | `system.tools.fnd_ebi` | `fnd_ebi` | No dedicated shell renderer; generic inspector/workbench projection currently used. |

## Appendix B — unresolved questions

1. Should `fnd-ebi` remain interface-panel-primary without a dedicated renderer module?
2. Should AWS continue reducer-unowned mode, or be migrated to reducer-owned to align tool-state semantics with other system tools?
3. Is legacy CTS-GIS alias support still required for active clients, and if yes, should shell-side debug indicators show alias-consumed mode?
