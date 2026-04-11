# ADR 0002: No Direct Reuse Of V1 Package Structure

## Status

Accepted

## Context

V1 path names reflect drifted ownership mixes such as `mycite_core`, `packages/hosts`, and instance-led wrappers.

## Decision

V2 will not preserve v1 package layout as a template. V1 paths are inspected only to extract concepts, anti-patterns, and migration evidence.

## Consequences

- No direct `mycite_core` mirror is created in v2.
- No `packages/hosts/` mirror is created in v2.
- Migration docs must explain conceptual relocation rather than file copying.
