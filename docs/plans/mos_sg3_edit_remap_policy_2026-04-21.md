# MOS SG-3 Deterministic Edit and Remap Policy

Date: 2026-04-21

Doc type: `policy`  
Normativity: `supporting`  
Lifecycle: `historical-superseded`  
Last reviewed: `2026-04-22`

## Purpose

Close `SG-3` from `docs/plans/master_plan_mos.md` by defining the deterministic insert, delete, and move/remap rules for authoritative datum documents.

## Canonical Write Surface

1. Mutation applies only to canonical authoritative document rows.
2. Every occupied `(layer, value_group)` family must already be contiguous before mutation.
3. Auto-remapped same-document references are limited to:
   - exact local datum addresses
   - dot-qualified refs
4. `rf.<anchor_address>` markers are never rewritten by this policy.
5. Hyphen-qualified local refs are `compatibility_only` and mutation-ineligible because they are ambiguous against non-reference numeric-hyphen payload values.

## Insert

1. The caller supplies the final target datum address.
2. Every row in the same `(layer, value_group)` family with `iteration >= target_iteration` shifts up by `+1`.
3. The inserted row is normalized through the same remap table so that references authored against the pre-insert layout are rewritten into the final post-insert layout.

## Delete

1. Deletion is allowed only when the target row is not referenced by any other local row.
2. Every row in the same `(layer, value_group)` family with `iteration > target_iteration` shifts down by `-1`.
3. References to shifted rows are rewritten through the final address map.
4. The policy intentionally refuses to guess a replacement semantic target for live references to the deleted row.

## Move

1. The caller supplies the final destination datum address.
2. The move is executed as:
   - remove source row
   - compact the source family
   - expand the destination family
   - rewrite all remappable references using the final old-to-new map
3. The moved row keeps its row payload but receives the destination datum address and rewritten local references.

## Readiness and Evidence Rules

1. Preview and apply must produce the same address map.
2. Every apply result must surface `version_hash_before` and `version_hash_after`.
3. SQL persistence must re-store the document through the authoritative catalog path so semantic identity and version identity stay synchronized.

## SQL Implementation

- `MyCiteV2/packages/adapters/sql/datum_semantics.py`
  - `preview_document_insert(...)`
  - `preview_document_delete(...)`
  - `preview_document_move(...)`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
  - `preview_document_insert(...)`
  - `apply_document_insert(...)`
  - `preview_document_delete(...)`
  - `apply_document_delete(...)`
  - `preview_document_move(...)`
  - `apply_document_move(...)`

## Evidence

- code: `MyCiteV2/packages/adapters/sql/datum_semantics.py`
- code: `MyCiteV2/packages/adapters/sql/datum_store.py`
- tests: `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`

## Closure Statement

`SG-3` is closed for current repo truth because the canonical write surface, the refusal behavior for unsafe deletes, the deterministic remap rules, and the regression evidence are now explicit.
