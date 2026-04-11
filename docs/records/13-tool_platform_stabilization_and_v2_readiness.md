# Tool Platform Stabilization & V2 Readiness

## PROMPT:

Work only inside `MyCiteV2/`.

Treat the following as already complete, passing, and authoritative:
- architecture MVP
- `Admin Band 0 Internal Admin Replacement`
- `admin_band1.aws_read_only_surface`
- `admin_band2.aws_narrow_write_surface`

Your task is not to implement Maps or AGRO-ERP yet.

Your task is to complete the single largest remaining shared-platform pass that will make future tool development streamlined and make MyCiteV2 stably deployable as the replacement admin portal.

This pass is:
`Post-AWS Tool Platform Stabilization And V2 Cutover Readiness`

Optimize for:
- maximum remaining shared-platform completion in one pass
- preserving v2 structural integrity
- making future tools drop into a stable, consistent host
- minimizing future prompt size
- making v2 operationally replace the old admin portal
- leaving Maps and AGRO-ERP to be developed individually afterward

Do not implement Maps semantics.
Do not implement AGRO-ERP semantics.
Do not start broad client-facing rollout.
Do not reintroduce v1 mixed provider-admin structure.

==================================================
PRIMARY GOAL
==================================================

Finish the shared post-AWS platform so that:

1. MyCiteV2 has one stable deployable admin shell/runtime core.
2. the old admin portal can begin to be displaced operationally by v2.
3. future tools can be developed individually by plugging into a stable shell/registry/runtime/tool contract.
4. later tool work does not need to rediscover shell legality, launch policy, runtime envelope, rollout gates, read-only pattern, bounded-write pattern, or audit/read-after-write behavior.

This pass should complete as much remaining shared development as possible without crossing into Maps or AGRO-ERP semantics.

==================================================
READ FIRST
==================================================

Read and follow, in order:

