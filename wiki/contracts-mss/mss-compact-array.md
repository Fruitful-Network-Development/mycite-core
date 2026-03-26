# MSS Compact Array

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Contracts And MSS](README.md)

## Status

Canonical

## Parent Topic

[Contracts And MSS](README.md)

## Current Contract

MSS is the compact-array form used to carry a scoped anthology context between portals without exposing a full `anthology.json`.

Canonical contract fields are:

- `owner_selected_refs`
- `owner_mss`
- `counterparty_mss`

Canonical local editing flow is:

1. select local datum refs
2. compile the isolated closure required to interpret them
3. write the compiled raw bitstring to `owner_mss`
4. use the matching contract context to resolve foreign refs

Key compact-array rules:

- rows are compiled from the transitive local reference closure of `owner_selected_refs`
- rows are reindexed into an isolated anthology ordered by `layer -> value_group -> iteration`
- multi-selection compiles add a synthetic selection-root row
- references are rewritten to the isolated anthology identifiers
- COBM is used between layers so reference width is determinable

Boundary reminder:

- MSS row/index order is transport-local to the isolated closure.
- It must not be used as a substitute for anthology/resource datum-address ordering policy.
- Anthology/resource key ordering remains numeric by `<layer>-<value_group>-<iteration>`.

Current decoder and writer behavior supports:

- `canonical_v2` as the active write target
- prior `canonical` payloads as dual-read compatibility
- archived fixture support as decode-only compatibility

## Boundaries

This page owns compact-array semantics and wire behavior. It does not own:

- revision messaging for external updates
- hosted or alias session behavior
- shell-level contract editor UI details beyond its role as the canonical editor

## Authoritative Paths / Files

- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/MSS_CONTRACT_CONTEXT_STATUS.md`
- `portals/_shared/portal/mss/`

## Source Docs

- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/MSS_CONTRACT_CONTEXT_STATUS.md`
- `docs/NETWORK_PAGE_MODEL.md`

## Update Triggers

- Changes to compact-array writer or decoder semantics
- Changes to `canonical_v2` or compatibility read support
- Changes to closure, selection-root, or COBM rules
- Changes to which contract fields are authoritative for local compilation
