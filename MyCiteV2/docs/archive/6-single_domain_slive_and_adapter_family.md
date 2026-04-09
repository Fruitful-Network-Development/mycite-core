# Single Domain Slice & Adapter Family

## PROMPT:

Work only inside `MyCiteV2/`.

Execute only the minimum required parts of phases 05 and 06 for the already-defined MVP.

This is an implementation task, but only for:
- the single MVP cross-domain module
- the single MVP adapter family

Do not widen scope.
Do not compensate for later phases.
Do not implement runtime composition, tools, sandboxes, extra domains, extra ports, or extra adapters here.

Do not touch unrelated worktree changes outside the approved phase-05/06 MVP surface.

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
8. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
9. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
10. `MyCiteV2/docs/plans/phases/05_domain_and_cross_domain_modules.md`
11. `MyCiteV2/docs/plans/phases/06_adapters.md`
12. `MyCiteV2/docs/plans/v1-migration/v1_retention_vs_recreation.md`
13. `MyCiteV2/docs/plans/v1-migration/source_authority_index.md`
14. the already-completed MVP implementations in:
   - `MyCiteV2/packages/core/datum_refs/`
   - `MyCiteV2/packages/state_machine/aitas/`
   - `MyCiteV2/packages/state_machine/nimm/`
   - `MyCiteV2/packages/state_machine/hanus_shell/`
   - `MyCiteV2/packages/ports/audit_log/`

Use v1 only as lower-precedence evidence.
Do not copy v1 package shapes.
Do not create compatibility wrappers.

==================================================
PHASE-05/06 MVP SCOPE
==================================================

Implement only these areas:

Phase 05:
- `MyCiteV2/packages/modules/cross_domain/local_audit/`

Phase 06:
- `MyCiteV2/packages/adapters/filesystem/` only to the extent required to implement the `audit_log` port for the MVP slice

That is the full implementation scope for this task.

Explicitly out of scope:
- all `packages/modules/domains/*`
- `packages/modules/cross_domain/external_events/`
- all other cross-domain modules
- all other adapter families
- all runtime composition code
- all tools
- all sandboxes
- all additional ports
- all query/index/search expansion beyond the MVP slice
- all hosted/progeny work
- all HOPS, SAMRAS, MSS, crypto, or broader mediation work

==================================================
IMPLEMENTATION GOAL
==================================================

Implement the MVP cross-domain semantics and adapter behavior required by the single proving slice:

Shell Action To Local Audit:
- phase 03 already produces the pure shell-side state/result surface
- phase 04 already defines the `audit_log` port contract
- this task must now:
  1. define narrow `local_audit` semantic rules
  2. provide one filesystem adapter that satisfies `AuditLogPort`
  3. preserve ownership boundaries between semantics and storage

The resulting implementation must allow later runtime composition to:
- hand one normalized audit record into `local_audit`
- have `local_audit` validate and normalize its semantic record boundary
- pass that record through `AuditLogPort`
- persist and read it back through the filesystem adapter

==================================================
PHASE 05: LOCAL_AUDIT OWNERSHIP
==================================================

Implement only the narrow semantic surface for `packages/modules/cross_domain/local_audit/`.

This module should own:
- normalized local-audit record policy
- secret-key rejection / forbidden-key rejection
- explicit handoff to the `AuditLogPort`
- narrow read/append semantics required by the MVP
- no broader event or logging framework

This module must not own:
- filesystem paths
- runtime wiring
- shell legality
- tool behavior
- sandbox behavior
- general external-event semantics

Keep it narrow.
Do not recreate a generic `services` bucket in disguise.

Likely acceptable outputs include:
- record normalization helpers
- forbidden-key / secret-key checks
- a narrow service object or functions that:
  - append one normalized local-audit record via `AuditLogPort`
  - read one local-audit record by id via `AuditLogPort`
- explicit result contracts if needed, but only if narrower than reusing raw port contracts would be

==================================================
PHASE 06: FILESYSTEM ADAPTER OWNERSHIP
==================================================

Implement only the narrow filesystem adapter needed to satisfy `AuditLogPort`.

The filesystem adapter should own:
- outward-facing persistence details
- record storage and retrieval mechanics
- adapter conformance to `AuditLogPort`

The filesystem adapter must not own:
- local-audit semantic validation
- redaction/forbidden-key policy
- shell-state meaning
- runtime routing or composition
- tool-specific hacks
- instance-led hardcoding in reusable logic

Keep filesystem assumptions narrow and reusable.
Do not build a broader filesystem framework.

==================================================
BOUNDARY RULES
==================================================

Phase 05 module rules:
- may import inward layers and ports
- must not import adapters or instances
- must not define runtime behavior
- must not redefine shell/state meaning

