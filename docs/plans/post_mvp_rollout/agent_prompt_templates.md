# Agent Prompt Templates

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

These templates exist so future prompts can stay small and still align with the post-MVP operating system.

## Template 1: Specify A Slice

```text
Work only inside `MyCiteV2/`.

Your task is to define or refine the slice file at `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/README.md`
3. `docs/plans/post_mvp_rollout/portal_rollout_bands.md`
4. `docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
5. `docs/plans/post_mvp_rollout/slice_registry/slice_template.md`
6. `docs/plans/post_mvp_rollout/client_exposure_gates.md`
7. `docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`

Do not implement code.
Do not widen scope beyond the slice file and directly supporting planning docs.
Set or confirm:
- slice status
- rollout band
- exposure status
- owning layers
- required ports
- required adapters
- runtime composition
- required tests
- out-of-scope items

Return the exact files updated, the final slice classification, and the next gate needed before implementation.
```

## Template 2: Implement An Approved Read-Only Slice

```text
Work only inside `MyCiteV2/`.

Implement only the approved read-only slice documented in `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/portal_rollout_bands.md`
3. `docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
4. `<slice_file>`
5. `docs/plans/post_mvp_rollout/client_exposure_gates.md`
6. `docs/plans/post_mvp_rollout/runtime_entrypoints.md`
7. `docs/testing/slice_gate_template.md`

Touch only the owning layers named in the slice file.
Do not touch unrelated worktree changes.
Do not add writable behavior.
Do not add tools, sandboxes, extra runtime paths, or flavor code.
Update the slice status and the gate record only if the implementation warrants it.
Return exact files changed, tests run, the runtime entrypoint touched, and whether the slice gate is now satisfied.
```

## Template 3: Implement An Approved Writable Slice

```text
Work only inside `MyCiteV2/`.

Implement only the approved writable slice documented in `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/portal_rollout_bands.md`
3. `docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
4. `<slice_file>`
5. `docs/plans/post_mvp_rollout/client_exposure_gates.md`
6. `docs/plans/post_mvp_rollout/runtime_entrypoints.md`
7. `docs/testing/slice_gate_template.md`

Implement only the bounded write surface named in the slice file.
Do not touch unrelated worktree changes.
Prove read-after-write, local audit emission, rollback clarity, and architecture boundaries.
Do not widen the writable field set.
Update the slice status and the gate record only if the implementation warrants it.
Return exact files changed, tests run, the runtime entrypoint touched, and remaining blockers.
```

## Template 4: Run A Slice Exposure Gate Review

```text
Work only inside `MyCiteV2/`.

Your task is to evaluate whether `<slice_file>` is ready for `<requested_band>` exposure.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/portal_rollout_bands.md`
3. `docs/plans/post_mvp_rollout/client_exposure_gates.md`
4. `docs/testing/slice_gate_template.md`
5. `<slice_file>`

Do not implement new features unless a tiny doc alignment fix is required.
Record pass or fail for each gate, list the blocking items, and state whether the slice is:
- still `candidate`
- `approved_for_build`
- `implemented_internal`
- `approved_for_exposure`
```

## Template 5: Specify An Admin-First Slice

```text
Work only inside `MyCiteV2/`.

Your task is to define or refine the admin-first slice file at `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/README.md`
3. `docs/plans/post_mvp_rollout/admin_first/README.md`
4. `docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
5. `docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`
6. `docs/plans/post_mvp_rollout/admin_first/tool_registry_and_launcher_surface.md`
7. `<slice_file>`
8. `docs/testing/slice_gate_template.md`

Do not implement code.
Do not widen scope beyond the slice file and directly supporting planning docs.
Return the exact files updated, the slice classification, and the next gate needed before implementation.
```

## Template 6: Implement An Approved Admin Shell Or Admin Surface Slice

```text
Work only inside `MyCiteV2/`.

