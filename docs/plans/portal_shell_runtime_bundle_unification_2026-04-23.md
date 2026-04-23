# Portal Shell Runtime Bundle Unification

Date: 2026-04-23

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## 1. Purpose

Unify server-side runtime bundle assembly so the shell has one shared surface-bundle contract instead of a segmented root/tool dispatcher with duplicated envelope construction.

This plan exists separately because it is the highest-risk server-side slice. It must land before client renderer retirement so the browser is consuming one stable assembly contract instead of a moving set of special cases.

## 2. In-Scope vs Out-of-Scope

### In scope

- `portal_shell_runtime.py` surface selection, bundle orchestration, and runtime-envelope assembly
- direct tool entrypoints that currently rebuild composition and envelopes separately
- bundle signature alignment across `SYSTEM`, `NETWORK`, `UTILITIES`, and tool surfaces
- tests that prove shell-route and direct-route bundle behavior stay aligned

### Out of scope

- shell authority in `MyCiteV2/packages/state_machine/portal_shell/shell.py` except for test references
- client-side renderer rewrites
- tool-specific feature backlog such as AWS action affordances, CTS-GIS data readiness, or FND-EBI analytics
- changing canonical query vocabularies beyond restoring already-contracted behavior

## 3. Exact Repo Evidence

- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - imports every tool/root builder directly at module scope
  - `_tool_bundle_for_surface()` still uses open-coded `if surface_id == ...` dispatch
  - `_bundle_for_surface()` still mixes selection, tool/root branching, inline `NETWORK`/`UTILITIES` payload generation, and bundle assembly
  - `run_portal_shell_entry()` still builds the final envelope after surface-specific bundle generation
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `build_portal_workbench_ui_surface_bundle()` accepts `surface_query`
  - `run_portal_workbench_ui()` passes `surface_query`
- verified on 2026-04-23:
  - `run_portal_shell_entry()` for `system.tools.workbench_ui` drops incoming `surface_query` and falls back to the fresh-entry default query because `_tool_bundle_for_surface()` does not forward `surface_query`
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - keeps a private `_runtime_envelope_from_bundle()` even though shell runtime already owns an envelope builder
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `run_portal_cts_gis()` rebuilds composition and the final envelope locally
- `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `run_portal_fnd_dcm()` rebuilds composition and the final envelope locally
- `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `run_portal_fnd_ebi()` rebuilds composition and the final envelope locally
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - currently asserts that runtime-owned tool query normalization uses the shared helper, but does not yet assert that shell-route and direct-route assembly share the same bundle path
- `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
  - covers direct `Workbench UI` behavior thoroughly, but not the shell-route query handoff
- `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - already locks posture and canonical URL behavior for tool routes, so this is the main regression gate for the unified assembler

## 4. Target State

- `portal_shell_runtime.py` owns request normalization, selection resolution, shared bundle orchestration, and final runtime-envelope assembly.
- Each surface-specific runtime file owns only payload generation plus surface-local canonical route/query details that are already part of its public contract.
- Direct tool endpoints keep their existing routes and schemas, but become thin wrappers around the same bundle assembly and envelope path that the shell route uses.
- `build_shell_composition_payload()` remains the sole first-load posture authority.
- Runtime-owned query handling stays centralized in `canonical_query_for_surface_query()` and `canonical_query_for_runtime_request_payload()`.
- Reducer-owned surfaces remain reducer-owned. This plan does not flatten CTS-GIS or FND-EBI into the runtime-owned query model.

### Change placement

- This plan belongs in runtime bundle assembly first.
- `shell.py` should not be edited for new bundle branching or posture work as part of this slice.
- Client renderers should only change after the bundle contract is stable enough to consume.

## 5. Staged Execution Slices

### Stage 1: Normalize the shell-route bundle call contract

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- Exact behavior expected to change:
  - every runtime-owned surface builder reached from `run_portal_shell_entry()` receives the normalized `surface_query` it already expects
  - `system.tools.workbench_ui` shell-route behavior matches the direct endpoint for canonical query projection
  - no user-visible posture or renderer-kind changes yet
- Compatibility adapters or temporary aliases required:
  - direct `run_portal_workbench_ui()` remains public and unchanged at the route/schema level
- Retirement gate:
  - no runtime-owned surface builder can be called from shell-route assembly without its contracted normalized query inputs

### Stage 2: Replace segmented surface dispatch with one shared bundle registry

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - `MyCiteV2/tests/unit/test_portal_shell_contract.py`
- Exact behavior expected to change:
  - `portal_shell_runtime.py` stops owning an open-coded per-surface branch table for tool bundles
  - all surface builders return one normalized bundle shape that the shell runtime can compose without knowing tool-specific field names
  - `NETWORK` and `UTILITIES` bundle generation follows the same return contract as `SYSTEM` and the tools, even if helper functions temporarily stay in `portal_shell_runtime.py`
- Compatibility adapters or temporary aliases required:
  - legacy extra bundle keys may remain while direct endpoints are still being collapsed
- Retirement gate:
  - `_tool_bundle_for_surface()` is removed or reduced to data-driven registry lookup with no surface-specific orchestration logic left in the branch body

### Stage 3: Collapse duplicate direct-entry envelope builders

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- Exact behavior expected to change:
  - direct `/portal/api/v2/system/tools/...` entrypoints and the shell route use the same composition and final-envelope assembly logic
  - canonical route, query, URL, reducer-owned flag, and shared warnings/error handling come from one path
  - direct endpoints remain route-stable and schema-stable
- Compatibility adapters or temporary aliases required:
  - public direct endpoints stay in place as thin wrappers
- Retirement gate:
  - duplicate `_runtime_envelope_from_bundle()` or inline `build_shell_composition_payload()` plus `build_portal_runtime_envelope()` blocks are removed from direct runtime files

### Stage 4: Tighten shared bundle assertions for later renderer migration

- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- Exact behavior expected to change:
  - the shared bundle contract becomes explicit enough for region-family renderers to rely on it
  - the shell runtime treats surface-specific payload content as opaque bundle data rather than inline orchestration knowledge
- Compatibility adapters or temporary aliases required:
  - existing legacy `kind` fields may remain until the renderer plan retires them
- Retirement gate:
  - no later renderer slice needs to rediscover how a selected surface becomes a bundle or which path owns canonical route/query/url

## 6. Risks And Anti-Patterns

- Fixing `workbench_ui` shell-route query drift inside the client instead of restoring the missing runtime assembly input.
- Re-implementing the registry as a second posture authority or as a second query-normalization path.
- Flattening reducer-owned and runtime-owned tool surfaces into one fake ownership model to simplify the code.
- Extracting network/utilities behavior into ad hoc helpers without first locking the shared bundle return contract.
- Leaving direct tool entrypoints on their own private composition/envelope builders after the shell path is unified.

## 7. Definition Of Done

- `portal_shell_runtime.py` assembles all surfaces through one shared bundle contract.
- Direct tool entrypoints reuse that same contract and final envelope path.
- `system.tools.workbench_ui` shell-route and direct-route query behavior are aligned and tested.
- No runtime slice in this plan moves posture, route authority, or query normalization out of the current canonical shell helpers.
- The bundle contract is stable enough that the renderer migration can proceed without rediscovering server-side assembly semantics.
