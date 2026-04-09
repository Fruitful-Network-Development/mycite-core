# Execute Phase 02 for the MVP

## PROMPT:

Work only inside `MyCiteV2/`.

Execute phase 02 for the already-defined MVP only.

This is an implementation task, but only for the MVP-approved pure core surface.
Do not widen scope.
Do not compensate for later phases.
Do not implement anything that belongs to state_machine, ports, modules, adapters, tools, sandboxes, or runtime composition.

==================================================
READ FIRST
==================================================

Read and follow, in order:
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/ontology/structural_invariants.md`
3. `MyCiteV2/docs/contracts/import_rules.md`
4. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
5. `MyCiteV2/docs/plans/mvp_boundary.md`
6. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
7. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
8. `MyCiteV2/docs/plans/phases/02_core_pure_modules.md`
9. any relevant `MyCiteV2/docs/plans/v1-migration/*` files that identify v1 datum-ref logic as evidence only

Use v1 only as implementation-history evidence.
Do not copy v1 package structure.
Do not create compatibility wrappers.

==================================================
PHASE-02 MVP SCOPE
==================================================

Implement only the pure core module area required by the MVP:

- `MyCiteV2/packages/core/datum_refs/`

That is the only core implementation area in scope for this task.

Explicitly out of scope for this task:
- `packages/core/identities/`
- `packages/core/structures/samras/`
- `packages/core/structures/hops/`
- `packages/core/mss/`
- `packages/core/crypto/`
- any cross-domain or domain module code
- any port definitions
- any adapter code
- any runtime composition code
- any tool code
- any sandbox code

==================================================
IMPLEMENTATION GOAL
==================================================

Recreate the minimum pure datum-ref normalization and validation logic required by the MVP end-to-end slice.

The output of this task must be sufficient for later phases to use datum-ref logic as a pure inward dependency, but it must not anticipate later concepts beyond what the MVP actually needs.

The resulting core module must be:
- deterministic
- standard-library-only unless an existing v2 authority doc explicitly allows otherwise
- free of runtime helpers
- free of instance-path logic
- free of adapter imports
- free of state_machine imports
- free of module, tool, sandbox, or runtime imports

==================================================
EXPECTED CODE SURFACE
==================================================

Implement only the minimum code surface needed for MVP datum-ref behavior, likely including:
- parsing
- validation
- normalization
- canonical formatting behavior required by the MVP slice
- explicit error behavior for malformed input

Do not add speculative APIs.
Do not add broader identity abstractions.
Do not add HOPS, SAMRAS, MSS, or crypto-adjacent helpers.
Do not create “future-useful” utilities unless they are required by the MVP slice.

==================================================
REQUIRED TESTS
==================================================

Add only the tests required for phase 02 and MVP scope.

At minimum include:
1. pure unit tests for datum-ref normalization
2. pure unit tests for invalid datum-ref rejection
3. determinism tests where appropriate
4. architecture-boundary tests for this implemented surface, including:
   - no outward imports
   - no `instances/` imports
   - no adapter imports
   - no runtime-path leakage
   - no hardcoded live-state paths or instance ids

If the repo already has architecture-boundary test scaffolding, extend it narrowly.
If not, add the smallest compliant tests needed for this phase only.

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if required by phase outputs or if implementation reveals a mismatch in:
- `mvp_boundary.md`
- `mvp_acceptance_criteria.md`
- `02_core_pure_modules.md`
- package-level README or contract docs for `packages/core/datum_refs/`

Do not rewrite broader phase docs.
Do not broaden the MVP boundary in docs.

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- import or reuse runtime path helpers
- import v1 modules directly
- create a generic “utils” bucket
- widen `datum_refs` into `identities`
- revive any v1 mixed-concern module shape
- pre-implement code needed for later phases
- create stubs for ports, adapters, tools, or runtime composition here

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:
- `packages/core/datum_refs/` exists as a real pure core implementation
- its tests pass
- its import boundaries are clean
- it remains narrow enough to match the MVP boundary
- nothing outside the approved phase-02 MVP scope was implemented

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the module surface implemented in `packages/core/datum_refs/`
3. the tests added
4. any architecture-boundary protections added
5. any scope reductions or exclusions enforced to stay inside MVP
6. any blocked ambiguities that should remain deferred to later phases

---

## OUTPUT:


**Files**
Created or updated for this phase-02 MVP task:

- [refs.py](/srv/repo/mycite-core/MyCiteV2/packages/core/datum_refs/refs.py)
- [__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/core/datum_refs/__init__.py)
- [README.md](/srv/repo/mycite-core/MyCiteV2/packages/core/datum_refs/README.md)
- [test_datum_refs.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_datum_refs.py)
- [test_core_datum_refs_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_core_datum_refs_boundaries.py)

I did not implement anything outside `packages/core/datum_refs/` and its narrow tests.

**Module surface**
Implemented in [refs.py](/srv/repo/mycite-core/MyCiteV2/packages/core/datum_refs/refs.py):

- `ParsedDatumRef`
- `parse_datum_ref(value, *, field_name="datum_ref")`
- `normalize_datum_ref(value, *, local_msn_id="", require_qualified=False, write_format="dot", field_name="datum_ref")`

Supported datum-ref forms are exactly:

- local: `4-1-77`
- qualified dot: `<msn_id>.4-1-77`
- qualified hyphen: `<msn_id>-4-1-77`

The module is standard-library-only, deterministic, and has no runtime/state/adapter/module/tool/sandbox imports.

**Tests added**
Added:

- [test_datum_refs.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_datum_refs.py)
- [test_core_datum_refs_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_core_datum_refs_boundaries.py)

They cover:

- local, dot, and hyphen parsing
- canonical normalization to `dot`, `hyphen`, and `local`
- malformed datum-ref rejection
- missing or invalid qualification rejection
- deterministic repeated normalization
- architecture-boundary enforcement for the implemented package

Verified with:

- `python3 -m unittest MyCiteV2.tests.unit.test_datum_refs`
- `python3 -m unittest MyCiteV2.tests.architecture.test_core_datum_refs_boundaries`

Both passed.

**Architecture protections**
Added narrow boundary protections in [test_core_datum_refs_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_core_datum_refs_boundaries.py):

- AST-based import scan blocking outward imports
- explicit rejection of `instances`, adapters, state_machine, modules, ports, tools, and sandboxes
- source-token scan blocking runtime-path leakage, live-state tokens, and hardcoded instance ids

**Scope kept narrow**
To stay inside the approved MVP phase:

- did not implement `is_datum_ref`, identifier-candidate helpers, or broader utility APIs
- did not implement `identities`, `mss`, `structures`, `crypto`, or any later-phase package
- did not add ports, adapters, runtime helpers, compatibility wrappers, or v1 package shapes
- only updated the local `datum_refs` package README for accuracy

**Deferred ambiguities**
These remain intentionally deferred to later phases:

- whether runtime-facing canonical subjects must always be qualified-dot before state reduction
- whether any datum-ref variants beyond local, qualified-dot, and qualified-hyphen are ever admitted
- whether later phases need lookup/candidate expansion helpers tied to MSS or other identity surfaces


---