# MOS Semantic Gate Register

Date: 2026-04-21

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Record the closure state for Track B from `docs/plans/master_plan_mos.md` so the SQL cutover and the native MOS semantic rules stay synchronized.

## Scope

In scope:

- `SG-1` version identity and MSS hashing policy
- `SG-2` hyphae derivation and stable semantic identity policy
- `SG-3` deterministic edit/remap algorithm for insert/delete/move
- `SG-4` native-standard closure criteria and compatibility retirement rules

Out of scope:

- Track C directive-context widening
- inventing new runtime surfaces outside the approved Track A seams

## Gate Ledger

### SG-1 — Version identity and MSS hashing policy

Status: `closed`

Closure artifact:

- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`

Implementation evidence:

- `MyCiteV2/packages/adapters/sql/datum_semantics.py`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
- `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

Closure summary:

- document version identity is now storage-derived through `mos.mss_sha256_v1`
- the SQL datum store persists `version_hash` plus the canonical MSS-equivalent input payload
- historical MSS assumptions remain compatibility-only unless equivalence is proven

### SG-2 — Hyphae derivation and stable semantic identity policy

Status: `closed`

Closure artifact:

- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`

Implementation evidence:

- `MyCiteV2/packages/adapters/sql/datum_semantics.py`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
- `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

Closure summary:

- stable semantic identity is now distinct from storage address
- the canonical hyphae chain includes local dependency closure plus the required `0-0-*` rudi prefix
- the SQL datum store persists semantic hashes and hyphae chains per row

### SG-3 — Deterministic edit/remap algorithm

Status: `closed`

Closure artifact:

- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`

Implementation evidence:

- `MyCiteV2/packages/adapters/sql/datum_semantics.py`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
- `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

Closure summary:

- canonical insert/delete/move rules now exist behind the SQL datum-store adapter
- deletion refuses live-reference targets instead of guessing semantic replacements
- successful apply operations re-store the authoritative catalog and refresh version/hyphae identities

### SG-4 — Native-standard closure and compatibility retirement rules

Status: `closed`

Closure artifact:

- `docs/plans/mos_sg4_standard_closure_policy_2026-04-21.md`

Implementation evidence:

- `docs/plans/master_plan_mos.md`
- `docs/plans/master_plan_mos.index.yaml`
- `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md`
- `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md`
- `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md`

Closure summary:

- native MOS closure criteria are now explicit
- compatibility retirement is staged as detect, freeze, migrate, retire
- Track C remains non-blocking for Track B semantic closure

## Validation Rules

1. Every closed gate must retain its dedicated closure artifact.
2. If implementation diverges from a closure artifact, `docs/plans/master_plan_mos.md` must be updated before the gate may remain closed.
3. Compatibility retirement may proceed only in the order defined by `SG-4`.

## Exit Criteria

- all four semantic gates remain closed with active evidence
- the master plan no longer treats Track B semantics as unresolved
- compatibility retirement is decision-complete even when individual compatibility paths remain intentionally retained
