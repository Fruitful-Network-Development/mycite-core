# Contract Compact Array — Compiled Datum Index

This document describes the **compiled datum index** view of a contract’s compact array. The index is keyed by **canonical datum path** (semantic identity), not by storage order, so recompilation or iteration changes do not break identity.

See also: [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md), [MSS_COMPACT_ARRAY_SPEC.md](MSS_COMPACT_ARRAY_SPEC.md).

---

## Purpose

- Treat the contract’s compact array as a **compiled snapshot** with a stable, identity-keyed view.
- **Datum path = semantic identity**; `layer/value_group/iteration` in the snapshot = storage address within that snapshot.
- When one portal updates or adds datums, the compact array can be recompiled and the index rebuilt; consumers look up by datum path, not by position.

---

## Index shape (intended)

A compiled datum index derived from a contract has the following structure:

| Field | Description |
|-------|-------------|
| `contract_id` | Contract identifier. |
| `relationship_mode` | `unilateral_local` \| `mirrored_shared` \| `negotiated_shared`. |
| `authority_mode` | Optional; who may update (owner, counterparty, both). |
| `access_mode` | `public` \| `contract` \| `private`. |
| `source_msn_id` | MSN that authored this snapshot (owner or counterparty). |
| `target_msn_id` | MSN this snapshot is for (counterparty or owner). |
| `revision` | Monotonic revision for this snapshot. |
| `compiled_at_unix_ms` | When the snapshot was compiled. |
| `source_card_revision` | Optional; contact-card or source revision if applicable. |
| `entries` | Map from **canonical datum path** to entry (see below). |

---

## Entry shape (keyed by datum path)

Each key in `entries` is a **canonical datum path** (`msn_id.datum_address`). Each value:

| Field | Description |
|-------|-------------|
| `datum_path` | Canonical path (same as key). |
| `scope` | e.g. local, foreign, public. |
| `access` | Access level for this datum. |
| `source_kind` | e.g. anthology, mss, public_export. |
| `source_ref` | Optional source reference. |
| `display_title` | Optional label for UI. |
| `magnitude_hint` | Optional type or unit hint. |
| `mediation_hint` | Optional mediation key. |
| `updated_unix_ms` | When this entry was last updated. |
| `revision` | Entry-level revision if needed. |
| `storage_address` | Row id in the snapshot (`layer-value_group-iteration`). |
| `semantic_address` | Source datum address when present (for example decoded `source_identifier`). |
| `row` | Optional full row payload for convenience. |

Recompilation may change `storage_address` or order; the key (`datum_path`) remains the stable identity. `semantic_address` should be used when available to preserve source identity across isolated reindexing.

---

## Relationship and sync modes (intended)

- **relationship_mode**
  - `unilateral_local`: only the referencing portal stores the contract.
  - `mirrored_shared`: both portals store compatible copies.
  - `negotiated_shared`: both store and coordinate updates (e.g. via update protocol).

- **sync_mode**
  - `none`: no sync.
  - `pull_refresh`: consumer may pull refreshed snapshot.
  - `push_notified`: consumer is notified when snapshot changes.
  - `negotiated`: updates follow the contract update protocol.

These belong in the contract schema so behavior is explicit. They are optional so existing contracts remain valid.

---

## Compilation

- The index is **compiled** from the contract’s MSS (decode `owner_mss` or `counterparty_mss`) and optional metadata (contract_id, source_msn_id, etc.).
- Rows from the decoded MSS are turned into entries keyed by **canonical datum path** (using the source MSN so that `layer-value_group-iteration` is interpreted in the correct scope).
- The data-engine module `datum_identity.compile_compact_array_entries_keyed_by_path` can build the entry map from a list of decoded rows and `source_msn_id`.

---

## Usage

- **Resolution**: To resolve a canonical datum path against a contract, look up `entries[datum_path]` in the compiled index. If present, the datum is in that snapshot; `storage_address` or `row` gives the snapshot-local row.
- **Updates**: When the compact array is updated (recompile, add/remove entries), bump `revision` and `compiled_at_unix_ms` and rebuild `entries`. Update protocol messages reference `from_revision` and `to_revision`; the request log carries update evidence for external updates.

---

## Relation to MSS bitstring

The MSS bitstring (`owner_mss` / `counterparty_mss`) remains the wire and storage form. The compiled index is a **derived view** for identity-keyed lookup and for the update protocol. Compilation is one-way: index ← decode(MSS) + metadata.
