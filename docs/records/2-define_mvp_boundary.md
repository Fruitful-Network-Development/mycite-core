# Define MVP Boundary

## Prompt

You are working in `mycite-core`, inside the already-created `MyCiteV2/` scaffold.

Your task is not to implement the MVP.

Your task is to define the exact MVP boundary for MyCiteV2 in a way that minimizes later implementation scope while still proving that the v2 architecture is real, coherent, and testable.

You must optimize for:
- the smallest coherent MVP
- strict adherence to the existing v2 authority stack
- no reintroduction of v1 structural drift
- one narrow proving slice rather than broad partial coverage
- documentation that later agents can execute against with minimal ambiguity

Do not invent a new architecture.
Do not widen scope for conceptual completeness.
Do not treat “important later features” as MVP by default.

==================================================
AUTHORITIES TO USE
==================================================

Use the current v2 authority stack first.

Read and follow, in order:
1. `MyCiteV2/README.md`
2. `MyCiteV2/docs/plans/authority_stack.md`
3. `MyCiteV2/docs/ontology/structural_invariants.md`
4. `MyCiteV2/docs/contracts/import_rules.md`
5. `MyCiteV2/docs/testing/architecture_boundary_checks.md`
6. `MyCiteV2/docs/plans/master_build_sequence.md`
7. the phase docs, especially:
   - `MyCiteV2/docs/plans/phases/02_core_pure_modules.md`
   - `MyCiteV2/docs/plans/phases/03_state_machine_and_hanus_shell.md`
   - `MyCiteV2/docs/plans/phases/04_ports.md`
   - `MyCiteV2/docs/plans/phases/05_domain_and_cross_domain_modules.md`
   - `MyCiteV2/docs/plans/phases/06_adapters.md`
   - `MyCiteV2/docs/plans/phases/07_tools.md`
   - `MyCiteV2/docs/plans/phases/08_sandboxes.md`
   - `MyCiteV2/docs/plans/phases/09_runtime_composition.md`
   - `MyCiteV2/docs/plans/phases/10_integration_testing.md`
8. `MyCiteV2/docs/plans/implementation_prohibition_for_scaffold_phase.md`
9. `MyCiteV2/docs/plans/v1-migration/v1_drift_ledger.md`
10. `MyCiteV2/docs/plans/v1-migration/v1_audit_map.md`
11. `MyCiteV2/docs/plans/v1-migration/v1_retention_vs_recreation.md`
12. `MyCiteV2/docs/plans/v1-migration/source_authority_index.md`

Then use v1 plan docs as lower-precedence evidence:
- `docs/plans/tool_dev.md`
- `docs/plans/hanus_interface_model.md`
- `docs/plans/tool_alignment.md`
- other relevant `docs/plans/*.md`

Then use v1 code only as evidence of what existed, what drifted, and what must not be copied structurally.

Do not treat v1 code as a template.

==================================================
PRIMARY DECISION RULE
==================================================

The MVP must be the smallest buildable, testable, demonstrable version of MyCiteV2 that proves the architecture.

That means the MVP must validate:
1. pure core recreation
2. pure state/navigation recreation
3. minimal ports
4. one recreated domain or cross-domain module
5. one adapter family
6. one shell-facing runtime composition path
7. one integration path
8. required architecture-boundary checks

Anything beyond that must be excluded unless it is strictly required for coherence.

Tools, sandboxes, multiple domains, multiple adapters, additional runtime flavors, hosted/progeny, and advanced surfaces are out of scope by default unless you determine they are required for the single proving slice.

==================================================
YOUR JOB
==================================================

Determine and document:

1. the exact MVP functional claim
2. the exact included phases needed to reach MVP
3. the exact excluded phases or partial phase outputs that may be deferred
4. the exact module areas in scope
5. the exact single end-to-end slice that should prove the MVP
6. the exact minimum tests required to claim MVP
7. the exact unresolved decisions that should be frozen rather than solved now

You must choose, not hedge.

If multiple MVP candidates are plausible, select one recommended MVP and justify why it is the narrowest coherent proving slice.

==================================================
QUESTIONS YOU MUST ANSWER
==================================================

Your work must answer these exactly:

1. What is the exact functional claim of the MVP?
   What can a person, runtime, or agent actually do in the MVP?

2. Which phases from the master build sequence are required for MVP completion?
   Which outputs from each included phase are mandatory?
   Which outputs are explicitly deferred?