Phase 06 adapter rules:
- may import inward layers and the `audit_log` port
- must not absorb semantic ownership from `local_audit`
- must not define shell truth
- must not define runtime routes
- must not hardcode instance-specific layouts unless the MVP absolutely requires a minimal local adapter path and that choice is isolated, documented, and kept outward

==================================================
EXPECTED TESTS
==================================================

Add only the tests required for this MVP slice.

At minimum include:

1. phase-05 module tests
- local-audit record normalization
- forbidden-key / secret-key rejection
- append handoff behavior against a fake or stub `AuditLogPort`
- read-by-id handoff behavior against a fake or stub `AuditLogPort`

2. phase-06 adapter tests
- filesystem adapter conformance to `AuditLogPort`
- append then read round-trip behavior
- persisted metadata behavior consistent with the port contract

3. architecture-boundary tests
- no adapter imports into `local_audit`
- no instance/runtime leakage into inward layers
- no semantic ownership leakage into filesystem adapter
- no tool or sandbox imports
- no direct `mycite_core` imports

If architecture-boundary tests already exist, extend them narrowly for:
- `packages/modules/cross_domain/local_audit/`
- `packages/adapters/filesystem/`

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- implement runtime composition here
- implement HTTP routes or shell-facing runtime wrappers
- add extra ports
- add extra adapters
- broaden `local_audit` into a generic event framework
- move semantics into the filesystem adapter
- move filesystem policy into the cross-domain module
- add tool integration
- add sandbox orchestration
- implement `external_events`
- create query/filter/index APIs beyond the MVP need
- introduce instance-specific hardcoding into inward layers

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if required by phase outputs or if implementation reveals a mismatch in:
- `mvp_boundary.md`
- `mvp_acceptance_criteria.md`
- `05_domain_and_cross_domain_modules.md`
- `06_adapters.md`
- package-level README or contract docs under:
  - `packages/modules/cross_domain/local_audit/`
  - `packages/adapters/filesystem/`

Do not broaden the MVP boundary in docs.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:
- `packages/modules/cross_domain/local_audit/` exists as a narrow semantic owner
- `packages/adapters/filesystem/` exists as a narrow `AuditLogPort` implementation
- their tests pass
- ownership boundaries remain clean
- nothing outside the approved phase-05/06 MVP scope was implemented

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the local-audit module surface implemented
3. the filesystem adapter surface implemented
4. the exact dependency direction preserved between:
   - core
   - state_machine
   - ports
   - cross_domain/local_audit
   - adapters/filesystem
5. the tests added
6. any architecture-boundary protections added
7. any scope reductions or exclusions enforced to stay inside MVP
8. what remains for runtime integration
9. any blocked ambiguities that should remain deferred to later phases


---


## OUTPUT:

**Files**
Created or updated inside `MyCiteV2/`:

- [service.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/local_audit/service.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/local_audit/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/local_audit/README.md)
- [audit_log.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/audit_log.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/README.md)
- [test_local_audit.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_local_audit.py)
- [test_filesystem_audit_log_adapter.py](/srv/repo/mycite-core/MyCiteV2/tests/adapters/test_filesystem_audit_log_adapter.py)
- [test_local_audit_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_local_audit_boundaries.py)
- [test_filesystem_adapter_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py)

**Local Audit Surface**
Implemented in [service.py](/srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/local_audit/service.py):

- `FORBIDDEN_LOCAL_AUDIT_KEYS`
- `LocalAuditRecord`
- `StoredLocalAuditRecord`
- `normalize_local_audit_record(...)`
- `LocalAuditService`

What it does:
- normalizes `event_type`, `shell_verb`, and `focus_subject`
- canonicalizes `focus_subject` through core datum-ref logic
- rejects unsupported top-level fields
- rejects forbidden secret-like keys inside nested `details`
- appends one normalized record through `AuditLogPort`
- reads one stored record by id through `AuditLogPort`

**Filesystem Adapter Surface**
Implemented in [audit_log.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/audit_log.py):

- `FilesystemAuditLogAdapter`

What it does:
- satisfies `AuditLogPort`
- persists records to one caller-supplied NDJSON file
- generates `record_id` and `recorded_at_unix_ms`
- reads one record back by opaque `record_id`
- keeps storage details outward and generic

**Dependency Direction Preserved**
The implemented direction stayed narrow:

- `packages/core/datum_refs` remains purely inward.
- `packages/state_machine/*` remains independent of ports, modules, and adapters.
- `packages/ports/audit_log` remains contract-only and imports no modules or adapters.
- `packages/modules/cross_domain/local_audit` imports only core datum-ref logic plus the `audit_log` port.
- `packages/adapters/filesystem` imports only standard library plus the `audit_log` port.
- `packages/adapters/filesystem` does not import `local_audit`, so semantic ownership stays in the module, not the adapter.

