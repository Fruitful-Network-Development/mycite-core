# Prove Slice & Tests

## PROMPT:

Work only inside `MyCiteV2/`.

Execute only the minimum remaining work required to satisfy the defined MVP acceptance criteria.

This is an implementation task, but only for:
- one shell-facing runtime composition path
- one integration path
- the minimum final tests required to claim the MVP

Do not widen scope.
Do not start post-MVP work.
Do not implement tools, sandboxes, extra adapters, extra runtime paths, or flavor expansion.
Do not touch unrelated worktree changes outside the approved MVP runtime-composition and integration surface.

==================================================
READ FIRST
==================================================

Read and follow, in order:
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/ontology/structural_invariants.md`
3. `MyCiteV2/docs/ontology/dependency_direction.md`
4. `MyCiteV2/docs/ontology/interface_surfaces.md`
5. `MyCiteV2/docs/contracts/import_rules.md`
6. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
7. `MyCiteV2/docs/plans/mvp_boundary.md`
8. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
9. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
10. `MyCiteV2/docs/plans/mvp_out_of_scope.md`
11. `MyCiteV2/docs/plans/phases/09_runtime_composition.md`
12. `MyCiteV2/docs/plans/phases/10_integration_testing.md`
13. the already-completed MVP implementations in:
   - `MyCiteV2/packages/core/datum_refs/`
   - `MyCiteV2/packages/state_machine/aitas/`
   - `MyCiteV2/packages/state_machine/nimm/`
   - `MyCiteV2/packages/state_machine/hanus_shell/`
   - `MyCiteV2/packages/ports/audit_log/`
   - `MyCiteV2/packages/modules/cross_domain/local_audit/`
   - `MyCiteV2/packages/adapters/filesystem/`

Use v1 only as lower-precedence evidence if absolutely needed.
Do not copy v1 runtime structure.
Do not create compatibility wrappers.

==================================================
MVP RUNTIME SCOPE
==================================================

Implement only one runtime composition path under:

- `MyCiteV2/instances/_shared/runtime/`

That path must do exactly the MVP slice and nothing broader:

1. accept one serialized shell action payload
2. construct the phase-03 shell action contract
3. reduce it through the pure state-machine logic
4. construct one local-audit record from the accepted shell-side result
5. instantiate `LocalAuditService`
6. instantiate `FilesystemAuditLogAdapter` with one caller-supplied storage file
7. append the audit record
8. perform the minimum required read-back behavior needed by the MVP
9. return one normalized runtime result containing:
   - normalized subject
   - normalized shell verb
   - normalized shell state
   - persisted audit identifier
   - persisted audit timestamp

Do not add any second runtime path.
Do not add HTTP routes unless the runtime composition phase doc and MVP boundary absolutely require a minimal callable surface and you keep it host-composition-only.
Prefer a narrow callable/runtime function surface over any broader host framework surface.

==================================================
OWNERSHIP RULES
==================================================

The runtime layer must compose inward layers only.

It must not:
- redefine shell semantics
- redefine local-audit semantics
- redefine port contracts
- absorb adapter behavior
- become a general host framework
- introduce instance-led architecture

The runtime path should be a thin composition seam only.

It is allowed to:
- instantiate the adapter
- instantiate the local-audit service
- call the state-machine reducer/contracts
- compose the final normalized response payload

It is not allowed to:
- invent new business rules
- broaden payload shapes beyond MVP need
- add tool attachment
- add sandbox orchestration
- add flavor-specific branches beyond the one proving path

==================================================
READ-BACK RULE
==================================================

The current MVP docs say the slice persists and reads back the audit metadata needed for the response.

Choose the narrowest compliant implementation:
- if append receipt alone satisfies the accepted MVP docs, document that clearly and avoid unnecessary read-back
- if the current MVP docs require an actual read-by-id path in the proving slice, implement the minimum read-back needed and nothing more

If implementation exposes a mismatch between the current MVP docs and the narrowest viable runtime behavior, update the MVP docs minimally and consistently.

==================================================
EXPECTED OUTPUT SURFACE
==================================================

Implement only the minimum runtime-facing surface needed to prove the MVP, likely including:

1. one composition entrypoint under `instances/_shared/runtime/`
   - pure-ish orchestration only
   - accepts serialized input payload and a storage-file path or equivalent minimal outward configuration
   - returns normalized runtime result payload

2. one integration test suite
   - executes the full slice end to end
   - proves composition across:
     - core
     - state_machine
     - port
     - local_audit
     - filesystem adapter
     - runtime composition

3. any final architecture-boundary tests needed for the runtime layer
   - enough to prove host composition did not become semantic ownership

Do not add more than one entrypoint unless absolutely required by the existing runtime package shape.

==================================================
TEST REQUIREMENTS
==================================================

Run and report the minimum set of tests required to claim MVP.

At minimum include:

1. existing passing lower-layer tests still relevant to MVP:
   - pure unit loop
   - state-machine loop
   - port/contract loop
   - adapter loop
   - architecture-boundary loops for included layers

2. one new integration loop for the full proving slice

3. runtime-layer architecture checks ensuring:
   - runtime composes rather than owns semantics
   - no tool or sandbox logic appears
   - no second runtime path appears
   - no flavor expansion appears

If there is a lightweight way to aggregate the MVP-required test commands, do so.
Do not invent a broad new test harness unless required.

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- implement tools
- implement sandboxes
- add domain modules
- add extra cross-domain modules
- add extra adapters
- add another runtime flavor
- broaden the runtime path into a framework
- compensate for missing lower-layer behavior in the runtime
- weaken boundary checks just to make composition pass
- hide semantic ownership inside the host/runtime layer

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if implementation reveals a mismatch in:
- `mvp_boundary.md`
- `mvp_acceptance_criteria.md`
- `mvp_end_to_end_slice.md`
- `09_runtime_composition.md`
- `10_integration_testing.md`
- package-level README docs for the runtime composition area

Do not broaden the MVP boundary in docs.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:
- one runtime composition path exists and works
- the full MVP slice executes end to end
- the runtime returns the normalized MVP result
- all minimum required tests pass
- the runtime layer remains composition-only
- no forbidden scope expansion occurred

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the implemented proving path
3. the exact runtime entrypoint/composition surface added
4. the tests run and their results
5. whether MVP acceptance criteria are now fully satisfied
6. any architecture-boundary protections added or extended
7. any scope reductions or exclusions enforced to stay inside MVP
8. any remaining blocker to claiming MVP
9. any doc updates made because plan and implementation needed to be aligned


---


## OUTPUT:

1. Exact files created or updated:

- [README.md](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/README.md)
- [mvp_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/mvp_runtime.py)
- [test_mvp_runtime_composition.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_mvp_runtime_composition.py)
- [test_runtime_composition_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py)

2. Implemented proving path:

The runtime now executes the full `Shell Action To Local Audit` slice, in order:

1. accept one serialized shell action payload
2. build `ShellAction`
3. reduce it through `reduce_shell_action(ShellState(), action)`
4. build one normalized local-audit record
5. instantiate `LocalAuditService`
6. instantiate `FilesystemAuditLogAdapter` with one caller-supplied storage file
7. append the audit record
8. read it back by `record_id`
9. return the normalized runtime result

3. Exact runtime entrypoint/composition surface added:

In [mvp_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/mvp_runtime.py):

- `run_shell_action_to_local_audit(shell_action_payload, *, storage_file) -> dict`

It returns exactly these MVP fields:

- `normalized_subject`
- `normalized_shell_verb`
- `normalized_shell_state`
- `persisted_audit_identifier`
- `persisted_audit_timestamp`

This entrypoint is composition-only. It does not redefine shell semantics, local-audit semantics, port contracts, or adapter behavior.

4. Tests run and results:

I ran the full MVP-required test stack with:

```bash
python3 -m unittest \
  MyCiteV2.tests.unit.test_datum_refs \
  MyCiteV2.tests.unit.test_state_machine_hanus_shell \
  MyCiteV2.tests.contracts.test_audit_log_contracts \
  MyCiteV2.tests.unit.test_local_audit \
  MyCiteV2.tests.adapters.test_filesystem_audit_log_adapter \
  MyCiteV2.tests.architecture.test_core_datum_refs_boundaries \
  MyCiteV2.tests.architecture.test_state_machine_boundaries \
  MyCiteV2.tests.architecture.test_ports_audit_log_boundaries \
  MyCiteV2.tests.architecture.test_local_audit_boundaries \
  MyCiteV2.tests.architecture.test_filesystem_adapter_boundaries \
  MyCiteV2.tests.architecture.test_runtime_composition_boundaries \
  MyCiteV2.tests.integration.test_mvp_runtime_composition
