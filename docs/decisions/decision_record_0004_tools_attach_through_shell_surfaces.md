# ADR 0004: Tools Attach Through Shell Surfaces

## Status

Accepted

## Context

V1 planning repeatedly states that the shell surface is primary and tools attach through it.

## Decision

Tools in v2 may consume shell-defined context and mediation surfaces, but they may not define shell-state authority or invent alternate shell models.

## Consequences

- `packages/tools/` depends on `packages/state_machine/`, not the reverse.
- Tool capability is distinct from shell ownership.
- Tool routing and host mounting remain later-layer concerns.
