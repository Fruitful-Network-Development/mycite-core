# Agro-ERP Workbench Contract

> **MOS-authority rule:** The Agro-ERP tool is a plain datum-workbench
> surface backed exclusively by the MOS authority database. See
> [`mos_authority_enforcement.md`](mos_authority_enforcement.md) for the
> binding storage-authority rule. No filesystem datum reads.

## Surface posture

| Field | Value |
|---|---|
| Tool id | `agro_erp` |
| Sandbox token | `agro_erp` (canonical, underscore form) |
| URL slug | `agro-erp` (hyphen form, route + display) |
| Surface id | `system.tools.agro_erp` |
| Route | `/portal/system/tools/agro-erp` |
| Tool kind | `general_tool` |
| Read-write posture | `write` |
| Applies-to source-kind | `("sandbox_source",)` |
| Manipulates datum kinds | `("sandbox_source",)` |
| Default workbench visible | `true` |
| Required capabilities | `("datum_recognition",)` |

## Available templates

| Template id | Archetype | Description |
|---|---|---|
| `agro_erp_taxonomy_source` | `agro_erp_taxonomy_row` | Repeating layer-4 value-group-2 rows; each row holds one taxonomy entry (node-address + ASCII title). |
| `product_profile` | `agro_erp_product_profile_row` | Repeating layer-4 value-group-2 rows; each row describes one product (SKU, name, optional taxonomy reference, unit-of-sale, description). |

Template files live in `MyCiteV2/data/datum_templates/` and are loaded
by `TemplateRegistry`. The unified workbench runtime
(`portal_workbench_ui_runtime`) surfaces templates whose `sandbox`
matches the resolved sandbox into the `new_source_document_form` slot
when the sandbox is writable.

## Row shape contract — `4-2-N` 4-tuple

The canonical agro_erp datum row shape (value-group-2 iteration N at
layer 4) is the 4-tuple:

```json
"4-2-N": [
  ["4-2-N", "rf.3-1-1", "<node_address>", "rf.3-1-2", "<title_binary>"],
  ["<title_ascii>"]
]
```

- `rf.3-1-1` resolves to the agro_erp anchor's
  `SAMRAS-babelette-txa_id` row (the taxonomy node-address space).
- `node_address` is a hyphen-form numeric path (e.g. `1-1-3-3-5-2`).
  It must address a node within the txa-SAMRAS magnitude declared at
  the anchor's `1-1-1` row.
- `rf.3-1-2` resolves to the anchor's `title-babelette` row.
- `title_binary` is the ASCII title encoded as 8 bits per character,
  right-padded with zeros to **512 bits** (per the anchor's
  `niu-baciloid-256-64` declaration: 64 base-256 digits = 64 ASCII
  bytes). The runtime composes this server-side from `title_ascii`.
- `title_ascii` is the plain human-readable title (UTF-8 ASCII subset,
  up to 64 chars).

Reference implementations:
- Encoder: `MyCiteV2/scripts/bootstrap_agro_erp_anchor.py`
  `_ascii_to_binary(title, width=512)`.
- Decoder (roundtrip): iterate 8-bit chunks, `chr(int(chunk, 2))`,
  stop at the first zero byte.

## User flow

### 1. Navigate to the workbench

`GET /portal/system/tools/agro-erp` returns the portal shell HTML.
The bootstrap shell request invokes the unified workbench runtime
(`portal_workbench_ui_runtime.build_portal_workbench_ui_bundle`) with
`sandbox="agro_erp"`. There is no longer a separate Agro-ERP-specific
bundle builder; the
`portal_agro_erp_runtime.build_portal_agro_erp_surface_bundle` shim
re-stamps the surface schema/route/entrypoint identifiers for
back-compat and delegates everything else to the unified workbench.
Per the doctrinal rule "modularization and reuse but different setting
of use" — the workbench is the modular code, the sandbox is the setting.

The unified workbench runtime:

1. Resolves the effective sandbox from
   `surface_query["sandbox_filter"]`, the explicit `sandbox` kwarg, the
   shell-state focus_path, or the default `WORKBENCH_UI_SANDBOX_TOKEN`.
2. Filters `workbench.document_collection.documents` to documents whose
   canonical id contains `.<sandbox>.` (the `system` sandbox is the
   reflective corpus-wide view and shows all documents).
3. Sets `read_write_posture` from `sandbox_is_writable(sandbox)` —
   `agro_erp` is writable; `system` stays read-only.
4. Emits a three-mode control panel (Docs / Datums / Author). The
   Author tab is hidden when the resolved sandbox is read-only.
5. Injects `surface_payload.new_source_document_form` +
   `surface_payload.new_datum_form` describing the scaffold and
   insert-datum affordances, and lifts both onto the control panel
   under `workbench_mode.author_forms` so the renderer can present
   inline forms under Author mode.

### 2. Create a new source document

The `new_source_document_form` slot carries:

