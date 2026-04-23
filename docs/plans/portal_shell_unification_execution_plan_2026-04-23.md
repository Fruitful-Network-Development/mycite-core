# Portal Shell Unification Execution Plan

Date: 2026-04-23

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## 1. Purpose

Define the stability-first merge order for the shell/runtime/renderer unification work and make retirement gates explicit so later agents can execute the program without rediscovering sequencing constraints.

## 2. In-Scope vs Out-of-Scope

### In scope

- execution order across the boundary, runtime, and renderer plans
- prerequisites, limited parallelism rules, and retirement gates
- repo-shape checkpoints after each stage

### Out of scope

- tool feature backlog from `docs/plans/one_shell_portal_refactor.md`
- public `inspector` alias retirement
- unrelated CTS-GIS data-fixture hardening except where it blocks the unification stages directly

## 3. Exact Repo Evidence

- the posture and route guardrails are already stabilized in contract and tests:
  - `docs/contracts/portal_shell_contract.md`
  - `docs/contracts/tool_operating_contract.md`
  - `docs/plans/one_shell_stabilization_matrix.md`
  - `MyCiteV2/tests/architecture/test_portal_shell_stabilization_matrix.py`
  - `MyCiteV2/tests/unit/test_portal_shell_contract.py`
- the remaining unification gaps are still split across runtime assembly and client hosts:
  - `portal_shell_runtime.py` still dispatches by surface builder
  - `v2_portal_shell_region_renderers.js`, `v2_portal_workbench_renderers.js`, and `v2_portal_inspector_renderers.js` still branch by tool-facing labels or payload kinds
- verified green on 2026-04-23:
  - `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
  - `python3 -m unittest MyCiteV2.tests.architecture.test_portal_shell_stabilization_matrix`
  - `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_contract`
  - `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`
- verified current drift on 2026-04-23:
  - `run_portal_shell_entry()` still drops `surface_query` for `system.tools.workbench_ui`

## 4. Target State

- boundary tests land first and stay green throughout the program
- runtime bundle assembly becomes shared before renderer retirement starts
- family-normalized payloads land before host branches are removed
- host migration proceeds family by family, not tool by tool
- compatibility branches retire only after tests prove they are no longer reached
- public `inspector` alias retirement is explicitly deferred to a later schema-revision plan

## 5. Staged Execution Slices

### Stage 1: Boundary freeze and missing guard tests

- Plans involved:
  - `portal_shell_boundary_map_and_system_workbench_split_2026-04-23.md`
- Exact files expected to change:
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_shell_contract.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
  - `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- Exact behavior expected to change:
  - no user-visible behavior change
  - failing tests begin to block `SYSTEM` versus `workbench_ui` blur, shell-authority drift, and new top-level tool branches in family hosts
- What must be done first:
  - this stage starts first and must merge before any unification code moves
- What can run in parallel:
  - only additive documentation updates
- Repo should look like after the stage:
  - current behavior still ships, but the missing guard rails are explicit and green
- Retirement gate:
  - do not start runtime bundle unification until the boundary freeze tests are merged

### Stage 2: Runtime bundle contract unification

- Plans involved:
  - `portal_shell_runtime_bundle_unification_2026-04-23.md`
- Exact files expected to change:
  - `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_fnd_ebi_runtime.py`
  - `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
  - the tests from Stage 1
- Exact behavior expected to change:
  - `workbench_ui` shell-route query handling is restored
  - bundle assembly becomes shared and direct tool entrypoints stop building composition/envelopes on their own
- What must not begin until this slice retires:
  - family-host branch retirement
  - any renderer work that assumes one stable shared bundle contract
- What can run in parallel:
  - only additive tests and docs that do not edit runtime assembly files
- Repo should look like after the stage:
  - server-side bundle assembly is unified, but legacy renderer kinds and compatibility fields are still present
- Retirement gate:
  - do not begin family-host retirement until direct and shell routes are on the same bundle/envelope path

### Stage 3: Family metadata and adapter foundation

- Plans involved:
  - `portal_shell_region_family_renderer_migration_2026-04-23.md`
- Exact files expected to change:
  - the runtime emitters above
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
  - `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
  - `MyCiteV2/tests/unit/test_portal_workspace_runtime_behavior.py`