3. Which module areas are in the MVP?
   Decide exact inclusion/exclusion for:
   - `packages/core`
   - `packages/state_machine`
   - `packages/ports`
   - `packages/modules/domains`
   - `packages/modules/cross_domain`
   - `packages/adapters`
   - `packages/tools`
   - `packages/sandboxes`
   - `instances/_shared/runtime`

4. What is the single proving end-to-end slice?
   Choose one narrow slice only.

5. What is explicitly out of scope for MVP?
   Name deferred domains, tools, adapters, sandbox work, runtime flavors, advanced surfaces, hosted/progeny decisions, and any broad integrations.

6. What tests are required to claim MVP?
   Define the minimum passing loops:
   - pure unit loop
   - state machine loop
   - port/contract loop
   - adapter loop
   - integration loop
   - architecture boundary loop

7. Which unresolved decisions must be frozen for MVP rather than solved now?

==================================================
EXPECTED OUTPUT FILES
==================================================

Create or update these files:

1. `MyCiteV2/docs/plans/mvp_boundary.md`
2. `MyCiteV2/docs/plans/mvp_acceptance_criteria.md`
3. `MyCiteV2/docs/plans/mvp_out_of_scope.md`
4. `MyCiteV2/docs/plans/mvp_end_to_end_slice.md`
5. `MyCiteV2/docs/decisions/decision_record_0009_mvp_boundary.md`

Update other docs only if needed for consistency with the new MVP definition.

==================================================
REQUIRED STRUCTURE OF `mvp_boundary.md`
==================================================

Use these sections exactly:

1. Purpose
2. Authority and source precedence
3. Recommended MVP statement
4. Why this is the narrowest coherent MVP
5. Mandatory architecture pillars
6. Included phase outputs
7. Included module areas
8. Chosen end-to-end slice
9. Minimum required tests
10. Explicitly deferred work
11. Frozen decisions for MVP
12. Completion rule
13. Follow-on work after MVP

==================================================
IMPORTANT CONSTRAINTS
==================================================

- Do not implement application code.
- Do not widen scope to solve future phases early.
- Do not redefine the authority stack.
- Do not contradict structural invariants.
- Do not assume tools are required.
- Do not assume sandboxes are required.
- Do not use vague scope language.
- Do not leave inclusion/exclusion implicit.
- Do not produce a report outside the repo docs.
- Produce authoritative planning documents inside `MyCiteV2/`.

==================================================
DECISION HEURISTICS
==================================================

Use these filters when choosing the MVP:

- prefer the smallest boundary that still validates the architecture
- prefer one vertical slice over many partial slices
- prefer proving dependency direction over proving breadth
- prefer proving state purity over adding UI breadth
- prefer one adapter family only
- prefer one domain or cross-domain module only
- prefer one runtime composition path only
- include tools only if the MVP cannot be coherent without one
- include sandboxes only if the MVP cannot be coherent without one
- defer anything that is not required to prove the architecture

==================================================
END-OF-TASK RESPONSE
==================================================

At the end, return:

1. the exact MVP statement in 3 to 6 lines
2. the recommended included phases
3. the excluded major areas
4. the single proving end-to-end slice
5. the files created or updated
6. any remaining ambiguities that should stay frozen for MVP

---

## Output

The MVP is one shell-facing runtime path that accepts a serialized shell action over a canonical datum-ref subject, reduces it through pure AITAS/NIMM/Hanus state logic, persists one redacted local-audit record through an `audit_log` port backed by a filesystem adapter, and returns a normalized result with shell state plus audit metadata.  
It proves core, state_machine, ports, one cross-domain module, one adapter family, one runtime composition path, one integration path, and architecture-boundary enforcement.  
It does not require tools, sandboxes, domain modules, multiple adapters, or multiple runtime flavors.

Recommended included phases are `02`, `03`, `04`, `05`, `06`, `09`, and `10`, with partial outputs only where the MVP stays narrow. The exact boundary is defined in [mvp_boundary.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/mvp_boundary.md) and accepted in [decision_record_0009_mvp_boundary.md](/srv/repo/mycite-core/MyCiteV2/docs/decisions/decision_record_0009_mvp_boundary.md).

Excluded major areas are:
- `packages/modules/domains/*`
- `packages/modules/cross_domain/external_events`
- all `packages/tools/*`
- all `packages/sandboxes/*`
- adapter families other than `filesystem`
- runtime flavor expansion
- HOPS, SAMRAS, MSS, crypto, hosted, progeny, and advanced mediation work

