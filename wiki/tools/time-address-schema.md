# Time Address Schema

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical (staged)

## Current Contract

Time-address schema authority for AGRO chronological mediation is read from tool sandbox anchor datum `1-1-1` (`UTC_mixed_radix`) in the AGRO tool anchor file (`tool.*.agro-erp.json`).

This schema is **not** a SAMRAS node map. It is a fixed mixed-radix denotation structure.

## Encoding Model

The `1-1-1` magnitude is encoded as a binary payload:

1. unary stop-index width (`0...01`)
2. unary denotation-count width (`0...01`)
3. denotation count (fixed width)
4. stop-index array (cumulative exclusive boundaries)
5. concatenated denotation binaries

Decoder behavior:

- reads width headers
- reads denotation count
- slices concatenated payload by stop indexes
- reconstructs ordered denotation values

Example decoded denotations from current staged magnitude:

- `14`
- `1000`
- `1000`
- `365`
- `60`
- `60`

## Semantics

- The decoded value defines the address-space schema, not specific time entries.
- Addresses remain human-readable mixed-radix strings.
- Omitted trailing segments reduce specificity rather than changing structure.
- Engine/core owns decode/validation/normalization.
- UI owns selection interaction only.

## Validation Policy (Current)

- Schema decode is required for authority metadata.
- Address validation currently enforces prefix-compatible bounds and schema-mode checks.
- When schema shape is narrower than full interactive address depth, validation degrades to controlled prefix-only mode with explicit warnings.

## Authoritative Paths / Files

- `portals/_shared/portal/application/time_address_schema.py`
- `portals/_shared/portal/application/time_address.py`
- `portals/_shared/runtime/flavors/tff/portal/tools/agro_erp/__init__.py`
- `compose/portals/state/tff_portal/private/utilities/tools/agro-erp/tool.*.agro-erp.json`

## Update Triggers

- Changes to `1-1-1` magnitude format
- Changes to decode/validation policy
- Changes to AGRO chronological selection depth
