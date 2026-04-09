# Execute Phase 03 for the MVP

## PROMPT:

Use Max reasoning for this one.

This version is tightened against the actual MVP boundary and the completed phase-02 output. It narrows phase 03 to the minimum serialized shell/state surface the MVP requires, keeps `state_machine` dependent only on inward core logic, and explicitly defers richer mediation behavior, tool attachment, and runtime concerns, which the current docs already require   

```text id="v0c4n1"
Work only inside `MyCiteV2/`.

Execute phase 03 for the already-defined MVP only.

This is an implementation task, but only for the MVP-approved state-machine and Hanus shell foundation.
Do not widen scope.
Do not compensate for later phases.
Do not implement ports, adapters, domain modules, tools, sandboxes, or runtime composition here.

==================================================
READ FIRST
==================================================

Read and follow, in order:
1. `MyCiteV2/docs/plans/authority_stack.md`
2. `MyCiteV2/docs/ontology/structural_invariants.md`
3. `MyCiteV2/docs/ontology/interface_surfaces.md`
4. `MyCiteV2/docs/glossary/ontology_terms.md`
5. `MyCiteV2/docs/contracts/import_rules.md`
6. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
7. `MyCiteV2/docs/plans/mvp_boundary.md`
8. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
9. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
10. `MyCiteV2/docs/plans/phases/03_state_machine_and_hanus_shell.md`
11. relevant `MyCiteV2/docs/plans/v1-migration/*` files about Hanus, AITAS, NIMM, and v1 drift
12. the phase-02 implementation already completed in `MyCiteV2/packages/core/datum_refs/`

Use v1 only as evidence of prior concepts and drift.
Do not copy v1 state-machine structure directly.
Do not create compatibility shims.

==================================================
PHASE-03 MVP SCOPE
==================================================

Implement only the minimal state-machine subareas required by the MVP:

- `MyCiteV2/packages/state_machine/aitas/`
- `MyCiteV2/packages/state_machine/nimm/`
- `MyCiteV2/packages/state_machine/hanus_shell/`

That is the only state-machine implementation area in scope for this task.

Explicitly out of scope for this task:
- `packages/state_machine/mediation_surface/`
- richer mediation projection behavior
- tool capability logic
- tool attachment logic
- sandbox orchestration logic
- any port interfaces
- any adapter implementations
- any runtime composition code
- any route or HTTP concerns
- any HOPS, SAMRAS, MSS, hosted, progeny, or crypto work

==================================================
IMPLEMENTATION GOAL
==================================================

Implement the minimum pure serialized shell/state foundation needed by the MVP end-to-end slice:

The MVP slice is:
- accept a serialized shell action over a canonical datum-ref subject
- reduce it through pure AITAS/NIMM/Hanus state logic
- later hand a normalized audit event to later-phase code
- later return a normalized runtime result containing shell state plus audit metadata

For this phase, implement only the pure state side of that slice.

The resulting state-machine layer must be:
- pure
- explicit
- serializable
- tool-independent
- host-independent
- adapter-independent
- deterministic

==================================================
EXPECTED STATE-MACHINE SURFACE
==================================================

Implement only the minimum code surface needed for MVP shell legality and state transitions, likely including:

1. serialized shell action contract
   - a minimal action shape that can carry:
     - a shell verb
     - a canonical datum-ref subject or focus subject
     - any minimal directive/intention data required by MVP

2. serialized shell state contract
   - a minimal explicit state shape for:
     - attention / focus
     - intention / directive, only to the degree MVP actually requires
     - accepted shell verb or shell-mode result if needed
     - any minimal normalized values required by later runtime result composition

3. reducer / transition logic
   - pure state transition logic from serialized action to serialized new state
   - no runtime side effects
   - no persistence
   - no adapter calls

4. normalized shell result contract
   - the pure state-machine result object that later phases can compose into the runtime result
   - this must not include audit persistence itself, only state-side output needed by the MVP slice

5. minimal AITAS / NIMM / Hanus vocabulary needed by the MVP
   - define only the minimal concepts actually used by the MVP slice
   - do not implement full conceptual breadth

==================================================
BOUNDARY RULES
==================================================

State-machine code may import only:
- `packages/core/*`
- standard library

State-machine code must not import:
- `instances/*`
- `packages/adapters/*`
- `packages/ports/*`
- `packages/modules/*`
- `packages/tools/*`
- `packages/sandboxes/*`

Do not bury shell meaning in UI, adapters, or runtime wrappers.
Do not create a view layer.
Do not implement tool-facing shell legality.
Do not create broad mediation logic beyond what the MVP strictly needs.

A UI widget is not the shell surface.
A runtime route is not the shell surface.
Tool capability is not shell ownership.

==================================================
SERIALIZATION RULE
==================================================

Everything implemented here must be explicitly serializable and stable as data.

Do not rely on hidden globals.
Do not rely on process-local state.
Do not rely on class instances that are not trivially serializable unless their outward contract is explicit and test-covered.

If a concept can be represented as plain structured data, prefer that.

==================================================
REQUIRED TESTS
==================================================

Add only the tests required for phase 03 and MVP scope.

At minimum include:
1. pure unit tests for shell action normalization
2. pure unit tests for reducer/state transitions
3. serialization tests for state and result contracts
4. contract-shape tests for action/state/result payloads
5. architecture-boundary tests for the implemented `packages/state_machine/*` surface, including:
   - no outward imports
   - no tool-defined shell truth
   - no host/runtime leakage
   - no adapter or port imports
   - no instance-path tokens
   - no sandbox semantics leakage

If architecture-boundary tests already exist, extend them narrowly for state_machine only.

==================================================
PROHIBITED SHORTCUTS
==================================================

Do not:
- implement ports here
- call filesystem or persistence code
- create runtime wrappers
- create HTTP route logic
- implement tool surfaces
- implement full mediation surface behavior
- add speculative state fields “for later”
- widen AITAS/NIMM/Hanus beyond MVP need
- create a generic `utils` bucket
- import v1 modules directly
- let tool, adapter, or runtime concerns define shell legality

==================================================
DOCUMENTATION RULE
==================================================

Update docs only if required by phase outputs or if implementation reveals a mismatch in:
- `mvp_boundary.md`
- `mvp_acceptance_criteria.md`
- `03_state_machine_and_hanus_shell.md`
- package-level README or contract docs under `packages/state_machine/`

Do not broaden the MVP boundary in docs.

==================================================
COMPLETION STANDARD
==================================================

This task is complete only if:
- the minimal AITAS/NIMM/Hanus shell foundation exists as real pure code
- the shell action, shell state, reducer, and normalized shell result are implemented
- all of them are serializable and deterministic
- tests pass
- import boundaries are clean
- nothing outside the approved phase-03 MVP scope was implemented

==================================================
END-OF-TASK RESPONSE
==================================================

Return:
1. the exact files created or updated
2. the state-machine surface implemented
3. the tests added
4. any architecture-boundary protections added
5. any scope reductions or exclusions enforced to stay inside MVP
6. any blocked ambiguities that should remain deferred to later phases
```

The main improvement over the earlier draft is that this one tells the agent exactly what phase 03 must produce for the MVP: serialized shell action, serialized shell state, reducer, and normalized shell result, with minimal AITAS/NIMM/Hanus vocabulary only, and with mediation/tool/runtime breadth explicitly deferred.

---


## OUTPUT:

**Files**
Created or updated for this phase-03 MVP task:

- [packages/state_machine/README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/README.md)
- [packages/state_machine/__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/__init__.py)
- [packages/state_machine/aitas/README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/aitas/README.md)
- [packages/state_machine/aitas/__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/aitas/__init__.py)
- [packages/state_machine/aitas/context.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/aitas/context.py)
- [packages/state_machine/nimm/README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/nimm/README.md)
- [packages/state_machine/nimm/__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/nimm/__init__.py)
- [packages/state_machine/nimm/directives.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/nimm/directives.py)
- [packages/state_machine/hanus_shell/README.md](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/README.md)
- [packages/state_machine/hanus_shell/__init__.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/__init__.py)
- [packages/state_machine/hanus_shell/contracts.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/contracts.py)
- [packages/state_machine/hanus_shell/reducer.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/reducer.py)
- [tests/unit/test_state_machine_hanus_shell.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_state_machine_hanus_shell.py)
- [tests/architecture/test_state_machine_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_state_machine_boundaries.py)

The worktree also showed `docs/archive/*` changes, but those were not part of the phase-03 implementation surface.

**State-machine surface**
Implemented the minimum pure shell/state foundation under `packages/state_machine`:

- [context.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/aitas/context.py)
  - `AitasContext`
  - `normalize_attention(...)`
  - MVP AITAS subset is only `attention` and `intention`
- [directives.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/nimm/directives.py)
  - `DEFAULT_SHELL_VERB = "navigate"`
  - `SUPPORTED_SHELL_VERBS = ("navigate",)`
  - `normalize_shell_verb(...)`
- [contracts.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/contracts.py)
  - `ShellAction`
  - `ShellState`
  - `ShellResult`
  - explicit `schema` values for action/state/result payloads
- [reducer.py](/srv/repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/reducer.py)
  - `reduce_shell_action(...)`

The implemented behavior is intentionally narrow:
- only one supported shell verb: `navigate`
- focus subjects must be qualified datum-refs
- qualified hyphen refs normalize to canonical dot refs
- reducer output is pure, serializable, and contains only state-side result data

**Tests added**
Added:

- [test_state_machine_hanus_shell.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_state_machine_hanus_shell.py)
- [test_state_machine_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_state_machine_boundaries.py)

They cover:

- shell action normalization
- invalid shell action rejection
- reducer/state transition behavior
- contract-shape round trips for action/state/result payloads
- JSON serialization of state/result contracts
- deterministic repeated reductions
- state-machine import and leakage boundaries

Ran and passed:

- `python3 -m unittest MyCiteV2.tests.unit.test_state_machine_hanus_shell`
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries`

**Architecture-boundary protections**
Added narrow protections in [test_state_machine_boundaries.py](/srv/repo/mycite-core/MyCiteV2/tests/architecture/test_state_machine_boundaries.py):

- AST-based import scan for outward imports
- explicit blocking of `instances`, adapters, ports, modules, tools, sandboxes, and direct `mycite_core` imports
- text-token scan for runtime/host leakage such as `instances/_shared`, `runtime_paths`, `service_tools`, and `SandboxEngine`

**Scope reductions enforced**
To stay inside the MVP phase-03 boundary, I explicitly did not implement:

- `packages/state_machine/mediation_surface/*`
- any port or adapter contract
- any tool legality or tool attachment logic
- any sandbox behavior
- any runtime wrapper or route code
- any verb beyond `navigate`
- time, archetype, spatial, HOPS, SAMRAS, MSS, hosted, progeny, or crypto expansion
- any broad action taxonomy beyond the minimal action/state/result contract

**Deferred ambiguities**
These should remain deferred to later phases:

- whether phase 04+ needs a broader shell action taxonomy beyond `shell_verb` plus `focus_subject`
- whether unqualified local datum-refs should ever be admitted at the shell boundary when runtime context can supply qualification
- how `mediation_surface` expands once later phases need projection behavior
- when `investigate`, `mediate`, and `manipulate` become legal NIMM directives in v2


---


## CONSIDERATION & ASSSMENT

This looks like a good phase-03 result.

It matches the MVP boundary closely. The MVP calls for one shell-facing path that accepts a serialized shell action over a canonical datum-ref subject, reduces it through pure AITAS/NIMM/Hanus logic, and leaves persistence/runtime work for later phases  The work you described stays inside that boundary by implementing only the narrow `state_machine` surface and explicitly excluding ports, adapters, tools, sandboxes, runtime wiring, and richer mediation behavior  

The strongest parts are:

The dependency direction is still clean. `aitas/context.py` imports only core datum-ref logic, and the state-machine contracts build on inward layers only, which is exactly what the import rules require for `packages/state_machine`  

The shell surface is explicit and serializable. The contracts now give you a real MVP shell data model:

* `ShellAction`
* `ShellState`
* `ShellResult`
  with explicit schemas and normalization rules, rather than hidden runtime state or UI-led meaning 

The narrowing is correct. The implementation limits the verb space to `navigate`, limits AITAS to `attention` and `intention`, and keeps Hanus/NIMM behavior minimal. That is the right move for this MVP. The phase doc says phase 03 should define serialized shell state, AITAS vocabulary, NIMM directives, and mediation-surface behavior independently of tools and hosts; your implementation takes only the minimal serialized shell/state part needed now and defers the rest cleanly 

The architecture protections are also appropriate. The added boundary tests blocking outward imports, `mycite_core`, runtime leakage, and host-specific tokens are consistent with the architecture-boundary checks and with the stated non-equivalence between shell surface, tools, routes, and sandboxes  

The main caution I would carry forward is this:

Right now, `intention` is effectively being used as the normalized shell verb. That is acceptable for the MVP, but it should remain an explicit MVP compression, not a permanent semantic collapse. In the fuller ontology, AITAS intention and NIMM directive / shell verb are related, but they are not automatically identical. The current summary already lists that broader action taxonomy is deferred, which is correct 

A second small caution: if `docs/archive/*` changed but was not part of the task, keep those changes out of the phase-03 commit. The implementation itself sounds clean, so unrelated worktree noise should not be allowed to blur the phase boundary.

So the judgment is:

Phase 03 appears successfully completed for the MVP slice.

You now have:

* pure datum-ref normalization from phase 02
* pure serialized shell/state contracts and reducer logic from phase 03

That means the next step should be phase 04, and phase 04 should stay just as narrow: define only the `audit_log` port needed by the MVP slice, nothing broader.


---