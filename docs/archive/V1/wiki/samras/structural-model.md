# Structural Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [SAMRAS](README.md)

## Status

Canonical

## Parent Topic

[SAMRAS](README.md)

## Current Contract

SAMRAS is a shape-addressed mixed-radix address space represented as a structural value.

The structure defines a tree or forest of nodes. Nodes do not store their full addresses directly. Instead:

1. the structure stores child counts
2. those counts are interpreted in breadth-first order
3. addresses are derived from ordinal child position

Boundary reminder:

- SAMRAS structural addresses are not anthology/resource datum addresses.
- SAMRAS addresses are also not MSS compact-array row indexes.
- Similar decode mechanics do not imply shared identity semantics.

The governing structural value is encoded as five parts:

1. `address_width_field`
2. `stop_count_width_field`
3. `stop_count_field`
4. `stop_address_array`
5. `value_stream`

Decoded values are interpreted so that:

- the first value is the root count
- each later value is the child count for the next node in breadth-first order

The canonical human-facing model is:

- edit addresses and nodes
- let the engine regenerate structure
- persist the rebuilt canonical magnitude

The governing SAMRAS structure datum is the layer-1 datum created in reference to `0-0-5`.

## Boundaries

This page owns the structural model. It does not own:

- UI layout for any specific page
- resource inventory ownership
- NETWORK contract context
- build-spec seeding

## Authoritative Paths / Files

- `docs/shape_addressed_mixed-radix_address_space.md`
- `instances/_shared/portal/samras/structure.py`
- `instances/_shared/portal/samras/codec.py`

## Source Docs

- `docs/shape_addressed_mixed-radix_address_space.md`
- `docs/SANDBOX_ENGINE.md`
- `docs/CANONICAL_DATA_ENGINE.md`

## Update Triggers

- Changes to the encoded field layout
- Changes to breadth-first interpretation rules
- Changes to the governing reference for SAMRAS structure datums
- Changes to the engine-facing decoded structure model
