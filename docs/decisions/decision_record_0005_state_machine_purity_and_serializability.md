# ADR 0005: State Machine Purity And Serializability

## Status

Accepted

## Context

Hanus, AITAS, and NIMM only remain legible if state is explicit and serializable rather than hidden in UI code or runtime wrappers.

## Decision

State-machine truth in v2 must be pure, serializable, and independent of adapters, tools, and hosts.

## Consequences

- `mediation_surface` belongs under `packages/state_machine/`.
- Navigation legality must not depend on runtime imports.
- Shell state can be inspected, tested, and rebuilt deterministically.
