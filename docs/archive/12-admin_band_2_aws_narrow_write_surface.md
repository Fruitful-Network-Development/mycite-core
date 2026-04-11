# Admin BAND 2 AWS Narrow Write Surface

## PROMPT 

Work only inside `MyCiteV2/`.

Implement `admin_band2.aws_narrow_write_surface` only.

This is the next step after the completed AWS read-only slice.
Your goal is to add one bounded AWS operational write path without widening back into a broad provider-admin control plane.

Do not implement Maps.
Do not implement AGRO-ERP.
Do not broaden AWS into a general control plane.
Do not disturb Admin Band 0 or AWS read-only behavior except for the smallest approved extension needed for this slice.

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
8. `MyCiteV2/docs/plans/post_mvp_rollout/README.md`
9. `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
10. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
11. `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`
12. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/README.md`
13. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
14. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md`
15. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`
16. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band2_aws_narrow_write_surface.md`
17. `MyCiteV2/docs/testing/slice_gate_template.md`

Also read the currently implemented supporting surfaces:
- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
- `MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py`
- `MyCiteV2/packages/ports/aws_read_only_status/`
- `MyCiteV2/packages/modules/cross_domain/aws_operational_visibility/`
- `MyCiteV2/packages/adapters/filesystem/aws_read_only_status.py`
- `MyCiteV2/packages/modules/cross_domain/local_audit/`
- `MyCiteV2/packages/ports/audit_log/`
- `MyCiteV2/packages/adapters/filesystem/audit_log.py`

Use v1 only as lower-precedence evidence if absolutely needed.
Do not copy v1 provider-admin structure directly.

==================================================
IMPLEMENT ONLY THIS SLICE
==================================================

Implement only `admin_band2.aws_narrow_write_surface`.

This means:

1. define one narrow AWS write seam
2. define one narrow AWS write adapter family
3. add one runtime entrypoint: `admin.aws.narrow_write`
4. keep launchability shell-owned through the existing registry
5. emit local-audit records for accepted writes through the existing audit path
6. prove read-after-write behavior
7. document rollback/manual recovery before exposure

Do not implement any second write slice.
Do not add broad provisioning.
Do not add manual newsletter send.
Do not add raw secret editing.

==================================================
PRIMARY DECISION RULE
==================================================

You must choose the smallest bounded field set that makes this slice useful and safe.

Default to the narrowest credible choice.
Do not implement multiple write families.

If the docs leave the field set open, select one recommended bounded field set, document it minimally where needed, and implement only that set.

Strong preference:
- selected verified sender
- canonical newsletter operational profile stewardship

Do not add additional writable AWS fields unless they are strictly required to make the slice coherent.

==================================================
TARGET OUTCOME
==================================================

At the end of this task, V2 should have one bounded AWS write slice that:

- launches only through the existing admin shell registry
- accepts only the approved narrow field set
- validates the write request explicitly
- uses one AWS narrow-write seam and one adapter
- performs the write
- reads back the resulting state for confirmation
- emits an accepted local-audit record
- returns a normalized read-after-write result
- includes rollback/manual recovery documentation
- keeps the existing AWS read-only slice intact

==================================================
OWNERSHIP RULES
==================================================

Preserve these ownership boundaries:

- shell legality and launch legality remain shell-owned
- runtime composes only
- AWS operational write semantics belong to the AWS narrow-write semantic surface, not the runtime
- adapters own outward provider/file details, not semantics
- local audit owns audit normalization and emission semantics
- the audit port and adapter remain the audit persistence path

Do not let:
- runtime define AWS operational semantics
- adapters define allowed field sets
- shell own AWS write semantics
- write behavior leak into the read-only seam

==================================================
EXPECTED IMPLEMENTATION SHAPE
==================================================

Implement only the minimum shapes required for this slice, likely including:

1. one AWS narrow-write contract/seam
   - explicit request shape
   - explicit response/confirmation shape
   - no speculative broad provider interface

2. one AWS narrow-write semantic owner
   - validates only the approved bounded field set
   - rejects unapproved writes
   - coordinates read-after-write confirmation
   - prepares local-audit emission payloads

3. one AWS narrow-write adapter family
   - satisfies the new seam
   - keeps outward/provider details outward
   - no secret display
   - no broad provisioning behavior

4. one runtime composition entrypoint
   - `admin.aws.narrow_write`
   - only launchable through the existing shell registry
   - returns normalized read-after-write result
   - triggers local-audit append for accepted writes

5. one minimal registry update
   - enough to surface the new narrow-write slice according to the current rollout/gating rules
   - no broad registry redesign

6. one minimal rollback/manual recovery doc update
   - only what the slice gate requires before trusted-tenant exposure

==================================================
OUT OF SCOPE
==================================================

Do not implement:
- manual newsletter dispatch
- broad mailbox provisioning
- raw credential editing or display
- Gmail verification toggles without confirmation evidence
- PayPal
- analytics
- Maps
- AGRO-ERP
- second write slices
- broad provider-admin dashboards
- any dynamic tool discovery

==================================================
TESTS REQUIRED
==================================================

Add only the tests required to prove this slice.

At minimum include:

1. AWS narrow-write semantic tests
   - allowed field validation
   - rejected field validation
   - bounded write request normalization

2. contract tests for the AWS narrow-write seam

3. adapter tests for the AWS narrow-write adapter

4. local-audit tests for accepted write-path audit emission
   - use the existing audit path rather than inventing a new one

5. integration tests for shell-registry-to-`admin.aws.narrow_write`
   - includes read-after-write confirmation

6. architecture-boundary tests proving:
   - shell still owns launch legality
   - runtime remains composition-only
   - adapters do not define semantics
   - no broad provider-admin control plane appears
   - no `mycite_core` imports appear
   - AWS read-only behavior remains intact

Also rerun the minimum regression stack needed to show:
- MVP still passes
- Admin Band 0 still passes
- AWS read-only still passes
- AWS narrow-write now passes

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- weaken the bounded field set by convenience
- let the write slice become the new admin shell center
- bypass the registry
- merge read-only and write semantics into one broad service bucket
- move audit semantics into runtime or adapter code
- skip read-after-write confirmation
- skip rollback/manual recovery documentation
- widen scope to “finish AWS” broadly

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if required by implementation alignment in:
- `runtime_entrypoints.md`
- `client_exposure_gates.md`
- `port_adapter_ownership_matrix.md`
- `admin_band2_aws_narrow_write_surface.md`
- `aws_first_surface.md`
- relevant package/runtime README files
- one ADR if a new explicit decision is required
- one rollback/manual recovery doc if the slice requires it

Do not broaden the rollout order.
Do not start Maps planning-by-implementation.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:

- one approved AWS narrow-write seam exists
- one approved AWS narrow-write adapter exists
- one `admin.aws.narrow_write` runtime entrypoint exists
- the slice launches only through the existing admin shell registry
- the writable field set is explicitly bounded
- read-after-write confirmation works
- accepted writes emit local-audit records
- rollback/manual recovery guidance exists
- tests pass
- MVP, Admin Band 0, and AWS read-only remain green
- the system is clearly ready for the next prompt to begin Maps follow-on work

==================================================
END-OF-TASK RESPONSE
==================================================

Return:

1. the exact files created or updated
2. the seam and adapter names implemented
3. the exact bounded field set chosen
4. the exact runtime entrypoint added
5. the read-after-write behavior implemented
6. the local-audit behavior added for accepted writes
7. the minimal shell/registry changes made
8. the tests run and their results
9. whether `admin_band2.aws_narrow_write_surface` is now satisfied
10. what remains for the next prompt to begin Maps follow-on work
11. any blocked ambiguities that should remain deferred

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

---


## CONSIDERATIONS & ANALYSIS


After `Admin Band 1 AWS Read Only Surface` and `Admin Band 2 AWS Narrow Write Surface`, stable tool development should become materially easier.

The main reason is that by that point the hard repeated problems will already be solved once, in the repo, instead of being rediscovered per tool: one shell-owned entry and registry, one tenant-safe runtime envelope, one approved tool-bearing runtime path, one read-only tool pattern, one bounded write pattern, and one audit/read-after-write pattern. Your current admin-first plan already fixes that ordering: Admin Band 0 first, then AWS read-only, then AWS narrow write, then Maps, then AGRO-ERP  

That means later tools do not need to invent:

* how they become discoverable
* how launch legality is decided
* how runtime entrypoints are shaped
* how read-only exposure is gated
* how bounded writes are audited
* how rollout bands work

Those are exactly the things that usually slow down and destabilize tool work. Your current Band 0 implementation already gives you the shell entry, home/status, and deny-by-default registry, with AWS only appearing as the gated next slice, not as a bypass around the shell  The Band 1 AWS slice is also already defined as a shell-launched, read-only operational visibility slice with its own runtime entrypoint and explicit tests, not a mixed provider dashboard  Then Band 2 AWS narrow write adds the bounded write model, read-after-write confirmation, and audit emission through the existing audit path, while still forbidding a return to a broad provider-admin control plane 

So for future tools, the pace should improve because the work becomes more like:
“define the tool’s seam, adapter, runtime entrypoint, and slice gate inside an already-proven operating model”
instead of:
“also invent the portal shell, registry, and rollout policy while building the tool.”

For tools closer to AWS in shape, this will help a lot. Anything that looks like an operational control surface with read-only first, then narrow write, should benefit directly from the established pattern.

For Maps and AGRO-ERP, it will still be easier, but not equally easy. They will benefit from the established shell, registry, runtime, gating, and slice discipline, so they will not need to solve portal-operating questions from scratch. But they will still require more intentional design because they are not just “another provider-admin slice.” They likely need more original semantics, possibly different ports/adapters, and maybe richer mediation behavior than AWS needs. Your own rollout plan already reflects that by forcing Maps to follow AWS and AGRO-ERP to follow Maps, rather than pretending they are the same kind of tool  

So the practical answer is:

AWS Band 1 and Band 2 do not make every later tool cheap, but they do make later tool development much more structured, repeatable, and safer. They establish the reusable operational pattern. After that, the remaining difficulty shifts away from shell/runtime uncertainty and toward the actual semantics of each tool. That is exactly where you want the difficulty to be.


---