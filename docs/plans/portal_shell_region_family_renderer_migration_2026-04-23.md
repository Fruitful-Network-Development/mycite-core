# Portal Shell Region-Family Renderer Migration

Date: 2026-04-23

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## 1. Purpose

Move the client from tool-identity and payload-kind dispatch to the canonical region families already defined in contract:

- `directive_panel`
- `reflective_workspace`
- `presentation_surface`

This plan exists separately because the repo already has a shell-shaped host. The remaining gap is that each family host still carries tool-specific compatibility branches, especially for CTS-GIS.

## 2. In-Scope vs Out-of-Scope

### In scope

- control-panel, workbench, and interface-panel render hosts
- shared wrapper and direct-query adapter behavior
- runtime payload changes needed so each host can consume family-scoped contracts
- module-manifest updates only when required to support family-local rendering without top-level tool branching

### Out of scope

- posture/query ownership in `shell.py`
- shell chrome and layout persistence in `portal.js`, except where tests must acknowledge existing compatibility aliases
- feature expansion inside the tools
- removing the public `inspector` compatibility alias in this sequence

## 3. Exact Repo Evidence

- `docs/contracts/tool_operating_contract.md`
  - already requires the three canonical region families and explicitly says tools should not add new shell-level renderer kinds
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
  - top-level control-panel renderer still branches on CTS-GIS via `region.surface_label === "CTS-GIS"` and `region.state_directive_compact`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  - top-level workbench renderer still branches on `surfacePayload.kind === "aws_csm_workspace"`, `system_workspace`, `network_system_log_workspace`, `workbench_ui_surface`, and `tool_secondary_evidence`
  - CTS-GIS workbench evidence still branches on `surfacePayload.tool_id === "cts_gis"`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - top-level interface-panel renderer still branches on `region.kind === "aws_csm_inspector"`, `network_system_log_inspector`, and `tool_mediation_panel`
  - CTS-GIS still enters through `region.interface_body.kind === "cts_gis_interface_body"`
  - the file is currently 1542 lines, which is already a signal that the host still owns too much specialized content
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - already centralizes readiness/warning resolution and wrapper states; this is the right compatibility seam for the migration
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`
  - already behaves like a proper shell host: it routes each region to its family renderer without inspecting tool identity
- runtime emitters still send legacy branch keys that drive the hosts:
  - `portal_system_workspace_runtime.py` emits `system_workspace`
  - `portal_shell_runtime.py` emits `network_system_log_workbench` and `network_system_log_inspector`
  - `portal_aws_runtime.py` emits `aws_csm_workspace` and `aws_csm_inspector`
  - `portal_workbench_ui_runtime.py` emits `workbench_ui_surface`
  - `portal_cts_gis_runtime.py` emits `tool_mediation_panel`, `tool_secondary_evidence`, and `cts_gis_interface_body`
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - currently proves the module registry and still asserts CTS-GIS-specific renderer tokens
- `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - currently asserts `cts_gis_interface_body`, current inspector/workbench kinds, and posture behavior

## 4. Target State

- `v2_portal_shell_region_renderers.js` becomes the `directive_panel` host, not a surface-label switchboard.
- `v2_portal_workbench_renderers.js` becomes the `reflective_workspace` host, not a `surfacePayload.kind` switchboard.
- `v2_portal_inspector_renderers.js` becomes the `presentation_surface` host, not a `region.kind` and `interface_body.kind` switchboard.
- `v2_portal_tool_surface_adapter.js` remains the compatibility layer for readiness, warnings, wrapper states, and direct-query helpers.
- Tool-local richness remains allowed, but it must enter through family-scoped data or registered local modules behind the family host, not through top-level host branching.
- `v2_portal_shell_core.js` stays shell-shaped and should not gain tool-specific dispatch.

### Change placement

- Runtime emitters may change to provide family-normalized payloads and compatibility markers.
- Family-host changes belong in the static renderer files and the asset manifest when needed.
- `shell.py` is out of scope except for tests or documentation references.

## 5. Staged Execution Slices

