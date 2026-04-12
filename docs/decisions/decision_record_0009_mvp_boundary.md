# ADR 0009: MVP Boundary

## Status

Accepted

## Context

MyCiteV2 needs a real proving slice, but broad partial coverage would recreate v1 drift and dilute the architecture check.

## Decision

The MVP is the `Shell Action To Local Audit` slice documented in:

- [../plans/v2-mvp_boundary.md](../plans/v2-mvp_boundary.md)
- [../plans/v2-mvp_acceptance_criteria.md](../plans/v2-mvp_acceptance_criteria.md)
- [../plans/v2-mvp_out_of_scope.md](../plans/v2-mvp_out_of_scope.md)
- [../plans/v2-mvp_end_to_end_slice.md](../plans/v2-mvp_end_to_end_slice.md)

The slice includes:

- `packages/core/datum_refs`
- minimal `packages/state_machine` work for AITAS, NIMM, and Hanus shell state reduction
- `packages/ports/audit_log`
- `packages/modules/cross_domain/local_audit`
- `packages/adapters/filesystem`
- one minimal runtime composition path under `instances/_shared/runtime`
- integration and architecture-boundary checks for that slice

The slice excludes:

- all tools
- all sandboxes
- all domain modules
- `external_events`
- multiple adapters
- multiple runtime paths or flavors

## Consequences

- MVP work proves dependency direction rather than breadth.
- Sandboxes and tools are not prerequisites for the first architectural proof.
- Runtime composition remains minimal and shell-facing.
- The next slice after MVP must be chosen explicitly rather than leaking in through convenience.