- Exact behavior expected to change:
  - every canonical route emits enough family-scoped payload metadata for the hosts to consume
  - current host branches still exist, but they are no longer the only available contract
- What must not begin until this slice retires:
  - removing `surfacePayload.kind`, `region.kind`, or CTS-GIS compatibility branches
- What can run in parallel:
  - after this stage merges, the directive-panel and reflective-workspace host migrations may run as separate PRs only if their write sets stay disjoint
- Repo should look like after the stage:
  - runtime is unified and payloads carry both family metadata and temporary legacy fields
- Retirement gate:
  - do not delete legacy host branches until family metadata is asserted in tests

### Stage 4: Host migration by family, not by tool

- Plans involved:
  - `portal_shell_region_family_renderer_migration_2026-04-23.md`
- Exact files expected to change:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - runtime files that still emit temporary compatibility shapes
  - `MyCiteV2/instances/_shared/portal_host/app.py` if asset-manifest changes are needed
  - architecture and runtime tests
- Exact behavior expected to change:
  - each top-level host dispatches by region family
  - tool-local richness survives only behind family-local inputs or modules
- What must be done first:
  - migrate the directive-panel host before presentation-surface retirement because CTS-GIS currently spans both
- What can run in parallel:
  - after the shared adapter foundation lands, the directive-panel host and reflective-workspace host may run in parallel if:
    - one slice owns `v2_portal_shell_region_renderers.js`
    - one slice owns `v2_portal_workbench_renderers.js`
    - neither slice edits `v2_portal_tool_surface_adapter.js` concurrently
  - the presentation-surface host remains serial behind the CTS-GIS contract cleanup
- Repo should look like after the stage:
  - shell core is still unchanged, family hosts are primary, and legacy kind branches are fallback-only
- Retirement gate:
  - do not remove the fallback branches until all three family hosts are green on the canonical route set

### Stage 5: Compatibility retirement and closeout

- Plans involved:
  - `portal_shell_runtime_bundle_unification_2026-04-23.md`
  - `portal_shell_region_family_renderer_migration_2026-04-23.md`
- Exact files expected to change:
  - runtime files that still emit compatibility-only branch keys
  - the three static family hosts
  - architecture and runtime tests
- Exact behavior expected to change:
  - no user-facing route or posture change
  - compatibility-only runtime keys and top-level host branches are removed once they are no longer needed
- What must not begin until this slice retires:
  - unrelated tool feature work that would otherwise reintroduce local branching against obsolete compatibility fields
- What can run in parallel:
  - additive docs and audit updates only
- Repo should look like after the stage:
  - one shell authority path, one runtime bundle contract, and family-scoped client hosts with no top-level tool dispatch
- Retirement gate:
  - public `inspector` alias retirement remains explicitly deferred; do not fold it into this closeout

## 6. Risks And Anti-Patterns

- Starting renderer branch deletion before the runtime bundle contract is stable.
- Treating the work as three independent tool migrations instead of one shell/runtime/host sequencing problem.
- Letting presentation-surface work start before the CTS-GIS directive-panel contract is stabilized.
- Using parallelism on shared files like `v2_portal_tool_surface_adapter.js` and creating unnecessary merge conflicts in the highest-risk slice.
- Pulling public alias retirement into this plan and expanding the risk surface for no unification gain.

## 7. Definition Of Done

- The repo reaches family-scoped rendering through the documented stage order.
- Every stage leaves the repo in a mergeable state with green boundary, contract, and runtime tests.
- Runtime and renderer compatibility fields retire only after explicit gates, not by assumption.
- Follow-on tool feature work can proceed without rediscovering how shell authority, bundle assembly, and family hosts are supposed to fit together.