```jsonc
{
  "schema": "mycite.v2.portal.workbench.new_source_document_form.v1",
  "sandbox_id": "agro_erp",
  "msn_id_default": "3-2-3-17-77-1-6-4-1-4",
  "available_templates": [
    {"template_id": "agro_erp_taxonomy_source", "label": "Agro Erp Taxonomy Source", "description": "...", "archetype": "agro_erp_taxonomy_row"},
    {"template_id": "product_profile", "label": "Product Profile", "description": "...", "archetype": "agro_erp_product_profile_row"}
  ],
  "name_input": {
    "field": "document_name",
    "label": "Document name",
    "placeholder": "e.g. crops_taxonomy",
    "pattern": "^[a-z][a-z0-9_]*$",
    "max_length": 64,
    "required": true
  },
  "endpoint_stage": "/portal/api/v2/mutations/stage",
  "endpoint_preview": "/portal/api/v2/mutations/preview",
  "endpoint_apply": "/portal/api/v2/mutations/apply"
}
```

The renderer presents a modal with a template-picker (single-select
from `available_templates`) and a name input (validated against the
`pattern`). On submit it POSTs the following payload three times
(stage → preview → apply):

```jsonc
{
  "target_authority": "datum_workbench",
  "sandbox_id": "agro_erp",
  "operation": "scaffold_datum",
  "template_id": "<selected>",
  "msn_id": "<msn_id_default>",
  "document_name": "<user input>",
  "canonical_name": "<user input>"
}
```

**Hash computation.** The backend `_scaffold_datum`
(`portal_datum_workbench_mutation_runtime.py:178`) hashes the
scaffolded document via `compute_mss_hash` and composes the canonical
id `lv.<msn_id>.agro_erp.<canonical_name>.<hash>`. The user never sees
or types a hash. Idempotent: re-applying with the same inputs yields
the same hash and the operation returns `status: "already_present"`.

### 3. Add taxonomy rows

For documents whose `document_metadata.datum_template_id ==
"agro_erp_taxonomy_source"` the renderer presents an "Add taxonomy
row" form (Phase 5 of the materialization plan). Fields:

- `node_address` — text input with autocomplete from the sibling
  `agro_erp.txa` document's known `4-2-N` node addresses
- `title_ascii` — text input (≤64 chars)

On submit the form composes the 4-tuple raw payload server-side via
`insert_datum` (operation auto-targets the next iteration in the
4-2 family) and runs the canonical stage→preview→apply pipeline.

## Enforcement

- `MyCiteV2/tests/integration/test_portal_agro_erp_routing.py` — the
  route resolves with the expected surface schema and the agro_erp
  documents are visible after the 2026-05-17 bootstrap.
- `MyCiteV2/tests/integration/test_portal_agro_erp_scaffold.py` —
  end-to-end scaffold produces a new MOS document with the template's
  header rows materialized.
- `MyCiteV2/tests/integration/test_portal_agro_erp_insert_datum.py` —
  insert_datum composes a 4-2-N 4-tuple and the binary title
  roundtrips back to the ASCII title.
- Architecture invariants from the 2026-05-17 audit
  (`test_no_disk_datum_authorities.py`,
  `test_no_filesystem_datum_authority_in_runtime.py`) continue to pass:
  no on-disk datum docs are added, no filesystem datum-store adapter
  imports are introduced.

## Cross-references

- [`mos_authority_enforcement.md`](mos_authority_enforcement.md) — the
  binding MOS-only rule
- [`datum_document_naming_taxonomy.md`](datum_document_naming_taxonomy.md)
  — canonical document id format
- [`samras_structural_model.md`](samras_structural_model.md) — the
  SAMRAS magnitude that the txa-SAMRAS row at anchor `1-1-1` encodes
- [`MyCiteV2/scripts/bootstrap_agro_erp_anchor.py`](../../MyCiteV2/scripts/bootstrap_agro_erp_anchor.py)
  — 2026-05-17 ingest script that seeded the anchor + txa documents

## Drift / open items

- Phase 5 (typed 4-tuple datum form) is the user-facing ergonomic
  polish. Until it lands, datum creation falls back to the generic
  YAML textarea (the user must hand-compose the 4-tuple raw payload).
- **product_profile anchor-extension (deferred).** The
  `product_profile` template currently only references the two
  babelettes the anchor defines: `rf.3-1-1` (taxonomy address) and
  `rf.3-1-2` (product name). The richer attributes (SKU, unit_of_sale,
  description) live in the interpreted-form list of each row and have
  no rf-anchor binding. A future task can extend
  `bootstrap_agro_erp_anchor.py` with `3-1-3` (sku-babelette), `3-1-4`
  (unit-of-sale-babelette), and `3-1-5` (description-babelette) — then
  update `data/datum_templates/product_profile.yaml` to reference them.
- The `documents` index table is updated lazily — the catalog
  snapshot is the runtime read path. A separate `documents`-table
  reconciliation runs via
  `MyCiteV2/scripts/migrate_to_canonical_document_ids.py` (or the
  per-sandbox bootstrap scripts).
