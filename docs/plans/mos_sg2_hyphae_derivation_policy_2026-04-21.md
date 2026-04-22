# MOS SG-2 Hyphae Derivation and Stable Semantic Identity Policy

Date: 2026-04-21

Doc type: `policy`  
Normativity: `supporting`  
Lifecycle: `completed`  
Last reviewed: `2026-04-22`

## Purpose

Close `SG-2` from `docs/plans/master_plan_mos.md` by defining the canonical hyphae-derivation algorithm and the stable semantic-identity boundary for datum rows.

## Canonical Policy

1. A row `hyphae_hash` is **semantic-derived**, not storage-derived.
2. Stable semantic identity is computed against an **anchor context** plus a **local dependency closure**.
3. The anchor context hash is derived from:
   - supporting anchor-document metadata
   - supporting anchor rows numerically sorted by datum address
4. Local dependencies are discovered from canonical row shapes only:
   - exact local datum addresses `<layer>-<value_group>-<iteration>`
   - dot-qualified refs `<msn_id>.<layer>-<value_group>-<iteration>`
5. `rf.<anchor_address>` markers are anchor-contract references, not mutable local row addresses.
6. The canonical row semantic hash is computed recursively by:
   - replacing the row’s own datum address with `__self__`
   - replacing local datum references with the referenced rows’ semantic hashes
   - including the anchor-context hash in the normalized payload
7. The canonical hyphae chain for a target row is:
   - the transitive closure of local dependencies in dependency order
   - plus the required `0-0-*` rudi prefix rows from `0-0-1` through the highest reachable `0-0-n`
8. The canonical hyphae policy identifier is `mos.hyphae_chain_v1`.
9. The persisted `hyphae_hash` is `sha256:<hex>` over:
   - anchor-context hash
   - target row semantic hash
   - ordered chain semantic hashes

## Identity Boundary

- Datum addresses remain valid local storage coordinates and projection/debug handles.
- Datum addresses are **not** the stable semantic identity.
- The stored hyphae chain may retain datum addresses for traceability, but the hash authority is semantic-hash ordered, not address-ordered by itself.

## SQL Implementation

- `MyCiteV2/packages/adapters/sql/_sqlite.py`
  - adds `datum_row_semantics`
- `MyCiteV2/packages/adapters/sql/datum_semantics.py`
  - `build_document_semantics(...)`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
  - persists row semantic identity on `store_authoritative_catalog(...)`
  - exposes `read_datum_semantic_identity(...)`

## Evidence

- code: `MyCiteV2/packages/adapters/sql/datum_semantics.py`
- code: `MyCiteV2/packages/adapters/sql/datum_store.py`
- tests: `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

## Closure Statement

`SG-2` is closed for current repo truth because the hyphae derivation path, the rudi-prefix rule, the semantic-versus-storage distinction, and the SQL persistence model are now explicit and tested.