```

Result: `Ran 39 tests in 0.033s` and `OK`.

5. Whether MVP acceptance criteria are now fully satisfied:

Yes. Within the defined MVP boundary, the acceptance criteria are now satisfied:

- runtime receives serialized shell action
- subject is normalized
- shell action is reduced
- local-audit record is produced
- record is persisted and read back through `audit_log` + filesystem adapter
- runtime returns the normalized MVP result
- lower-layer and runtime boundary tests all pass

6. Architecture-boundary protections added or extended:

Added [test_runtime_composition_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py), which checks:

- runtime imports only inward layers and standard library
- no tool imports
- no sandbox imports
- no direct `mycite_core` imports
- exactly one runtime Python entrypoint exists under `instances/_shared/runtime/`
- no Python runtime files exist under `instances/_shared/runtime/flavors/`
- no route/framework/tool/sandbox logic appears in the runtime source

7. Scope reductions or exclusions enforced to stay inside MVP:

- one runtime entrypoint only
- no HTTP surface
- no host framework
- no flavor expansion
- no tools
- no sandboxes
- no extra runtime paths
- no extra adapters
- no post-MVP composition behavior

I kept real read-back because the current MVP docs require it.

8. Any remaining blocker to claiming MVP:

None within the approved MVP scope.

9. Any doc updates made because plan and implementation needed to be aligned:

Only [README.md](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/README.md) was updated to describe the single MVP runtime composition path. No MVP boundary or acceptance docs needed changes because the implementation matched the existing plan.


---


## CONSIDERATION & ASSSMENT

HERE


---
