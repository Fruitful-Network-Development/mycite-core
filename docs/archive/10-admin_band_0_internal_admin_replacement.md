# Admin Band 0 Internal Admin Replacement

## PROMPT

Work only inside `MyCiteV2/`.

Implement `Admin Band 0 Internal Admin Replacement` only.

This is the next foundational implementation chunk after the completed architecture MVP and the completed admin-first staging pass.

Your goal is to restore a stable internal admin portal operating band so that later tool work can proceed normally through the shell, with AWS as the first real tool-bearing target afterward.

Do not implement AWS yet.
Do not implement Maps.
Do not implement AGRO-ERP.
Do not implement tools themselves.
Do not add broad client rollout behavior.

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
9. `MyCiteV2/docs/plans/post_mvp_rollout/README.md`
10. `MyCiteV2/docs/plans/post_mvp_rollout/portal_rollout_bands.md`
11. `MyCiteV2/docs/plans/post_mvp_rollout/client_exposure_gates.md`
12. `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md`
13. `MyCiteV2/docs/plans/post_mvp_rollout/port_adapter_ownership_matrix.md`
14. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/README.md`
15. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_first_rollout_band.md`
16. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_shell_entry_requirements.md`
17. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_runtime_envelope.md`
18. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/admin_home_and_status_surface.md`
19. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/tool_registry_and_launcher_surface.md`
20. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/aws_first_surface.md`
21. `MyCiteV2/docs/plans/post_mvp_rollout/admin_first/frozen_decisions_admin_band.md`
22. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_shell_entry.md`
23. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_home_status.md`
24. `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_tool_registry.md`
25. `MyCiteV2/docs/testing/slice_gate_template.md`
26. `MyCiteV2/docs/plans/post_mvp_rollout/agent_prompt_templates.md`

Also read the already-implemented V2 runtime and MVP surfaces:
- `MyCiteV2/instances/_shared/runtime/`
- `MyCiteV2/packages/state_machine/`
- `MyCiteV2/packages/modules/cross_domain/local_audit/`
- `MyCiteV2/packages/adapters/filesystem/`

Use v1 only as lower-precedence evidence if absolutely needed.
Do not copy v1 structure.

==================================================
IMPLEMENT ONLY THIS BAND
==================================================

Implement the full `Admin Band 0 Internal Admin Replacement` and nothing beyond it.

That means implementing, in one coherent chunk:

1. one stable admin shell entry
2. one tenant-safe admin runtime envelope
3. one admin home/status surface
4. one shell-owned tool registry / launcher surface

These must work together as one stable internal admin operating band.

Do not implement the AWS read-only slice yet.
Only make the shell, runtime envelope, home/status surface, and tool registry ready for AWS to plug into next.

==================================================
TARGET OUTCOME
==================================================

At the end of this task, V2 should have one stable internal admin entry surface that:

- is the only intended admin landing path
- is tenant-safe
- is composition-only at runtime
- exposes one admin home/status payload
- exposes a deny-by-default tool registry / launcher surface
- can list the future AWS slice as planned/unavailable or gated, without implementing AWS itself
- does not rely on legacy provider-admin routes
- is ready for the next prompt to implement the AWS read-only slice cleanly

==================================================
IN-SCOPE IMPLEMENTATION
==================================================

Implement only what is required for these three slice-registry items and their combined band behavior:

- `admin_band0.shell_entry`
- `admin_band0.home_status`
- `admin_band0.tool_registry`

This likely includes:

1. one admin runtime entrypoint under `instances/_shared/runtime/`
   - the single shell-owned admin landing entry
   - composition-only
   - no provider-specific semantics
   - no direct tool execution

2. any minimal state-machine additions strictly required for shell entry / slice selection state
   - only if the slice docs require it
   - keep shell legality owned by `packages/state_machine/`

3. one normalized admin home/status response shape
   - internal admin only
   - indicates:
     - tenant/context identity at the minimum safe level
     - current rollout band
     - available internal admin slices
     - gated/unavailable slices
     - readiness/status summary needed by the slice docs
   - keep it narrow and operational

4. one shell-owned tool registry / launcher payload
   - deny-by-default
   - catalog-driven, not dynamic package scanning
   - no tool-owned launch legality
   - may include AWS as a listed but gated next slice if that is what the docs require

==================================================
OUT OF SCOPE
==================================================

Do not implement:
- AWS tool logic
- AWS read-only data retrieval
- AWS narrow write behavior
- Maps
- AGRO-ERP
- PayPal
- Keycloak
- analytics
- sandbox flows
- second runtime entrypoints
- flavor expansion
- client-facing rollout
- direct provider-admin replacement routes
- any broad tool framework beyond what the tool registry slice explicitly needs

==================================================
BOUNDARY RULES
==================================================

- Hosts/runtime compose only. They do not own semantics.
- Shell legality remains owned by `packages/state_machine/`.
- Tool registry/launcher is shell-owned. Tools do not define their own launch legality.
- No tool may bypass the shell-owned registry/launcher.
- No direct provider-admin route may become the v2 entry surface.
- No legacy `newsletter-admin` style standalone comeback.
- Keep deny-by-default behavior for slices and tools not yet implemented.
- Keep internal-only posture for this band.

==================================================
TESTS REQUIRED
==================================================

Add only the tests required to prove `Admin Band 0`.

At minimum include:

1. integration tests for the admin shell entry
   - one stable landing path
   - expected payload shape
   - denied/gated slice behavior
   - no tool execution

2. integration tests for admin home/status behavior
   - correct rollout band/status data
   - internal-only posture
   - narrow, stable payload shape

3. integration tests for tool registry/launcher behavior
   - catalog-driven behavior
   - deny-by-default gating
   - no dynamic package scan assumptions
   - no launch of unavailable slices

4. architecture-boundary tests for the runtime/admin layer
   - runtime remains composition-only
   - no tool-owned shell legality
   - no second runtime entrypoint introduced by convenience
   - no provider-admin semantics leaking into the shell entry
   - no direct `mycite_core` imports

5. any state-machine tests only if shell-entry implementation requires minimal state additions

Run the minimum full stack needed to show this band is stable without regressing the completed MVP.

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if implementation reveals a mismatch in:
- `runtime_entrypoints.md`
- `client_exposure_gates.md`
- the three Admin Band 0 slice files
- package/runtime README files
- one ADR if a new explicit decision is required

Do not broaden the rollout plan.
Do not redefine the admin-first ordering.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:

- one stable internal admin shell entry exists
- one tenant-safe admin runtime envelope exists
- one admin home/status surface exists
- one shell-owned deny-by-default tool registry/launcher exists
- these are integrated together through one stable internal admin path
- no forbidden scope expansion occurred
- tests pass
- the system is clearly ready for the next prompt to implement the AWS read-only slice

==================================================
END-OF-TASK RESPONSE
==================================================

Return:

1. the exact files created or updated
2. the exact admin runtime entrypoint/composition surface added
3. the shell entry behavior implemented
4. the admin home/status payload implemented
5. the tool registry/launcher behavior implemented
6. the tests run and their results
7. whether `Admin Band 0 Internal Admin Replacement` is now satisfied
8. what remains for the next prompt to implement the AWS read-only slice
9. any blocked ambiguities that should remain deferred

---


## OUTPUT 

1. **Files created or updated**

Created:
- [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py)
- [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py)
- [test_state_machine_admin_shell.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_state_machine_admin_shell.py)
- [test_admin_runtime_composition.py](/srv/repo/mycite-core/MyCiteV2/tests/integration/test_admin_runtime_composition.py)

Updated:
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/README.md)
- [README.md](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/README.md)
- [test_runtime_composition_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py)
- [runtime_entrypoints.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md)
- [admin_band0_shell_entry.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_shell_entry.md)
- [admin_band0_home_status.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_home_status.md)
- [admin_band0_tool_registry.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_tool_registry.md)

I left unrelated archive files in `MyCiteV2/docs/archive/` alone.

2. **Exact admin runtime entrypoint/composition surface added**

Added [run_admin_shell_entry](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py) in [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py).

It is the single Admin Band 0 runtime path:
- entrypoint id: `admin.shell_entry`
- input: serialized admin shell request payload plus optional `audit_storage_file`
- output: one normalized admin runtime envelope with tenant scope, shell selection state, active surface payload, warnings, and explicit gated/denied errors

3. **Shell entry behavior implemented**

The shell-owned legality now lives in [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py).

Implemented behavior:
- defaults to `admin_band0.home_status`
- treats `admin_band0.shell_entry` as the landing alias to the home/status surface
- allows only `admin_band0.home_status` and `admin_band0.tool_registry`
- rejects non-internal audiences for Admin Band 0
- gates `admin_band1.aws_read_only_surface` with an explicit `slice_gated` error
- returns `slice_unknown` for unapproved slice ids
- keeps the registry static and shell-owned, not tool-owned

4. **Admin home/status payload implemented**

The home/status surface returned by [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py) now includes:
- current admin band
- internal-only exposure posture
- normalized tenant scope
- available internal admin slices
- gated future tool slices
- runtime health summary
- readiness summary
- fixed follow-on ordering: AWS, then Maps, then AGRO-ERP

It also provides a narrow audit-health check when `audit_storage_file` is supplied, without writing records or exposing paths.

5. **Tool registry/launcher behavior implemented**

The registry is now catalog-driven and deny-by-default:
- shell-owned catalog lives in [admin_shell.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py)
- runtime only composes that catalog in [admin_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py)
- no dynamic package scan
- no tool execution
- no direct provider route fallback
- AWS appears only as a planned, gated next slice
- `newsletter-admin` does not appear

6. **Tests run and results**

Ran and passed:
- `python3 -m unittest MyCiteV2.tests.unit.test_state_machine_admin_shell`
- `python3 -m unittest MyCiteV2.tests.integration.test_admin_runtime_composition`
- `python3 -m unittest MyCiteV2.tests.architecture.test_runtime_composition_boundaries`
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries`

