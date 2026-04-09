# Execute Phase 04 for MVP Ports

## PROMPT:

Work only inside `MyCiteV2/`.

Execute phase 04 for the already-defined MVP only.

This is an implementation task, but only for the MVP-approved port surface.
Do not widen scope.
Do not compensate for later phases.
Do not implement adapters, cross-domain semantics, runtime composition, tools, sandboxes, or additional ports here.

Do not touch unrelated worktree changes outside the phase-04 MVP surface.

==================================================
READ FIRST
==================================================

Read and follow, in order:
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/ontology/structural_invariants.md`
3. `MyCiteV2/docs/ontology/dependency_direction.md`
4. `MyCiteV2/docs/ontology/interface_surfaces.md`
5. `MyCiteV2/docs/contracts/module_contract_template.md`
6. `MyCiteV2/docs/contracts/import_rules.md`
7. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
8. `MyCiteV2/docs/plans/mvp_boundary.md`
9. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
10. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
11. `MyCiteV2/docs/plans/phases/04_ports.md`
12. the already-completed MVP implementations in:
   - `MyCiteV2/packages/core/datum_refs/`
   - `MyCiteV2/packages/state_machine/aitas/`
   - `MyCiteV2/packages/state_machine/nimm/`
   - `MyCiteV2/packages/state_machine/hanus_shell/`

Use v1 only as lower-precedence evidence if truly needed.
Do not copy v1 port shapes.
Do not create compatibility shims.

==================================================
PHASE-04 MVP SCOPE
==================================================

Implement only the minimal port set required by the MVP:

- `MyCiteV2/packages/ports/audit_log/`

That is the only port implementation area in scope for this task.

Explicitly out of scope for this task:
- `packages/ports/datum_store/`
- `packages/ports/payload_store/`
- `packages/ports/event_log/`
- `packages/ports/resource_resolution/`
- `packages/ports/session_keys/`
- `packages/ports/time_projection/`
- `packages/ports/shell_surface/`
- any adapter code
- any cross-domain module code
- any runtime composition code
- any tool or sandbox code

==================================================
IMPLEMENTATION GOAL
==================================================

Define the minimum inward-facing `audit_log` contract required by the MVP end-to-end slice.

The MVP slice needs a later path that:
- takes normalized shell-side output from the state machine
- passes a normalized local-audit event to a cross-domain module
- persists and reads it through an `audit_log` contract
- later composes that through one filesystem adapter and one runtime path

For this phase, implement only the contract side of that seam.

The `audit_log` port must:
- be explicit
- be narrow
- be serialization-friendly
- be adapter-neutral
- be runtime-neutral
- not own local-audit semantics
- not own filesystem policy
- not own shell-state legality

==================================================
EXPECTED PORT SURFACE
==================================================

Implement only the minimum contract surface needed for MVP audit-log interaction, likely including:

1. explicit append contract
   - accepts an already-normalized audit record payload
   - returns a normalized persistence result or append result contract

2. explicit read contract
   - supports the minimum read shape required by the MVP slice
   - does not assume broad querying or indexing features unless the MVP requires them

3. optional contract types
   - dataclasses, protocols, or other explicit contract structures are allowed if they remain narrow
   - prefer plain structured data unless a stronger type contract is clearly useful

4. no adapter implementation details
   - no filesystem path assumptions
   - no directory layouts
   - no runtime wrappers
   - no concrete storage code

==================================================
BOUNDARY RULES
==================================================

The port layer may import inward layers only, and should stay as close to contract-only as possible.

Do not import:
- `instances/*`
- `packages/adapters/*`
- `packages/modules/*`
- `packages/tools/*`
- `packages/sandboxes/*`

Do not let the port define:
- shell truth
- local-audit redaction policy
- event semantics beyond the narrow append/read contract
- filesystem naming/layout
- runtime routing behavior

A port interface is a capability boundary, not a broad service bucket.

==================================================
SEMANTIC OWNERSHIP RULE
==================================================

Be careful here:

- phase 03 already owns shell action/state/result meaning
- phase 05 will own `local_audit` semantic rules
- phase 06 will own filesystem implementation details

Therefore phase 04 must not absorb either phase-03 or phase-05/06 concerns.

In this phase, define only the smallest stable contract that those later phases can meet.

==================================================
REQUIRED TESTS
==================================================

Add only the tests required for the phase-04 MVP port surface.

At minimum include:
1. contract tests for the `audit_log` append shape
2. contract tests for the `audit_log` read shape
3. serialization or payload-shape tests if contract dataclasses or typed payloads are introduced
4. architecture-boundary tests for the implemented `packages/ports/audit_log/` surface, including:
   - no adapter imports
   - no runtime or instance-path leakage
   - no filesystem-specific assumptions in the port contract
   - no module/tool/sandbox imports
   - no shell-ownership leakage

If architecture-boundary tests already exist, extend them narrowly for `packages/ports/audit_log/` only.

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- create the filesystem adapter here
- create `local_audit` semantic logic here
- embed redaction rules here
- embed runtime result composition here
- create a broad generic logging/event framework
- pre-implement future ports
- create speculative query/filter APIs not required by MVP
- widen the port surface for future convenience
- use v1 helper imports directly
- define storage paths or instance roots

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if required by phase outputs or if implementation reveals a mismatch in:
- `mvp_boundary.md`
- `mvp_acceptance_criteria.md`
- `04_ports.md`
- package-level README or contract docs under `packages/ports/audit_log/`

Do not broaden the MVP boundary in docs.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:
- `packages/ports/audit_log/` exists as a real narrow contract surface
- its tests pass
- it remains contract-only and adapter-neutral
- import boundaries are clean
- nothing outside the approved phase-04 MVP scope was implemented

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the port surface implemented in `packages/ports/audit_log/`
3. why each contract element is necessary for the MVP slice
4. the tests added
5. any architecture-boundary protections added
6. any scope reductions or exclusions enforced to stay inside MVP
7. any blocked ambiguities that should remain deferred to later phases


---


## OUTPUT:

1. Exact files created or updated:

- [contracts.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/audit_log/contracts.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/audit_log/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/ports/audit_log/README.md)
- [test_audit_log_contracts.py](/srv/repo/mycite-core/MyCiteV2/tests/contracts/test_audit_log_contracts.py)
- [test_ports_audit_log_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_ports_audit_log_boundaries.py)

2. Port surface implemented in `packages/ports/audit_log/`:

- `AuditLogAppendRequest`
  - carries one already-normalized audit record payload as a non-empty JSON-serializable dict
- `AuditLogAppendReceipt`
  - returns the minimum persisted metadata the MVP needs from append: `record_id` and `recorded_at_unix_ms`
- `AuditLogReadRequest`
  - reads one persisted record by opaque `record_id`
- `AuditLogRecord`
  - represents one persisted audit record with metadata plus payload
- `AuditLogReadResult`
  - returns either one `AuditLogRecord` or `None`, with a derived `found` flag
- `AuditLogPort`
  - protocol with:
    - `append_audit_record(request)`
    - `read_audit_record(request)`

3. Why each contract element is necessary for the MVP slice:

- `AuditLogAppendRequest` is needed because phase 05 will hand phase 06 one normalized local-audit record, and this phase needs a stable seam for that handoff.
- `AuditLogAppendReceipt` is needed because the MVP runtime result must later include persisted audit metadata, and the narrowest useful metadata is identifier plus persisted timestamp.
- `AuditLogReadRequest` is needed because the MVP slice explicitly requires a read path through the port, not append-only behavior.
- `AuditLogRecord` is needed because the read side must return both persisted metadata and the stored normalized payload in one explicit structure.
- `AuditLogReadResult` is needed because the read path must distinguish found vs not-found without inventing broader query semantics.
- `AuditLogPort` is needed because phase 06 requires an adapter target, and the port has to be an explicit capability boundary rather than an implied helper API.

4. Tests added:

- [test_audit_log_contracts.py](/srv/repo/mycite-core/MyCiteV2/tests/contracts/test_audit_log_contracts.py)
  - append-shape contract test
  - invalid append payload rejection
  - append receipt serialization
  - read request serialization
  - read result found/not-found shapes
  - record metadata validation
- [test_ports_audit_log_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_ports_audit_log_boundaries.py)
  - outward-import boundary check
  - runtime/filesystem/shell-leakage token check

Passed with:

- `python3 -m unittest MyCiteV2.tests.contracts.test_audit_log_contracts`
- `python3 -m unittest MyCiteV2.tests.architecture.test_ports_audit_log_boundaries`

5. Architecture-boundary protections added:

- AST import scan blocking:
  - `instances`
  - adapters
  - modules
  - tools
  - sandboxes
  - direct `mycite_core` imports
- source-token scan blocking:
  - runtime-path leakage
  - filesystem-specific assumptions such as `pathlib`, `os.path`, `ndjson`, and `filesystem`
  - shell-ownership leakage via `shell_state`

6. Scope reductions and exclusions enforced to stay inside MVP:

- no adapter code
- no `local_audit` semantic logic
- no redaction policy
- no runtime composition
- no query/filter/index API beyond read-by-id
- no additional ports
- no filesystem layout, directory, or path contract
- no shell-state legality or state-machine meaning inside the port

7. Blocked ambiguities that should remain deferred:

- whether later phases need a broader persisted metadata surface than `record_id` plus `recorded_at_unix_ms`
- whether read-by-id remains sufficient once the runtime path is implemented, or whether a second narrow read shape is needed later
- whether phase 05 will require stronger typing for the normalized audit payload fields themselves, rather than the current JSON-serializable record boundary


---


## CONSIDERATION & ASSSMENT

HERE


---