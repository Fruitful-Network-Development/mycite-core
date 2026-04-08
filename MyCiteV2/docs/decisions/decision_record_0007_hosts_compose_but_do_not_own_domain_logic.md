# ADR 0007: Hosts Compose But Do Not Own Domain Logic

## Status

Accepted

## Context

V1 runtime wrappers and host surfaces carry too much semantic weight.

## Decision

Runtime composition in v2 lives under `instances/_shared/runtime/` and is limited to wiring inward layers together.

## Consequences

- Host code may mount routes, choose adapters, and compose tools.
- Host code may not redefine shell legality, datum truth, or domain rules.
- Instance-led layout must not become an architecture surface again.