Then ran the full required regression stack:
- `python3 -m unittest MyCiteV2.tests.unit.test_datum_refs MyCiteV2.tests.unit.test_state_machine_hanus_shell MyCiteV2.tests.unit.test_state_machine_admin_shell MyCiteV2.tests.contracts.test_audit_log_contracts MyCiteV2.tests.unit.test_local_audit MyCiteV2.tests.adapters.test_filesystem_audit_log_adapter MyCiteV2.tests.architecture.test_core_datum_refs_boundaries MyCiteV2.tests.architecture.test_state_machine_boundaries MyCiteV2.tests.architecture.test_ports_audit_log_boundaries MyCiteV2.tests.architecture.test_local_audit_boundaries MyCiteV2.tests.architecture.test_filesystem_adapter_boundaries MyCiteV2.tests.architecture.test_runtime_composition_boundaries MyCiteV2.tests.integration.test_mvp_runtime_composition MyCiteV2.tests.integration.test_admin_runtime_composition`

Result: `Ran 50 tests` and `OK`.

7. **Whether Admin Band 0 is now satisfied**

Yes. `Admin Band 0 Internal Admin Replacement` is now satisfied within the approved scope:
- one stable internal admin shell entry exists
- one tenant-safe runtime envelope exists
- one admin home/status surface exists
- one shell-owned deny-by-default registry exists
- they are integrated through one admin runtime path
- AWS is listed only as gated, not implemented

8. **What remains for the next prompt to implement the AWS read-only slice**

The next prompt can stay narrow:
- add the approved AWS read-only seam and adapter
- add the `admin.aws.read_only` runtime entrypoint
- plug that entrypoint into the existing shell-owned registry
- move the AWS registry entry from gated to approved when its tests pass
- keep shell entry, home/status, and registry behavior unchanged unless the AWS slice truly needs a small extension

9. **Blocked ambiguities that should remain deferred**

These should stay frozen:
- the exact future AWS port and adapter names
- whether dispatch-health belongs in the first AWS read-only slice or a later AWS follow-up slice
- whether admin home/status and tool registry later merge into one shell payload
- the exact bounded field set for the first AWS narrow write surface

---