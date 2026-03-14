# AGRO-ERP Tool (TFF)

## Purpose

AGRO-ERP is an optional portal tool that acts as an **agricultural data workbench** for the TFF portal. It provides a single entry point for property geometry, taxonomy, product types, and related data, using the portal’s anthology and (when applicable) inherited or public datum sources.

The tool’s full API contract is **not** finalized; it will evolve as the shared foundation (datum identity, public resolver, contract compact-array model) stabilizes and as more capabilities are added.

---

## Capability buckets

- **Current**
  - Property geometry: resolve coordinate tokens (config hex or anthology-backed) via daemon; decode fixed-width hex to lon/lat.
- **Planned**
  - Inherited taxonomy: view and use taxonomy data from FND (or other portals) via contract or public contact-card exported metadata.
  - Product types: define and save product-type datums (e.g. `txa_id`, `title`, `gestation_time`) to the local anthology.
  - Field records, crop references, and related agricultural entities (to be specified later).

Tool-spec inputs/outputs and capability buckets are described in the tool spec (`private/tools/agro_erp.spec.json`) and in [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md). Storage bindings (e.g. layer/value_group for product types) are not frozen in the base anthology schema.

**Datum resolution:** When using inherited or contract-backed data (e.g. taxonomy), the tool should resolve datums via the **datum-identity layer** and **compiled compact-array index** (or **public_datum_resolver** for contact-card exports), not by raw MSS row order or storage addresses. Use canonical datum paths (`msn_id.datum_address`) for lookups and comparisons. See [CONTRACT_COMPACT_INDEX.md](CONTRACT_COMPACT_INDEX.md) and [CANONICAL_DATA_ENGINE.md](CANONICAL_DATA_ENGINE.md).

---

## Routes

- `GET /portal/tools/agro_erp/home`
- `GET /portal/tools/agro_erp/model.json`
- `POST /portal/tools/agro_erp/daemon/resolve`
- `POST /portal/tools/agro_erp/product_types` — create a product-type datum (persisted to anthology; audit via local audit log, not request log).

---

## Current capability: daemon and coordinate resolution

The tool defines two daemon entrypoints:

- `property_geometry` -> `property.geometry.coordinates`
- `property_bbox` -> `property.bbox`

Each daemon exposes a NIMM-style directive payload (`action`, `subject`, `method`, AITAS args) and resolves tokens to coordinate pairs. Resolution prefers canonical engine mediation (`daemon_resolve_tokens`) when available and falls back to local decoding.

**Coordinate decoding:** split fixed-width hex into equal upper/lower halves, interpret each half as signed two’s-complement, divide by `1e7`, map to `[longitude, latitude]`. Example: `CF69268F1894171F` -> `[-81.5192433000000, 41.2358431000000]`.

**Runtime inputs:** active private config (`private/config.json`), anthology payload (`data/anthology.json`). Taxonomy and product-type features also use tool spec and (when available) inherited taxonomy service and contracts.

---

## Local tool writes and audit

Product-type creation (and other local tool CRUD) is persisted via the data engine and recorded in the **local audit log** (`private/audit/tool_actions.ndjson`), not in the request log. The request log is reserved for external resource access and negotiation (see [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md) and [REQUEST_LOG_V1.md](REQUEST_LOG_V1.md)).

---

## Enablement

Set in active private config:

```json
"enabled_tools": ["config_schema", "agro_erp"]
```
