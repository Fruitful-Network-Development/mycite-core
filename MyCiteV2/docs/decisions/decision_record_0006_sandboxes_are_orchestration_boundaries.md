# ADR 0006: Sandboxes Are Orchestration Boundaries

## Status

Accepted

## Context

V1 mixes sandbox machinery with domain and runtime concerns.

## Decision

V2 gives sandboxes their own top-level package and defines them as orchestration boundaries only.

## Consequences

- `packages/sandboxes/` is separate from `packages/modules/`.
- Sandboxes may coordinate staging, mediation, and derived-artifact handling.
- Sandboxes may not own contract, publication, or reference-exchange semantics.
