# Homogeneous Ordinal Partition Structure (HOPS)

## Purpose

This page defines the canonical HOPS interpretation used by CTS-GIS for
chronological and geospatial address tokens.

HOPS provides:

- deterministic partitioning for coordinate-like streams
- stable ordinal addressing semantics across repeated encode/decode operations
- compatibility with SAMRAS adjunct context rows that preserve time-scoped
  collection references

## Chronological Addressing Context

For chronological CTS-GIS adjunct usage, HOPS is carried as a binary payload
bound through anchor-space rows (for example `1-1-5`, `2-0-4`, `3-1-5` when
present).

Contract expectations:

- the payload is treated as canonical encoded state, not an interpreted calendar
  label at storage time
- CTS-GIS mediation may receive caller-provided `time` context and preserve it in
  runtime metadata
- navigation semantics (`attention_node_id`, `intention_token`) remain independent
  of chronological context

## Geospatial Addressing Context

CTS-GIS profile source documents encode coordinates via HOPS tokens bound through
`rf.3-1-1` references in `4-*` rows.

Core invariants:

- decode order follows row token order exactly
- deterministic encode of the same input coordinates yields the same token stream
- ring closure is runtime-only and is not stored by duplicating the first point in
  row payloads

## Relationship To SAMRAS

SAMRAS defines structural navigation authority. HOPS provides encoded payload
carriers used by CTS-GIS for geometry and adjunct context.

This means:

- SAMRAS chooses where the user is in the hierarchy
- HOPS rows provide the encoded values projected or interpreted for that scope
- adjunct `time` context can annotate profile selection/provenance without changing
  structural lineage traversal
