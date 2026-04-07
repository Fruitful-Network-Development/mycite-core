# Validity And Mutation

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [SAMRAS](README.md)

## Status

Canonical

## Parent Topic

[SAMRAS](README.md)

## Current Contract

A SAMRAS structure is valid only when its encoded fields decode correctly and the derived address space is structurally consistent.

Important validity conditions include:

- width fields decode correctly
- stop-count and stop-address array decode correctly
- stop addresses are strictly increasing and remain within the value stream
- value slicing yields no empty tokens
- breadth-first child-count decode consumes all tokens exactly
- roots and children are contiguous
- referenced addresses do not exceed the structure the value permits

Canonical mutation does not edit the raw magnitude directly. The required flow is:

1. decode the current structure
2. derive the canonical address tree
3. apply address-level mutation
4. revalidate continuity and structure
5. regenerate breadth-first child counts
6. regenerate stop addresses
7. regenerate the final canonical bitstream

This makes address rows derived, not independently authoritative.

## Boundaries

This page owns validity and mutation rules. It does not own:

- shell-level mutate affordances
- resource inventory indexes
- hosted or contract session logic
- historical JSON-only SAMRAS milestone UI behavior

## Authoritative Paths / Files

- `docs/shape_addressed_mixed-radix_address_space.md`
- `instances/_shared/portal/samras/validation.py`
- `instances/_shared/portal/samras/mutation.py`

## Source Docs

- `docs/shape_addressed_mixed-radix_address_space.md`
- `docs/SANDBOX_ENGINE.md`

## Update Triggers

- Changes to validity predicates
- Changes to mutation workflow or allowed operations
- Changes to round-trip enforcement
- Changes to derived-address versus stored-address policy
