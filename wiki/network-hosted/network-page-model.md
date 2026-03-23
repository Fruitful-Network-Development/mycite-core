# Network Page Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Network And Hosted](README.md)

## Status

Canonical

## Parent Topic

[Network And Hosted](README.md)

## Current Contract

`/portal/network` is the canonical workbench page for portal-to-portal metadata, request logs, hosted views, profile editing, and contract context.

Canonical tabs are:

- `Messages`
- `Hosted`
- `Profile`
- `Contracts`

`NETWORK > Contracts` is the canonical contract editor.

`NETWORK > Profile` uses shared datum-backed write intents:

- field contracts from `/portal/api/data/write/field_contracts`
- preview via `/portal/api/data/write/preview`
- apply via `/portal/api/data/write/apply`

Network APIs continue to group trust posture into:

- `anonymous`
- `asymmetric`
- `symmetric`

Asymmetric verification remains the canonical ingress trust boundary.

## Boundaries

This page owns the NETWORK surface and its current tabs. It does not own:

- low-level MSS encoding
- compiled datum index internals
- hosted template derivation in depth
- local data-engine daemon semantics outside NETWORK usage

## Authoritative Paths / Files

- `docs/NETWORK_PAGE_MODEL.md`
- shared network and contract code under `portals/_shared/portal/**`

## Source Docs

- `docs/NETWORK_PAGE_MODEL.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/MSS_COMPACT_ARRAY_SPEC.md`

## Update Triggers

- Changes to canonical NETWORK tabs or routes
- Changes to profile-edit write integration
- Changes to trust-qualifier handling
- Changes to where contract editing is canonically performed
