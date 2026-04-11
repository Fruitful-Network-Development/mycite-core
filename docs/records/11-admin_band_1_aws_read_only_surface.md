# Admin Band 1 AWS Read Only Surface

## PROMPT 

Work only inside `MyCiteV2/`.

Implement `admin_band1.aws_read_only_surface` only.

This is the first real tool-bearing slice after the completed `Admin Band 0 Internal Admin Replacement`.

Your goal is to add the first AWS read-only operational visibility slice through the existing admin shell and registry, without disturbing the structural integrity already established.

Do not implement AWS write behavior.
Do not implement Maps.
Do not implement AGRO-ERP.
Do not add extra tools.
Do not broaden client rollout.
Do not rework Admin Band 0 beyond the smallest approved extension needed for this slice.

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
16. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band1_aws_read_only_surface.md`
17. `MyCiteV2/docs/testing/slice_gate_template.md`
18. `MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md`

Also read the already-implemented supporting surfaces:
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
- `MyCiteV2/instances/_shared/runtime/README.md`
- current tests covering Admin Band 0 and MVP runtime composition

Use v1 only as lower-precedence evidence if absolutely needed.
Do not copy v1 AWS or provider-admin structure directly.

==================================================
IMPLEMENT ONLY THIS SLICE
==================================================

Implement only `admin_band1.aws_read_only_surface`.

This means:

1. add one AWS read-only seam
2. add one AWS read-only adapter family
3. add one runtime entrypoint: `admin.aws.read_only`
4. plug that entrypoint into the existing shell-owned admin registry
5. move the AWS registry item from gated/planned to approved only if this slice passes its gate

Do not implement `admin_band2.aws_narrow_write_surface`.
Do not add write behavior of any kind.

==================================================
TARGET OUTCOME
==================================================

At the end of this task, V2 should have one trusted-tenant-safe AWS read-only operational visibility surface, launched through the existing admin shell and registry, that shows only the approved AWS operational summary and exposes no writes and no secret-bearing values.

==================================================
AWS READ-ONLY SCOPE
==================================================

Implement only the first approved AWS visibility surface.

The slice should remain limited to operational visibility such as:
- mailbox/profile readiness
- SMTP-ready vs Gmail-pending vs verified evidence state
- selected verified sender
- canonical newsletter operational profile summary
- safe compatibility warnings

Do not widen scope beyond what the slice docs allow.

Out of scope:
- provisioning writes
- manual newsletter send
- credential display
- secret-bearing values
- PayPal
- analytics
- Maps
- AGRO-ERP
- raw provider dashboards
- mixed AWS/PayPal/newsletter surfaces
- standalone `newsletter-admin`

==================================================
OWNERSHIP RULES
==================================================

Preserve the existing ownership boundaries:

- shell legality remains owned by `packages/state_machine/`
- the admin shell/registry remains shell-owned
- the AWS slice must be launched through the registry, not bypass it
- runtime entrypoints compose only
- tool semantics must not redefine shell entry behavior
- adapters must not own AWS semantic policy
- no direct provider-admin route becomes the v2 surface

Keep the current admin shell entry, home/status, and tool registry behavior unchanged unless a very small approved extension is required.

==================================================
IMPLEMENTATION SHAPE
==================================================

Implement only the minimum shapes required for this read-only slice, likely including:

1. one AWS read-only semantic surface
   - narrow, read-only, explicit
   - only approved status/summary fields
   - no write verbs
   - no credential-bearing payloads

2. one AWS read-only seam
   - explicit contract
   - narrow payloads
   - no speculative broad provider interface

3. one AWS read-only adapter family
   - satisfies the new seam
   - keeps outward/provider details outward
   - no write methods

4. one runtime composition entrypoint
   - `admin.aws.read_only`
   - launchable through the admin shell registry
   - returns one normalized AWS read-only surface payload

5. minimal shell/registry update
   - only enough to allow the now-approved AWS read-only slice to appear as available
   - do not broaden registry behavior
   - do not add dynamic package scanning

==================================================
TESTS REQUIRED
==================================================

Add only the tests required to prove this slice.

At minimum include:

1. AWS read-only semantic tests
2. seam/contract tests for the AWS read-only contract
3. adapter tests for the AWS read-only adapter
4. integration tests for shell-registry-to-`admin.aws.read_only` launch
5. architecture-boundary tests proving:
   - shell still owns discoverability and launch legality
   - no write behavior exists in the AWS read-only slice
   - no secret-bearing values are exposed
   - no direct provider-admin fallback exists
   - no Maps or AGRO-ERP behavior appears
   - no `mycite_core` imports appear

Also rerun the minimum regression stack needed to show:
- Admin Band 0 still passes
- MVP runtime still passes
- the new AWS read-only slice passes

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- implement AWS write behavior
- add a second tool-bearing slice
- widen the shell registry into a tool framework
- add dynamic discovery by scanning packages
- expose provider-specific raw objects directly
- leak secrets or provider-internal fields
- bypass the shell-owned registry
- create broad “provider admin” parity
- use compatibility fields to override the canonical newsletter operational profile
- weaken Band 0 behavior just to make AWS easier

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if implementation requires a small alignment in:
- `runtime_entrypoints.md`
- `client_exposure_gates.md`
- `admin_band1_aws_read_only_surface.md`
- `aws_first_surface.md`
- package/runtime README files
- one ADR if a new explicit decision is required

Do not broaden the rollout order.
Do not start AWS narrow write planning-by-implementation.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:

- one approved AWS read-only seam exists
- one approved AWS read-only adapter exists
- one `admin.aws.read_only` runtime entrypoint exists
- the slice launches only through the existing admin shell registry
- the payload is read-only, narrow, and secret-safe
- tests pass
- Admin Band 0 behavior still passes
- the system is clearly ready for the next prompt to implement `admin_band2.aws_narrow_write_surface`

==================================================
END-OF-TASK RESPONSE
==================================================

Return:

1. the exact files created or updated
2. the seam and adapter names implemented
3. the exact runtime entrypoint added
4. the AWS read-only payload implemented
5. the minimal shell/registry changes made
6. the tests run and their results
7. whether `admin_band1.aws_read_only_surface` is now satisfied
8. what remains for the next prompt to implement `admin_band2.aws_narrow_write_surface`
9. any blocked ambiguities that should remain deferred

---


## OUTPUT 

**Files**
Created:
- [contracts.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/aws_read_only_status/contracts.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/aws_read_only_status/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/ports/aws_read_only_status/README.md)
- [service.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_operational_visibility/service.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_operational_visibility/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_operational_visibility/README.md)
- [aws_read_only_status.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/aws_read_only_status.py)
- [admin_aws_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py)
- [test_aws_operational_visibility.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_aws_operational_visibility.py)
- [test_aws_read_only_status_contracts.py](/srv/repo/mycite-core/MyCiteV2/tests/contracts/test_aws_read_only_status_contracts.py)
- [test_filesystem_aws_read_only_status_adapter.py](/srv/repo/mycite-core/MyCiteV2/tests/adapters/test_filesystem_aws_read_only_status_adapter.py)
- [test_admin_aws_read_only_runtime.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_aws_read_only_runtime.py)
- [test_aws_operational_visibility_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_aws_operational_visibility_boundaries.py)
- [test_aws_read_only_status_port_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_aws_read_only_status_port_boundaries.py)
- [test_filesystem_aws_read_only_status_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_aws_read_only_status_boundaries.py)

Updated:
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/README.md)
- [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/README.md)
- [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/README.md)
- [test_state_machine_admin_shell.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_state_machine_admin_shell.py)
- [test_admin_runtime_composition.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_runtime_composition.py)
- [test_filesystem_adapter_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py)
- [test_runtime_composition_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py)
- [runtime_entrypoints.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md)
- [port_adapter_ownership_matrix.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md)
- [aws_first_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md)
- [frozen_decisions_admin_band.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md)
- [admin_band0_shell_entry.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_shell_entry.md)
- [admin_band0_home_status.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_home_status.md)
- [admin_band0_tool_registry.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_tool_registry.md)
- [admin_band1_aws_read_only_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band1_aws_read_only_surface.md)

Unrelated preexisting archive changes in [11-admin_band_1_aws_read_only_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/archive/11-admin_band_1_aws_read_only_surface.md) and [12-admin_band_2_aws_narrow_write_surface.md](/srv/repo/mycite-core/MyCiteV2/docs/archive/12-admin_band_2_aws_narrow_write_surface.md) were left alone.

**Implementation**
The seam is `packages/ports/aws_read_only_status/` with `AwsReadOnlyStatusPort`, `AwsReadOnlyStatusRequest`, `AwsReadOnlyStatusSource`, and `AwsReadOnlyStatusResult`. The adapter is [FilesystemAwsReadOnlyStatusAdapter](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/aws_read_only_status.py), backed by one caller-supplied JSON snapshot file and exposing no write methods.

The semantic owner is [AwsOperationalVisibilityService](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_operational_visibility/service.py). It normalizes one tenant-scoped AWS operational snapshot, rejects secret-bearing keys, derives compatibility warnings, and emits a read-only summary only.

The runtime entrypoint added is [run_admin_aws_read_only](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py), cataloged as `admin.aws.read_only`.

The AWS read-only payload includes:
- `mailbox_readiness`
- `smtp_state`
- `gmail_state`
- `verified_evidence_state`
- `selected_verified_sender`
- `canonical_newsletter_operational_profile`
- `compatibility_warnings`
- `inbound_capture`
- `dispatch_health`
- `write_capability: not_available`

**Shell / Registry**
The minimal shell change is in [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py):
- AWS is now a launchable shell-owned registry entry.
- Launch legality is still shell-owned via `resolve_admin_tool_launch(...)`.
- `admin.shell_entry` still stays the landing surface; if AWS is requested inline there, it returns `launch_via_registry` and redirects to the registry path instead of executing tool semantics inside the shell entry.
- The registry remains catalog-driven. No dynamic package scan was added.

**Tests**
Added the new slice loops:
- unit: [test_aws_operational_visibility.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_aws_operational_visibility.py)
- contract: [test_aws_read_only_status_contracts.py](/srv/repo/mycite-core/MyCiteV2/tests/contracts/test_aws_read_only_status_contracts.py)
- adapter: [test_filesystem_aws_read_only_status_adapter.py](/srv/repo/mycite-core/MyCiteV2/tests/adapters/test_filesystem_aws_read_only_status_adapter.py)
- integration: [test_admin_aws_read_only_runtime.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_aws_read_only_runtime.py)
- architecture: the three new AWS boundary tests above, plus updates to [test_runtime_composition_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py) and [test_filesystem_adapter_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py)

Ran and passed:
- targeted AWS slice stack: `32` tests, `OK`
- full regression stack across MVP, Admin Band 0, and AWS read-only: `68` tests, `OK`

**Status**
`admin_band1.aws_read_only_surface` is now satisfied within the approved scope. The slice has:
- one approved AWS read-only seam
- one approved AWS read-only adapter
- one `admin.aws.read_only` runtime entrypoint
- shell-owned registry launchability
- a narrow, read-only, secret-safe payload
- passing regression coverage without breaking Admin Band 0 or the MVP

What remains for the next prompt to implement `admin_band2.aws_narrow_write_surface`:
- define the exact AWS narrow-write seam and adapter names
- implement the bounded write field set only
- prove read-after-write behavior
- emit local-audit records for accepted writes
- document rollback/manual recovery before exposure
- keep the current AWS read-only slice and shell/registry behavior intact

Blocked ambiguities that should stay deferred:
- the exact AWS narrow-write seam and adapter names
- the bounded field set for the first AWS narrow write
- whether broader dispatch-health visibility belongs in a later AWS follow-up slice
- whether the admin home/status surface and tool registry later merge into one shell payload
- whether trusted-tenant users later receive the admin shell landing surface itself, rather than only the registry-resolved `admin.aws.read_only` path

---