### Stage 1: Add family-normalized payload markers without retiring current branches

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- Exact behavior expected to change:
  - each region payload gains family-normalized metadata or structure that the family hosts can consume
  - current `kind`, `tool_secondary_evidence`, `state_directive_compact`, and `interface_body.kind` fields stay in place for compatibility
- Compatibility adapters or temporary aliases required:
  - all existing top-level host branches remain during this stage
- Retirement gate:
  - every canonical route emits enough family-scoped metadata that host migration can begin without discovering payload semantics later

### Stage 2: Migrate the directive-panel host first

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Exact behavior expected to change:
  - top-level control-panel rendering consumes a `directive_panel` contract instead of branching on `surface_label === "CTS-GIS"`
  - CTS-GIS directive content is still allowed, but it arrives through a documented compatibility adapter or family-local structure rather than a host-level identity check
- Compatibility adapters or temporary aliases required:
  - `state_directive_compact` may remain temporarily as the CTS-GIS compatibility input
- Retirement gate:
  - no primary-path branch in `v2_portal_shell_region_renderers.js` depends on tool label or tool identity

### Stage 3: Migrate the reflective-workspace host

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Exact behavior expected to change:
  - `PortalShellWorkbenchRenderer` stops using `surfacePayload.kind` as its primary dispatch table
  - `SYSTEM`, `NETWORK`, `AWS-CSM`, `Workbench UI`, and tool secondary evidence all render through one reflective-workspace host contract
  - CTS-GIS secondary evidence remains workbench-only, but the top-level host no longer branches on `tool_id === "cts_gis"` in the primary path
- Compatibility adapters or temporary aliases required:
  - the legacy `surfacePayload.kind` map may remain as a fallback during this stage
- Retirement gate:
  - the workbench host can render every canonical route without needing a new top-level `surfacePayload.kind` branch

### Stage 4: Migrate the presentation-surface host and shrink CTS-GIS specialization

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - `MyCiteV2/instances/_shared/portal_host/app.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Exact behavior expected to change:
  - `PortalShellInspectorRenderer` stops using `region.kind` and `interface_body.kind` as its primary authority
  - CTS-GIS Diktataograph/Garland content remains available, but it moves behind a presentation-surface contract or a family-local registered module rather than a top-level host branch
  - AWS, NETWORK, FND-DCM, FND-EBI, `SYSTEM`, and `workbench_ui` use the same presentation-surface wrapper and fallback policy
- Compatibility adapters or temporary aliases required:
  - `aws_csm_inspector`, `network_system_log_inspector`, `tool_mediation_panel`, and `cts_gis_interface_body` remain accepted only during the cutover window
- Retirement gate:
  - the top-level interface-panel host no longer requires tool-identity or legacy body-kind branching in its primary path

### Stage 5: Retire compatibility branches without touching public alias retirement

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Exact behavior expected to change:
  - family hosts delete compatibility branches that are no longer reached
  - no public route, query contract, or shell-region set changes
- Compatibility adapters or temporary aliases required:
  - keep `regions.inspector` and `inspector_collapsed` compatibility aliases out of scope for this sequence
- Retirement gate:
  - new regressions fail architecture tests if they reintroduce top-level tool branches

## 6. Risks And Anti-Patterns

- Renaming legacy `kind` fields to family-flavored names while leaving the same top-level branch structure intact.
- Moving canonical query or `tool_state` decisions into client code because the renderer already sees the interaction.
- Treating the presence of a registered module as permission to add a new shell-level renderer family.
- Migrating only the workbench and interface-panel hosts while leaving `directive_panel` on a CTS-GIS special case.
- Using the renderer pass to blur `SYSTEM` workbench responsibilities with `workbench_ui`’s SQL inspection role.
- Attempting public `inspector` alias retirement in the same sequence and turning a renderer migration into a schema break.

## 7. Definition Of Done

- The top-level control-panel, workbench, and interface-panel hosts dispatch by family contract, not by tool identity.
- CTS-GIS still renders correctly, but its specialization no longer owns the top-level host contract.
- Shared wrapper states continue to come from `v2_portal_tool_surface_adapter.js`.
- `v2_portal_shell_core.js` remains shell-shaped and unaware of tool-specific render decisions.
- No new shell regions or shell-level renderer kinds were added to achieve the migration.
