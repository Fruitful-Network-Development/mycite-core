# Shared Platform Stabilization

## PROMPT:

Work only inside `MyCiteV2/`.

The AWS slices are already complete.
Do not touch AWS semantics unless a small normalization is strictly required.

Implement only the remaining shared platform stabilization needed to make future tools drop into a stable host.

Read first:
- `MyCiteV2/docs/plans/authority_stack.md`
- `MyCiteV2/docs/ontology/structural_invariants.md`
- `MyCiteV2/docs/contracts/import_rules.md`
- `MyCiteV2/docs/testing/architecture_boundary_checks.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/maps_follow_on_surface.md`
- the currently implemented admin/AWS runtime, shell, and tests

Goal:
Normalize the already-proven Admin Band 0 + AWS read-only + AWS narrow-write patterns into one stable shared platform for later tools.

Implement only:
1. one canonical shell-owned tool descriptor / registry contract
2. one canonical runtime entrypoint catalog / launch contract
3. one normalized admin runtime envelope for shell + tool entrypoints
4. one explicit future-tool drop-in contract in code/docs
5. one deployable V2 admin cutover surface

Do not implement:
- Maps semantics
- AGRO-ERP semantics
- new tool slices
- new adapters beyond what shared-platform normalization strictly requires
- dynamic package scanning
- second registries or second runtime catalogs

Preserve:
- shell-owned legality
- runtime as composition only
- AWS read-only behavior
- AWS narrow-write bounded field set
- read-after-write confirmation
- accepted-write audit emission

Tests required:
- registry/descriptor tests
- runtime entrypoint catalog tests
- launch-envelope / denied/gated behavior tests
- regression proving Admin Band 0, AWS read-only, and AWS narrow-write still pass
- architecture-boundary tests proving no bypass, no dynamic-discovery authority, and no second convenience shell

Return:
1. exact files created or updated
2. shared platform surfaces implemented
3. what existing Admin/AWS surfaces were normalized rather than redesigned
4. tests run and results
5. whether the codebase is now in the stable drop-in state for individual tool development
6. the exact next prompt to begin the first Maps slice

---

## OUTPUT:

**Files**
No files were created or updated in this pass. The `MyCiteV2/` worktree is clean, and the requested shared-platform/cutover surfaces are already present and verified.

Key existing files verified:
- [runtime_platform.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/runtime_platform.py)
- [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py)
- [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py)
- [admin_aws_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py)
- [post_aws_tool_platform/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md)
- [future_tool_drop_in_contract.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md)
- [v2_admin_cutover_readiness.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_admin_cutover_readiness.md)

**Shared Platform**
The stable host model is implemented through:
- shell-owned `AdminToolRegistryEntry` descriptors with `catalog-driven`, `deny-by-default`, `shell-owned-registry`, `read-only`, and `bounded-write` contract fields
- static `AdminRuntimeEntrypointDescriptor` catalog in `runtime_platform.py`
- shared admin runtime envelope via `build_admin_runtime_envelope`
- shared denied/unavailable error shape via `build_admin_runtime_error`
- post-AWS docs for tool descriptors, runtime catalog, launch envelopes, read-only/write patterns, future drop-in work, and V2 cutover readiness

**Normalized, Not Redesigned**
Existing Admin/AWS behavior is preserved:
- Admin Band 0 remains the shell/home/registry base.
- AWS read-only remains read-only.
- AWS narrow-write remains bounded.
- Read-after-write confirmation remains required.
- Accepted-write local audit remains required.
- Runtime remains composition-only.
- No dynamic package scanning, second registry, second shell, Maps semantics, or AGRO-ERP semantics were added.

**Tests**
Ran the full regression stack for MVP, Admin Band 0, AWS read-only, AWS narrow-write, and shared platform/cutover tests.

Result: `Ran 90 tests in 0.161s` and `OK`.

Also ran `py_compile` on:
- `runtime_platform.py`
- `admin_runtime.py`
- `admin_aws_runtime.py`
- `admin_shell.py`

Result: passed.

**Stable Drop-In State**
Yes. The codebase is already in the intended stable drop-in state for individual tool development. Future tools can be added with one slice file, one semantic owner, one seam, one adapter family if needed, one runtime entrypoint, one shell-owned descriptor, and one test/gate set.

**Exact Next Prompt**
```text
Work only inside `MyCiteV2/`.

Implement the first Maps read-only admin tool slice only.

Read first:
- `MyCiteV2/docs/plans/authority_stack.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/tool_descriptor_contract.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/runtime_entrypoint_catalog.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/maps_follow_on_surface.md`
- the current Admin Band 0 and AWS tests

Implement one narrow Maps read-only slice only:
- one Maps slice file if missing or incomplete
- one Maps semantic owner
- one Maps read-only port seam
- one Maps adapter family if needed
- one runtime entrypoint
- one shell-owned registry descriptor
- one test/gate set

Do not implement Maps writes, AGRO-ERP, sandboxes, dynamic discovery, flavor runtime code, or broad public rollout.
Preserve Admin Band 0 and AWS behavior.
Run the regression stack proving MVP, Admin Band 0, AWS read-only, AWS narrow-write, and the new Maps slice all pass.
```

---