1. `MyCiteV2/README.md`
2. `MyCiteV2/docs/plans/authority_stack.md`
3. `MyCiteV2/docs/ontology/structural_invariants.md`
4. `MyCiteV2/docs/ontology/dependency_direction.md`
5. `MyCiteV2/docs/ontology/interface_surfaces.md`
6. `MyCiteV2/docs/contracts/import_rules.md`
7. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
8. `MyCiteV2/docs/plans/phase_completion_definition.md`
9. `MyCiteV2/docs/testing/phase_gates.md`
10. `MyCiteV2/docs/plans/post_mvp_rollout/README.md`
11. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
12. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
13. `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
14. `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`
15. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/README.md`
16. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
17. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md`
18. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/maps_follow_on_surface.md`
19. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/agro_erp_follow_on_surface.md`
20. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`
21. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_shell_entry.md`
22. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band1_aws_read_only_surface.md`
23. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band2_aws_narrow_write_surface.md`
24. `MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md`
25. `MyCiteV2/docs/testing/slice_gate_template.md`

Also read the currently implemented supporting surfaces:
- `MyCiteV2/packages/state_machine/hanus_shell/`
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
- `MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py`
- `MyCiteV2/packages/modules/cross_domain/local_audit/`
- `MyCiteV2/packages/ports/audit_log/`
- `MyCiteV2/packages/adapters/filesystem/audit_log.py`
- `MyCiteV2/packages/ports/aws_read_only_status/`
- `MyCiteV2/packages/modules/cross_domain/aws_operational_visibility/`
- `MyCiteV2/packages/adapters/filesystem/aws_read_only_status.py`
- `MyCiteV2/packages/ports/aws_narrow_write/`
- `MyCiteV2/packages/modules/cross_domain/aws_narrow_write/`
- `MyCiteV2/packages/adapters/filesystem/aws_narrow_write.py`
- the current runtime tests, registry tests, AWS tests, and architecture-boundary tests

Use v1 only as lower-precedence evidence if absolutely needed.
Do not copy v1 layout.

==================================================
IMPORTANT REFINEMENT
==================================================

Do not invent a broad generic framework if the existing AWS-backed implementation can be normalized into shared contracts more directly.

This pass should:
- extract or normalize only what AWS has already proven once
- avoid creating parallel abstractions
- avoid speculative “future framework” work
- prefer hardening and reusing the existing shell/registry/runtime/catalog patterns in place when possible

If an existing surface can be normalized instead of replaced, normalize it.
Do not create duplicate registries, duplicate runtime catalogs, or duplicate tool descriptor systems.

==================================================
IMPLEMENT ONLY SHARED PLATFORM / CUTOVER WORK
==================================================

Implement the largest safe shared-platform chunk only.

This pass should complete the reusable substrate for later tools, including:

1. canonical tool descriptor / registry contract
   - shell-owned discoverability
   - deny-by-default by default
   - catalog-driven, not dynamic package scanning
   - future tools can register through a stable descriptor shape without owning shell legality
   - the contract should reflect what the AWS slices already proved in practice

2. canonical runtime entrypoint catalog / launch contract
   - one stable way runtime entrypoints are declared, named, and composed
   - stable per-tool launch envelope
   - no tool bypass around the shell registry
   - normalize the current admin and AWS runtime entrypoints into this contract without changing their semantics unnecessarily

3. tenant-safe admin runtime envelope hardening
   - consistent request/response envelope for shell + tool runtime entrypoints
   - consistent gated/denied/unavailable result handling
   - consistent rollout-band and audience handling
   - consistent launch-via-registry behavior

4. post-AWS read-only / bounded-write / audit pattern normalization
   - make the established AWS patterns reusable for later tools
   - specifically:
     - read-only tool surface pattern
     - bounded-write tool surface pattern
     - read-after-write confirmation pattern
     - accepted-write audit emission pattern
   - do this without moving semantics into runtime or adapters
   - do this without broadening the existing AWS slices

5. deployable v2 admin cutover surface
   - one clear v2 admin landing/runtime surface
   - one clear legacy-isolation or replacement rule
   - no second parallel convenience shell
   - enough deployment-facing readiness to treat v2 as the stable admin portal base

6. future-tool drop-in contract
   - make it so later tool work can proceed individually by implementing:
     - one slice file
     - one seam
     - one adapter family if needed
     - one runtime entrypoint
     - one registry descriptor
     - one test/gate set
   - without re-solving shell/runtime policy

==================================================
DO NOT IMPLEMENT
==================================================

Do not implement:
- Maps semantics
- AGRO-ERP semantics
- PayPal follow-on
- analytics
- progeny/workbench resurrection
- sandboxes
- broad public rollout
- extra runtime flavors
- direct provider-admin parity surfaces
- broad tool framework features not required for stable drop-in development

This is not a tool-semantics pass.
This is a shared platform hardening and cutover pass.

==================================================
EXPECTED CODE / DOC SURFACE
==================================================

Implement only the minimum shared surfaces needed to make later per-tool work streamlined and consistent.

Possible areas include, only if justified by the existing repo structure:
- a shared tool descriptor/registry contract location
- shared runtime entrypoint catalog support under `instances/_shared/runtime/`
- shell/registry support only where needed to stabilize the shared drop-in model
- deployment/cutover docs under `docs/plans/post_mvp_rollout/`
- one ADR for the post-AWS tool-platform stabilization decision if required

Prefer normalizing existing locations over adding new roots.
Do not create `packages/tools/_shared/` unless the existing structure truly needs it.
Do not create a second source of truth for registry or runtime catalog data.

==================================================
OWNERSHIP RULES
==================================================

Preserve all existing boundaries:

- shell owns discoverability and launch legality
- runtime composes only
- tools do not define shell legality
- ports own contracts, not semantics
- adapters own outward details, not semantics
- domain/cross-domain modules own semantics
- no dynamic package scanning as the source of truth
- no tool registry that silently becomes a second shell
- no direct provider route becomes the admin portal replacement

Do not weaken or rewrite the already-proven AWS slice ownership just to create a shared model.
The shared model must be derived from the correct existing boundaries.

==================================================
PRESERVE EXISTING AWS BEHAVIOR
==================================================

The AWS read-only and AWS narrow-write slices are now the reference implementations for later tools.

Do not change their field sets or operational meaning unless a small normalization is strictly required for shared-platform consistency.

Specifically:
- keep AWS read-only read-only
- keep the AWS narrow-write field set explicitly bounded
- keep read-after-write confirmation
- keep accepted-write local-audit emission
- keep registry-launched behavior
- keep Admin Band 0 shell/home/registry behavior intact

==================================================
DEPLOYABLE-V2 RULE
==================================================

At the end of this pass, the codebase should be able to support this statement:

“MyCiteV2 is now a stable admin portal base. Future tools can be added individually into a fixed shell, registry, runtime, gate, and audit model.”

That does not mean every tool is built.
It means the shared host/platform work is complete enough that tool work becomes mostly local.

==================================================
TESTS REQUIRED
==================================================

Add only the tests required to prove this shared-platform/cutover state.

At minimum include:

1. registry/descriptor tests
2. runtime entrypoint catalog tests
3. shared launch-envelope / denied/gated behavior tests
4. regression tests proving existing Admin Band 0, AWS read-only, and AWS narrow-write slices still work under the stabilized shared model
5. architecture-boundary tests proving:
   - shell still owns legality
   - runtime still composes only
   - tools cannot bypass registry policy
   - no dynamic scan becomes authoritative
   - no second convenience shell emerges
   - no `mycite_core` imports appear

Also rerun the minimum regression stack needed to prove:
- MVP still passes
- Admin Band 0 still passes
- AWS read-only still passes
- AWS narrow-write still passes
- the new shared-platform/cutover layer passes

==================================================
DOCUMENTATION RULE
==================================================

Update docs only where necessary to align the stabilized shared-platform state, especially in:
- `runtime_entrypoints.md`
- `port_adapter_ownership_matrix.md`
- `client_exposure_gates.md`
- `agent_prompt_templates.md`
- the relevant admin-first docs
- one new post-AWS tool-platform/cutover doc subtree if needed
- one ADR if required

Prefer concrete operational docs over narrative prose.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:

- the shared tool-registry/entrypoint/drop-in model is explicit and implemented
- the admin runtime/shell base is stable enough to be treated as the deployable v2 admin core
- the old portal can begin to be displaced operationally by v2
- future tools can be developed individually against a stable consistent host model
- the already-implemented AWS slices remain behaviorally intact
- no forbidden scope expansion occurred
- regression tests pass

==================================================
END-OF-TASK RESPONSE
==================================================

Return:

1. the exact files created or updated
2. the shared platform surfaces implemented
3. the deployable-v2/cutover surfaces implemented
4. the exact future-tool drop-in contract established
5. what existing AWS/Admin surfaces were normalized rather than redesigned
6. the tests run and their results
7. whether the codebase is now in the intended “stable consistent core for individual tool development” state
8. what the next prompt should be to begin Maps as the first post-AWS follow-on tool
9. any blocked ambiguities that should remain deferred

---


## OUTPUT

**Files**
- Created port seam files: [README.md](/srv/repo/mycite-core/MyCiteV2/packages/ports/aws_narrow_write/README.md), [contracts.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/aws_narrow_write/contracts.py), [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/aws_narrow_write/__init__.py)
- Created semantic-owner files: [README.md](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_narrow_write/README.md), [service.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_narrow_write/service.py), [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_narrow_write/__init__.py)
- Created adapter and recovery docs: [aws_narrow_write.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/aws_narrow_write.py), [aws_narrow_write_recovery.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_narrow_write_recovery.md)
- Created tests: [test_aws_narrow_write.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_aws_narrow_write.py), [test_aws_narrow_write_contracts.py](/srv/repo/mycite-core/MyCiteV2/tests/contracts/test_aws_narrow_write_contracts.py), [test_filesystem_aws_narrow_write_adapter.py](/srv/repo/mycite-core/MyCiteV2/tests/adapters/test_filesystem_aws_narrow_write_adapter.py), [test_admin_aws_narrow_write_runtime.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_aws_narrow_write_runtime.py), [test_aws_narrow_write_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_aws_narrow_write_boundaries.py), [test_aws_narrow_write_port_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_aws_narrow_write_port_boundaries.py), [test_filesystem_aws_narrow_write_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_aws_narrow_write_boundaries.py)
- Updated runtime and shell files: [admin_aws_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py), [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py), [README.md](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/README.md), [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py), [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/__init__.py), [README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/README.md), [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/__init__.py), [README.md](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/README.md)
- Updated tests and rollout docs: [test_state_machine_admin_shell.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_state_machine_admin_shell.py), [test_admin_runtime_composition.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_runtime_composition.py), [test_filesystem_adapter_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py), [runtime_entrypoints.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md), [port_adapter_ownership_matrix.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md), [aws_first_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md), [frozen_decisions_admin_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md), [admin_band2_aws_narrow_write_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band2_aws_narrow_write_surface.md)
- Left alone: [12-admin_band_2_aws_narrow_write_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/archive/12-admin_band_2_aws_narrow_write_surface.md) was already dirty and was not touched for this slice

**Outcome**
- Seam and adapter implemented: `packages/ports/aws_narrow_write/` with `AwsNarrowWritePort`, `AwsNarrowWriteRequest`, `AwsNarrowWriteResult`, `AwsNarrowWriteSource`; adapter `FilesystemAwsNarrowWriteAdapter` in [aws_narrow_write.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/aws_narrow_write.py).
- Exact bounded field set chosen: `selected_verified_sender` only. No other AWS field is writable in this slice.
- Runtime entrypoint added: `admin.aws.narrow_write`, implemented by [run_admin_aws_narrow_write](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py).
- Read-after-write behavior: the adapter updates the caller-supplied AWS snapshot file, rereads it immediately, the semantic layer normalizes that confirmed state through the existing read-only visibility model, and the runtime returns that confirmed read-only surface in the write result.
- Local-audit behavior: accepted writes emit one `aws.operational.write.accepted` record through existing [LocalAuditService](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/local_audit/service.py) plus the existing `audit_log` port and filesystem audit adapter. The audit payload records tenant scope, profile id, updated fields, selected sender, and canonical focus subject.
- Minimal shell/registry changes: the shell-owned registry gained one approved `aws_narrow_write` entry and launch resolver for `admin.aws.narrow_write`; `admin.shell_entry` still redirects AWS slices through the registry and no dynamic discovery or registry redesign was added.
- Tests run: targeted AWS narrow-write stack ran `28` tests, `OK`. Full regression stack across MVP, Admin Band 0, AWS read-only, and AWS narrow-write ran `84` tests, `OK`.
- `admin_band2.aws_narrow_write_surface` is now satisfied within the approved scope.
- What remains before Maps follow-on: no more AWS expansion is required for this slice. The next prompt can start the first Maps slice by defining or implementing its own narrow seam, adapter, runtime entrypoint, and registry entry through the existing admin shell and runtime catalog, without changing the two AWS slices.
- Deferred ambiguities that should stay frozen: whether any AWS writable field beyond `selected_verified_sender` is ever approved, whether dispatch-health gets a later AWS follow-up slice, whether admin home and tool registry eventually merge into one shell payload, and the exact first Maps seam/adapter names.

The requested `Post-AWS Tool Platform Stabilization And V2 Cutover Readiness` pass is already implemented in the current `MyCiteV2/` tree, and I did not create duplicate registry/runtime/framework surfaces. I verified the implementation as-is; `git status --short MyCiteV2` is clean.

**Files**
The shared platform/cutover implementation is centered on:

- [runtime_platform.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/runtime_platform.py)
- [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py)
- [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py)
- [admin_aws_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py)
- [test_admin_tool_platform_contract.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_admin_tool_platform_contract.py)
- [test_admin_runtime_platform_contracts.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_runtime_platform_contracts.py)
- [post_aws_tool_platform/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md)
- [future_tool_drop_in_contract.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md)
- [v2_admin_cutover_readiness.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_admin_cutover_readiness.md)
- [decision_record_0012_post_aws_tool_platform_stabilization.md](/srv/repo/mycite-core/MyCiteV2/docs/decisions/decision_record_0012_post_aws_tool_platform_stabilization.md)

**Implemented Surfaces**
- Shared platform surfaces: shell-owned `AdminToolRegistryEntry` descriptors, static runtime entrypoint descriptors, shared runtime envelope construction, explicit read-only and bounded-write patterns, and boundary tests preventing dynamic discovery or bypass routes.
- Deployable V2/cutover surfaces: `admin.shell_entry` remains the intended admin landing path, `runtime_platform.py` is the admin runtime catalog, and docs define slice-by-slice operational displacement of the old portal without route-level parity porting.
- Future-tool drop-in contract: one slice file, one semantic owner, one seam, one adapter family if needed, one runtime entrypoint, one shell-owned registry descriptor, and one test/gate set.
- Normalized rather than redesigned: Admin Band 0 behavior, AWS read-only behavior, AWS narrow-write behavior, registry-launched execution, read-after-write confirmation, and accepted-write audit emission.

**Verification**
Ran the required regression stack across MVP, Admin Band 0, AWS read-only, AWS narrow-write, and the shared platform layer:

`Ran 90 tests in 0.161s`  
`OK`

Also ran `py_compile` on the runtime/platform modules; all passed.

**Status**
Yes, the codebase is now in the intended stable-consistent-core state for individual tool development. Future tools can plug into the fixed shell, registry, runtime catalog, envelope, gate, read-only/write, and audit patterns without re-solving shared platform policy.

**Next Prompt**
Implement the first Maps slice as a narrow read-only admin tool slice. The prompt should point to [future_tool_drop_in_contract.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md), [read_only_and_bounded_write_patterns.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md), and [maps_follow_on_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/maps_follow_on_surface.md), then require one Maps slice file, seam, adapter, runtime entrypoint, registry descriptor, and tests.

Deferred ambiguities: exact first Maps boundary, whether Maps requires reopening `mediation_surface`, Maps seam/adapter names, and environment-specific traffic cutover from old admin routes.

---