# MVP Boundary

## Purpose

Define the smallest coherent MyCiteV2 MVP that proves the architecture is real, coherent, and testable without widening scope toward the eventual full system.

## Authority and source precedence

This MVP boundary is subordinate to the existing v2 authority order in [authority_stack.md](authority_stack.md).

Source precedence for MVP decisions is:

1. [../ontology/structural_invariants.md](../ontology/structural_invariants.md)
2. [../decisions/](../decisions/)
3. [phases/](phases/) and [phase_completion_definition.md](phase_completion_definition.md)
4. [v1-migration/](v1-migration/)
5. `../../../docs/plans/*.md` from v1
6. v1 code as evidence only

This document does not redefine the authority stack. It chooses the smallest proving slice inside it.

## Recommended MVP statement

The MyCiteV2 MVP is a single shell-facing runtime path that accepts a serialized shell action over a canonical datum-ref subject, reduces that action through pure AITAS/NIMM/Hanus state logic, persists one redacted local-audit record through an `audit_log` port backed by a filesystem adapter, and returns a normalized runtime result containing the new shell state and persisted audit metadata.

The MVP proves:

- pure core recreation is usable
- pure shell/state recreation is usable
- one explicit port and one adapter family are usable
- one narrow cross-domain module is usable
- one runtime composition path is usable
- architecture boundary checks are enforceable

## Why this is the narrowest coherent MVP

This slice is narrower than a contracts slice, reference-exchange slice, publication slice, tool slice, or sandbox slice because:

- it requires no domain breadth beyond one narrow cross-domain module
- it avoids v1 drift around mixed tool and shell ownership
- it avoids v1 drift around sandbox semantics
- it avoids premature runtime breadth such as multiple flavors or UI surfaces
- it still proves the complete dependency direction from `core` to `state_machine` to `ports` to `adapters` to `instances/_shared/runtime`

The recommended cross-domain owner is `local_audit`, not `external_events`, because `local_audit` has the smallest coherent behavior surface, the fewest semantic prerequisites, and the least pressure to pull in network, request-log, or externally-meaningful-event policy.

## Mandatory architecture pillars

The MVP must validate all of these pillars:

1. one pure core module is recreated and actually used
2. shell state is pure, serializable, and independent of tools and hosts
3. one explicit port replaces direct runtime-path imports
4. one recreated module owns semantics without becoming a broad service bucket
5. one adapter family implements that port without absorbing semantics
6. one runtime composition path wires the inward layers together
7. one end-to-end integration path executes successfully
8. architecture-boundary checks fail the known v1 drift patterns

## Included phase outputs

### Included phases

- Phase 02
- Phase 03
- Phase 04
- Phase 05
- Phase 06
- Phase 09
- Phase 10

### Mandatory outputs by included phase

#### Phase 02

- `packages/core/datum_refs/` only
- pure datum-ref normalization and validation contracts
- unit tests proving deterministic behavior

Deferred from phase 02:

- `packages/core/identities/`
- `packages/core/structures/`
- `packages/core/mss/`
- `packages/core/crypto/`

#### Phase 03

- minimal `packages/state_machine/aitas/`
- minimal `packages/state_machine/nimm/`
- minimal `packages/state_machine/hanus_shell/`
- serialized shell action, shell state, reducer, and normalized runtime-facing shell result

Deferred from phase 03:

- `packages/state_machine/mediation_surface/`
- richer mediation projection behavior
- advanced time, archetype, and spatial projection semantics

#### Phase 04

- `packages/ports/audit_log/` only
- explicit append/read contract for local audit persistence

Deferred from phase 04:

- `payload_store`
- `event_log`
- `resource_resolution`
- `session_keys`
- `time_projection`
- `shell_surface`
- `datum_store`

#### Phase 05

- `packages/modules/cross_domain/local_audit/` only
- narrow local-audit semantic rules, including secret-key rejection and normalized record policy

Deferred from phase 05:

- all `packages/modules/domains/*`
- `packages/modules/cross_domain/external_events/`

#### Phase 06

- `packages/adapters/filesystem/` only, implementing `audit_log`

Deferred from phase 06:

- `event_transport`
- `session_vault`
- `portal_runtime`

#### Phase 09

- one minimal runtime composition path under `instances/_shared/runtime/`
- no multiple flavors
- no tool wiring
- no sandbox wiring

