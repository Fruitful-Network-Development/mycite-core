# Agent Prompt Templates

Authority: [../authority_stack.md](../authority_stack.md)

These templates exist so future prompts can stay small and still align with the post-MVP operating system.

## Template 1: Specify A Slice

```text
Work only inside `MyCiteV2/`.

Your task is to define or refine the slice file at `<slice_file>`.

Read first:
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/plans/post_mvp_rollout/README.md`
3. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
4. `MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
5. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/slice_template.md`
6. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
7. `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`

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
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
3. `MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
4. `<slice_file>`
5. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
6. `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
7. `MyCiteV2/docs/testing/slice_gate_template.md`

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
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
3. `MyCiteV2/docs/plans/post_mvp_rollout/frozen_decisions_current_band.md`
4. `<slice_file>`
5. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
6. `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
7. `MyCiteV2/docs/testing/slice_gate_template.md`

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
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
3. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
4. `MyCiteV2/docs/testing/slice_gate_template.md`
5. `<slice_file>`

Do not implement new features unless a tiny doc alignment fix is required.
Record pass or fail for each gate, list the blocking items, and state whether the slice is:
- still `candidate`
- `approved_for_build`
- `implemented_internal`
- `approved_for_exposure`
```
