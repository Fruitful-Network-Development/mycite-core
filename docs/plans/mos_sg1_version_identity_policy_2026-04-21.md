# MOS SG-1 Version Identity and MSS Hashing Policy

Date: 2026-04-21

Doc type: `policy`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Close `SG-1` from `docs/plans/master_plan_mos.md` by defining the canonical version-identity policy for authoritative datum documents and the SQL-backed storage rules for persisting that identity.

## Canonical Policy

1. A document `version_hash` is **storage-derived**, not semantic-derived.
2. The canonical hash input is the **MSS-equivalent JSON projection** of one datum document:
   - `source_kind`
   - `document_metadata`
   - ordered datum rows, numerically sorted by `layer-value_group-iteration`
   - each row represented only as `datum_address` plus canonical `raw`
3. The hash input does **not** include:
   - `document_id`
   - relative path or filename
   - runtime-only fields
   - anchor rows from supporting documents
4. The canonical hash policy identifier is `mos.mss_sha256_v1`.
5. The persisted hash string format is `sha256:<hex>`.
6. Historical MSS forms remain `compatibility_only` unless they prove equivalence to the `mos.mss_sha256_v1` canonical input. A historical bitstream or filename convention is not canonical for write authority by itself.

## SQL Implementation

- `MyCiteV2/packages/adapters/sql/_sqlite.py`
  - adds `datum_document_semantics`
- `MyCiteV2/packages/adapters/sql/datum_semantics.py`
  - `build_document_version_identity(...)`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
  - persists document version identity on `store_authoritative_catalog(...)`
  - exposes `read_document_version_identity(...)`

## Operational Notes

- The policy intentionally uses a repo-native canonical projection rather than claiming a historical bitstream implementation that is not present in the current codebase.
- This keeps SQL-side version identity deterministic now while leaving room for a future byte-level MSS encoder to prove equivalence instead of silently replacing the policy.

## Evidence

- code: `MyCiteV2/packages/adapters/sql/datum_semantics.py`
- code: `MyCiteV2/packages/adapters/sql/datum_store.py`
- tests: `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

## Closure Statement

`SG-1` is closed for current repo truth because the version-identity boundary, canonical input, compatibility posture, storage schema, and regression evidence are now explicit.
