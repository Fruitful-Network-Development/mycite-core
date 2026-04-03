# Contract Context Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Contracts And MSS](README.md)

## Status

Canonical

## Parent Topic

[Contracts And MSS](README.md)

## Current Contract

`NETWORK > Contracts` is the canonical contract editor. Contracts carry the shared MSS context needed to understand foreign datum references without transferring a full anthology.

Canonical contract context fields are:

- `owner_selected_refs`
- `owner_mss`
- `counterparty_mss`

Local behavior:

- `owner_selected_refs` is the editable local source
- `owner_mss` is the compiled local compact array when refs are present
- `counterparty_mss` is stored remote context and is read-only in the editor

Resolution behavior:

- local `<msn_id>.<datum>` refs resolve from the local anthology
- foreign `<msn_id>.<datum>` refs resolve through the matching contract MSS context

The NETWORK page remains the canonical contract editing surface. Data Tool and other surfaces may help users inspect or choose local datums, but they do not replace the contract editor.

## Boundaries

This page owns contract context semantics. It does not own:

- low-level compact-array encoding details
- compiled index shape in depth
- revisioned external update messages
- local sandbox resource inventory

## Authoritative Paths / Files

- `docs/NETWORK_PAGE_MODEL.md`
- `docs/MSS_CONTRACT_CONTEXT_STATUS.md`
- `docs/MSS_COMPACT_ARRAY_SPEC.md`

## Source Docs

- `docs/NETWORK_PAGE_MODEL.md`
- `docs/MSS_CONTRACT_CONTEXT_STATUS.md`
- `docs/MSS_COMPACT_ARRAY_SPEC.md`
- `docs/DATA_TOOL.md`

## Update Triggers

- Changes to contract payload fields
- Changes to how local and foreign refs resolve
- Changes to the canonical editor surface
- Changes to local recompilation behavior when anthology changes