Implement only the approved admin-first slice documented in `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/admin_first/README.md`
3. `docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
4. `docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`
5. `docs/plans/post_mvp_rollout/admin_first/admin_shell_entry_requirements.md`
6. `docs/plans/post_mvp_rollout/admin_first/admin_runtime_envelope.md`
7. `<slice_file>`
8. `docs/plans/post_mvp_rollout/runtime_entrypoints.md`
9. `docs/testing/slice_gate_template.md`

Touch only the owning layers named in the slice file.
Do not touch unrelated worktree changes.
Do not add tool execution or provider semantics unless the slice file explicitly calls for them.
Return exact files changed, tests run, the runtime entrypoint touched, and whether the slice gate is now satisfied.
```

## Template 7: Implement An Approved Admin Tool Slice

```text
Work only inside `MyCiteV2/`.

Implement only the approved admin-first tool slice documented in `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/admin_first/README.md`
3. `docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
4. `docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`
5. `docs/plans/post_mvp_rollout/admin_first/tool_registry_and_launcher_surface.md`
6. `<tool_track_doc>`
7. `<slice_file>`
8. `docs/plans/post_mvp_rollout/runtime_entrypoints.md`
9. `docs/testing/slice_gate_template.md`

Implement only the bounded tool-bearing slice named in the slice file.
Use:
- `aws_first_surface.md` for AWS work
- `cts_gis_follow_on_surface.md` for CTS-GIS work
- `agro_erp_follow_on_surface.md` for AGRO-ERP work
Do not add direct tool routes, a second shell entry, or flavor-specific runtime code.
Return exact files changed, tests run, the runtime entrypoint touched, and remaining blockers.
```

## Template 8: Implement A Post-AWS Tool Slice

```text
Work only inside `MyCiteV2/`.

Implement only the approved post-AWS tool slice documented in `<slice_file>`.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md`
3. `docs/plans/post_mvp_rollout/post_aws_tool_platform/future_tool_drop_in_contract.md`
4. `docs/plans/post_mvp_rollout/post_aws_tool_platform/tool_descriptor_contract.md`
5. `docs/plans/post_mvp_rollout/post_aws_tool_platform/runtime_entrypoint_catalog.md`
6. `docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md`
7. `<tool_track_doc>`
8. `<slice_file>`
9. `docs/testing/slice_gate_template.md`

Implement one slice only.
Add one semantic owner, one port seam, one adapter family if needed, one runtime entrypoint, one shell-owned descriptor, and one test/gate set.
Do not add dynamic discovery, a second shell, flavor-specific runtime code, broad provider-admin parity, or unrelated tool semantics.
Return exact files changed, tests run, descriptor added, runtime entrypoint added, and remaining blockers.
```

## Template 9: Review Historical Bridge Evidence

```text
Do not implement or reopen the V1-host bridge.

Use this prompt only when you need historical cutover context for records,
audits, or retirement review.

Read first:
1. `docs/plans/v2-authority_stack.md`
2. `docs/plans/post_mvp_rollout/current_planning_index.md`
3. `docs/records/22-v1_retirement_closure.md`
4. `docs/plans/post_mvp_rollout/post_aws_tool_platform/deployment_bridge_contract.md`
5. `docs/plans/post_mvp_rollout/post_aws_tool_platform/cutover_execution_sequence.md`
6. `docs/plans/post_mvp_rollout/slice_registry/admin_band0_v2_deployment_bridge.md`
7. `docs/records/15-cut_over.md`
8. `docs/records/16-v2_native_portal_cutover.md`

Summarize only:
- what the bridge did during cutover
- which artifacts remain as `historical_only` or `quarantine`
- why the live canonical boundary is now the V2-native host instead
- what current planning surface should be used instead of bridge-era docs

Do not propose bridge-first implementation work, alternate cutover shapes, or new bridge routes.
Return exact historical sources consulted and any mismatch you find against the closure record.
```