The single proving end-to-end slice is `Shell Action To Local Audit`: normalize a canonical datum-ref, reduce shell state, persist a local-audit event via `audit_log` + filesystem adapter, and return the normalized runtime result. That slice is documented in [mvp_end_to_end_slice.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/mvp_end_to_end_slice.md).

Files created or updated:
- [mvp_boundary.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/mvp_boundary.md)
- [mvp_acceptance_criteria.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/mvp_acceptance_criteria.md)
- [mvp_out_of_scope.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/mvp_out_of_scope.md)
- [mvp_end_to_end_slice.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/mvp_end_to_end_slice.md)
- [decision_record_0009_mvp_boundary.md](/srv/repo/mycite-core/MyCiteV2/docs/decisions/decision_record_0009_mvp_boundary.md)
- [README.md](/srv/repo/mycite-core/MyCiteV2/README.md)
- [plans/README.md](/srv/repo/mycite-core/MyCiteV2/docs/plans/README.md)

Remaining ambiguities that should stay frozen for MVP are:
- whether hosted becomes a first-class domain
- whether progeny becomes a first-class domain
- whether `external_events` later stays separate from or merges with `local_audit`
- how `mediation_surface` expands beyond minimal shell-state work
- which tools, sandboxes, and runtime flavors come immediately after MVP

---

## CONSIDERATION & ASSSMENT

This is a good boundary.

It is materially better than a broader “first useful feature” MVP because it is now explicitly architecture-proving rather than feature-proving. That fits the current V2 scaffold, which defines V2 as documentation-first, authority-led, and explicitly not a partial port of V1  The boundary also follows the repo’s precedence model instead of inventing a parallel one, which is important because `authority_stack.md` already fixes how V2 decisions are supposed to resolve 

The strongest part is the chosen slice itself. The `Shell Action To Local Audit` path is narrow, coherent, and cleanly aligned with the structural invariants. It proves:

* one pure core concern
* one pure shell/state concern
* one explicit port
* one adapter family
* one runtime composition path
* one integration path
  without dragging in tools, sandboxes, domain breadth, or runtime-flavor expansion  

That is exactly the kind of MVP boundary you want when the goal is to validate dependency direction and prevent V1-style mixing. The current `mvp_boundary.md` is especially strong in three ways.

First, it selects `local_audit` as the cross-domain proving module rather than something more ambitious like contracts or reference exchange. That is the correct narrowing move. The document explicitly explains why this is the smallest coherent semantic surface and why it avoids pulling in broader policy and network complexity 

Second, it makes tools and sandboxes truly optional rather than conceptually “probably later in MVP.” That is a major improvement. The included module areas now clearly exclude all tools and all sandboxes, and the proving slice says they do not participate at all 

Third, it uses partial phase inclusion correctly. Instead of claiming “complete phases 02–10,” it identifies only the required outputs from included phases and explicitly defers the rest. That makes the MVP smaller and less likely to expand by accident  

So, from a workload perspective, this is the first point where the project becomes realistically executable in a small number of disciplined prompts.

The main caution is this:

This MVP proves architectural legitimacy, not product legitimacy.

That is not a flaw, but it is important to be conscious of it. The chosen slice validates that V2 can:

* normalize datum refs
* reduce serialized shell state
* use a real port
* persist through a real adapter
* compose one runtime path
* preserve import boundaries

What it does not yet prove is that V2’s more distinctive long-term structures—Hanus as a meaningful interface surface, HOPS/SAMRAS mediation, MSS, tool attachment, or sandbox orchestration—survive contact with implementation. That is acceptable for MVP, but only if you continue to treat this as an architecture MVP and not as evidence that higher-complexity slices are already safe.

The other thing I would specifically watch is whether the runtime path remains truly “shell-facing” and not quietly “route-shaped.” If the implementation of this MVP starts centering HTTP or framework concerns too early, the slice could accidentally prove adapter/runtime convenience more than shell composition. The repo’s invariants already warn against hosts owning domain logic, so keep that pressure high during implementation 

My judgment is:

This MVP boundary is appropriately narrow.
It is much less likely to drift.
It should reduce the prompt count meaningfully.
It is now small enough that future prompts can be operational instead of architectural.

If this boundary is held firm, you are probably no longer looking at 10 to 18 prompts for MVP. You are closer to about 5 to 8 disciplined prompts, because the slice excludes tools, sandboxes, domains, HOPS/SAMRAS, MSS, and multi-flavor runtime work. The biggest remaining risk is not scope size. It is accidental scope contamination during implementation.

---