# ADR 0003: Dependency Direction, Ports, And Adapters

## Status

Accepted

## Context

V1 shows reusable logic importing runtime helpers and portal-specific code directly.

## Decision

V2 uses explicit inward dependency flow. Ports define external seams. Adapters implement ports. Inward layers must not import outward layers.

## Consequences

- Port interfaces exist as explicit contracts, not as implied helper imports.
- Adapters remain replaceable.
- Import-boundary checks become mandatory.
