# AGRO-ERP MVP Validation Report

> **Status: Historical MVP validation snapshot (non-canonical).**
> Use `AGRO_ERP_TOOL.md` and `SANDBOX_ENGINE.md` for current behavior.

## Live-State Gate (FND state snapshot)

State checked against:

- `compose/portals/state/fnd_portal/data/anthology.json`
- `compose/portals/state/fnd_portal/data/sandbox/resources/*.json`

Result:

- `isolated_resource_files_exist`: **PASS**
  - txa resource ids: `["txa.samras.5-0-1"]`
  - msn resource ids: `["msn.samras.5-0-2"]`
- `anthology_owns_no_full_txa_tree`: **PASS**
  - `4-1-*` rows absent
  - selector rows `5-0-1` / `5-0-2` absent from anthology
- `txa_resource_ids_known`: **PASS**
  - committed MVP txa id: `txa.samras.5-0-1`
- `product_invoice_reads_ok_after_migration`: **PASS**
  - inherited refs can be read from config surface (empty or canonical refs)
- `no_hidden_local_txa_subtree_dependency`: **PASS**
  - no detected config/profile dependency on `4-1-*` subtree

## Live-Like FND MVP Workflow Validation

Validation method:

- temp copy of live-like FND `data/` (anthology + sandbox resources)
- compile isolated txa resource
- compile inherited txa context
- preview/apply `inherited_product_profile_ref` and `inherited_supply_log_ref`
- verify read/write invariants

Resource used:

- `sandbox:txa.samras.5-0-1`

Result:

- txa compile: **PASS**
- txa inherited-context compile: **PASS**
- product preview/apply: **PASS**
  - `created_count: 0`, `reused_count: 1`
- invoice preview/apply: **PASS**
  - `created_count: 0`, `reused_count: 1`
- no local anthology materialization calls: **PASS**
  - `rows_created_calls: 0`
- no `4-1-*` subtree introduced: **PASS**
- config ref readback updates: **PASS**
  - product: `3-2-3-17-77-1-6-4-1-4.8-5-11`
  - invoice: `3-2-3-17-77-1-6-4-1-4.8-4-11`

## MVP Completion Checklist

- Resource tab visualization: **complete**
- Product create from inherited txa context: **complete**
- Invoice create from inherited txa context: **complete**
- Shared preview/apply flow usage: **complete**
- Readback contract (`items[]`, `summary`, sort, empty state): **complete**
- No-materialization invariant (`4-1-*` absent): **complete**
- Local + external-origin parity path: **complete** (adapter + endpoint tests)

## Deferred (Post-MVP)

- Auto-selection reliability when txa resource has no `8-5-*`/`8-4-*` typed bindings
  - current behavior: explicit inherited-ref override path available
- msn inherited write workflows