Deferred from phase 09:

- flavor-specific runtime trees
- route families beyond the one proving path
- any hosted or progeny runtime composition

#### Phase 10

- one end-to-end integration test for the chosen slice
- architecture-boundary checks covering included modules

Deferred from phase 10:

- full-system integration
- tool-loop integration
- sandbox-loop integration

## Included module areas

### `packages/core`

Included:

- `datum_refs`

Excluded:

- `identities`
- `structures/samras`
- `structures/hops`
- `mss`
- `crypto`

### `packages/state_machine`

Included:

- `aitas`
- `nimm`
- `hanus_shell`

Excluded:

- `mediation_surface`

### `packages/ports`

Included:

- `audit_log`

Excluded:

- `datum_store`
- `payload_store`
- `event_log`
- `resource_resolution`
- `session_keys`
- `time_projection`
- `shell_surface`

### `packages/modules/domains`

Included:

- none

Excluded:

- `contracts`
- `publication`
- `reference_exchange`

### `packages/modules/cross_domain`

Included:

- `local_audit`

Excluded:

- `external_events`

### `packages/adapters`

Included:

- `filesystem`

Excluded:

- `event_transport`
- `session_vault`
- `portal_runtime`

### `packages/tools`

Included:

- none

Excluded:

- all tool packages
- `_shared` implementation work beyond inert scaffolding

### `packages/sandboxes`

Included:

- none

Excluded:

- all sandbox implementation work

### `instances/_shared/runtime`

Included:

- one minimal shell-facing runtime composition path for the chosen slice

Excluded:

- flavor expansion
- tool runtime composition
- sandbox runtime composition
- hosted/progeny runtime composition

## Chosen end-to-end slice

The single proving slice is:

1. input a serialized shell action that focuses a canonical datum-ref subject and sets a shell verb
2. normalize the datum ref through `packages/core/datum_refs`
3. reduce the shell action through `packages/state_machine`
4. pass a normalized audit event to `packages/modules/cross_domain/local_audit`
5. persist and read it through the `packages/ports/audit_log` contract and `packages/adapters/filesystem`
6. return one normalized runtime result containing:
   - normalized shell state
   - normalized attention subject
   - accepted shell verb
   - persisted local-audit metadata

No tools, no sandboxes, no external events, and no multi-flavor runtime behavior participate in the slice.

## Minimum required tests

- pure unit loop
  - datum-ref normalization and failure behavior
  - local-audit redaction and record normalization
- state machine loop
  - shell action normalization
  - attention/intention/directive serialization
  - reducer behavior for focus and verb changes
- port/contract loop
  - `audit_log` append/read contract behavior
- adapter loop
  - filesystem adapter conformance to `audit_log`
- integration loop
  - one runtime composition test for the full proving slice
- architecture boundary loop
  - no outward imports from included inward layers
  - no instance-path leakage
  - no tool ownership
  - no sandbox ownership
  - no runtime-path helper reuse

## Explicitly deferred work

- all domain modules
- `external_events`
- all tools
- all sandboxes
- all advanced mediation-surface work
- HOPS and SAMRAS recreation
- MSS recreation
- crypto/session-vault split implementation
- multiple adapters
- multiple runtime flavors
- hosted and progeny decisions
- publication, contracts, and reference-exchange behavior
- tool and sandbox integration loops

## Frozen decisions for MVP

These questions must stay frozen rather than solved during MVP work:

- whether hosted becomes a first-class domain
- whether progeny becomes a first-class domain
- whether `external_events` later merges with or stays separate from `local_audit`
- how `mediation_surface` is expanded beyond minimal shell-state work
- which tools are implemented first after MVP
- how sandbox orchestration is partitioned later
- which runtime flavors exist beyond the single proving path

## Completion rule

The MVP is complete only when the chosen slice works end to end and every included layer is proven at its own boundary without requiring any tool, sandbox, domain module, or secondary adapter.

If the slice only works because runtime composition, adapter code, or tests compensate for missing inward contracts, MVP is not complete.

## Follow-on work after MVP

The first follow-on steps after MVP are:

1. expand `packages/core` only as needed by the next chosen slice
2. add the next explicit port set
3. choose either one domain slice or one tool slice, not both at once
4. defer sandboxes until a chosen slice actually requires orchestration boundaries
