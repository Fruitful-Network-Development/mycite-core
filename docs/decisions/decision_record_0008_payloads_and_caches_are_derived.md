# ADR 0008: Payloads And Caches Are Derived

## Status

Accepted

## Context

V1 tool and data handling repeatedly needed correction around datum truth versus payloads and caches.

## Decision

Payload binaries and caches are always derived artifacts in v2. They must never become the authority source for domain or datum semantics.

## Consequences

- Derived outputs may be regenerated.
- Human-authored datum truth must remain explicit and fail-closed.
- Architecture checks must flag attempts to promote derived outputs into truth.