**Tests Added**
Added and passed:

- [test_local_audit.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_local_audit.py)
  - record normalization
  - forbidden-key rejection
  - append handoff to a fake `AuditLogPort`
  - read-by-id handoff to a fake `AuditLogPort`
- [test_filesystem_audit_log_adapter.py](/srv/repo/mycite-core/MyCiteV2/tests/adapters/test_filesystem_audit_log_adapter.py)
  - `AuditLogPort` conformance
  - append/read round trip
  - not-found behavior
- [test_local_audit_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_local_audit_boundaries.py)
- [test_filesystem_adapter_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_filesystem_adapter_boundaries.py)

Executed:

- `python3 -m unittest MyCiteV2.tests.unit.test_local_audit`
- `python3 -m unittest MyCiteV2.tests.adapters.test_filesystem_audit_log_adapter`
- `python3 -m unittest MyCiteV2.tests.architecture.test_local_audit_boundaries`
- `python3 -m unittest MyCiteV2.tests.architecture.test_filesystem_adapter_boundaries`

**Architecture Protections**
Added boundary checks for:

- no adapter imports into `local_audit`
- no `instances` or runtime-path leakage into `local_audit`
- no tool or sandbox imports
- no direct `mycite_core` imports
- no module-semantic imports into the filesystem adapter
- no local-audit field knowledge leaked into the filesystem adapter source

**Scope Kept Tight**
Explicitly kept out of this task:

- runtime composition
- `external_events`
- all domain modules
- all extra adapters
- all extra ports
- any search/query/index API
- any tool or sandbox work
- any instance-led path logic in inward layers

The adapter takes a caller-supplied storage file path, so no runtime layout was hardcoded into reusable semantics.

**What Remains For Runtime Integration**
Runtime integration still needs to:

- build the phase-03 shell result path
- instantiate `FilesystemAuditLogAdapter` with a chosen storage file
- instantiate `LocalAuditService` with that adapter
- create the MVP local-audit record from the shell-side result
- append it, optionally read it back, and compose persisted metadata into the runtime response

**Deferred Ambiguities**
These should stay deferred:

- whether `LocalAuditRecord` stays at its current strict four-field shape or expands later
- whether runtime integration should rely only on append receipt metadata or also always perform a read-back
- whether the filesystem adapter remains single-file NDJSON or later moves to a different outward storage layout
- whether later phases want shell-verb validation in `local_audit` or keep it semantically looser than state-machine legality


---


## CONSIDERATION & ASSSMENT

This looks good.

It matches the MVP boundary closely. The MVP includes only one cross-domain module, `local_audit`, and one adapter family, `filesystem`, while excluding domain modules, `external_events`, tools, sandboxes, extra ports, and runtime composition 

The separation of ownership is the strongest part.

`local_audit/service.py` owns semantic normalization and policy:

* canonicalizes `focus_subject`
* normalizes `event_type` and `shell_verb`
* rejects unsupported top-level fields
* rejects secret-like nested keys
* hands off through `AuditLogPort` rather than doing storage itself 

The filesystem adapter stays outward-facing:

* implements `AuditLogPort`
* writes and reads NDJSON
* generates `record_id` and `recorded_at_unix_ms`
* does not import or depend on `local_audit` semantics 

That dependency direction is exactly what you want at this point:

* core stays inward
* state machine stays independent
* port stays contract-only
* `local_audit` depends on core + port
* filesystem adapter depends on port, not on module semantics  

The scope control also looks right. The task stayed out of runtime composition, extra adapters, extra ports, tools, sandboxes, and broad event modeling, which is correct for this MVP slice 

The main caution I would carry forward is small:

`LocalAuditRecord` currently normalizes `shell_verb` to lowercase but does not validate it against the state-machine’s legal verb set. That is acceptable because your summary explicitly keeps that question deferred, but it should remain an intentional boundary, not an accident. If later runtime integration needs exact verb legality, that should be decided explicitly rather than drifting into either layer 

A second minor caution is that `StoredLocalAuditRecord` coerces `recorded_at_unix_ms` with `int(...)` rather than applying the same stricter non-negative validation the port contract uses. That is not a major problem for the MVP, but it is one place where later tightening may be useful.

Overall judgment:

Phases 05 and 06 appear successfully completed for the MVP slice.

You now have:

* phase 02 pure datum-ref core
* phase 03 pure serialized shell/state foundation
* phase 04 narrow audit-log port contract
* phase 05 local-audit semantic owner
* phase 06 filesystem adapter

The next prompt should be phase 09 plus the minimum phase-10 integration/testing work needed to compose the full MVP path:
serialized shell action → state reduction → local audit append → filesystem persistence → normalized runtime result.


---
