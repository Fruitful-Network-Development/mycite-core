# AGRO-ERP Tool (TFF)

## Purpose

AGRO-ERP is an optional portal tool that acts as an **agricultural data workbench** for the TFF portal. It provides a single entry point for property geometry, taxonomy, product types, and related data, using the portal’s anthology and (when applicable) inherited or public datum sources.

The tool’s full API contract is **not** finalized; it will evolve as the shared foundation (datum identity, public resolver, contract compact-array model) stabilizes and as more capabilities are added.

---

## Capability model

AGRO-ERP declares capabilities in a machine-readable registry:

- `portals/_shared/runtime/flavors/tff/portal/tools/agro_erp/capabilities.json`

The registry defines:

- accepted public resource families (for example `taxonomy.txa_collection`, `identity.msn_collection`)
- datum templates AGRO-ERP can create
- prerequisite abstraction chains per template
- auto-create rules for missing prerequisites

Tool-spec inputs/outputs and capability buckets are described in the tool spec (`private/tools/agro_erp.spec.json`) and in [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md). Storage bindings (e.g. layer/value_group for product types) are not frozen in the base anthology schema.

**Datum resolution:** When using inherited or contract-backed data (e.g. taxonomy), the tool should resolve datums via the **datum-identity layer** and **compiled compact-array index** (or **public_datum_resolver** for contact-card exports), not by raw MSS row order or storage addresses. Use canonical datum paths (`msn_id.datum_address`) for lookups and comparisons. See [CONTRACT_COMPACT_INDEX.md](CONTRACT_COMPACT_INDEX.md) and [CANONICAL_DATA_ENGINE.md](CANONICAL_DATA_ENGINE.md).

---

## Routes

- `GET /portal/tools/agro_erp/home`
- `GET /portal/tools/agro_erp/model.json`
- `GET /portal/tools/agro_erp/capabilities.json`
- `GET /portal/tools/agro_erp/resources` (thin delegate to canonical data API)
- `POST /portal/tools/agro_erp/plan_preview` (thin orchestration over canonical planner services)
- `POST /portal/tools/agro_erp/apply` (plan-first apply through canonical data mutation routes)
- `POST /portal/tools/agro_erp/daemon/resolve`
- `POST /portal/tools/agro_erp/product_types` — compatibility route delegating to planner-driven product-type apply.

Canonical core semantics remain on `/portal/api/data/*`:

- `/portal/api/data/external/resources`
- `/portal/api/data/write/field_contracts`
- `/portal/api/data/write/preview`
- `/portal/api/data/write/apply`
- `/portal/api/data/geometry/preview`
- `/portal/api/data/geometry/apply`
- external planner endpoints under `/portal/api/data/external/*` (used when template/resource family requires remote closure/materialization)

---

## Current capability: daemon and coordinate resolution

The tool defines two daemon entrypoints:

- `property_geometry` -> `property.geometry.coordinates`
- `property_bbox` -> `property.bbox`

Each daemon exposes a NIMM-style directive payload (`action`, `subject`, `method`, AITAS args) and resolves tokens to coordinate pairs. Resolution prefers canonical engine mediation (`daemon_resolve_tokens`) when available and falls back to local decoding.

**Coordinate decoding:** split fixed-width hex into equal upper/lower halves, interpret each half as signed two’s-complement, divide by `1e7`, map to `[longitude, latitude]`. Example: `CF69268F1894171F` -> `[-81.5192433000000, 41.2358431000000]`.

**Runtime inputs:** active private config (`private/config.json`), anthology payload (`data/anthology.json`). Taxonomy and product-type features also use tool spec and (when available) inherited taxonomy service and contracts.

---

## Planner preview and sparse materialization

Before apply, AGRO-ERP obtains and displays a structured write preview including:

- selected public resource and isolate/provenance context
- existing local prerequisites
- missing prerequisites
- prerequisites satisfiable from bundle
- prerequisites requiring auto-create
- ordered write actions from the shared write plan

AGRO-ERP then applies only shared write-pipeline-approved writes through canonical data-engine routes.

AGRO-ERP boundary in hardened write model:

- AGRO-ERP is a thin consumer of `/portal/api/data/write/*` and `/portal/api/data/geometry/*`
- shared contracts/templates in `field_contracts.py` and `geometry_datums.py` own datum-family semantics, prerequisites, and reuse policy
- AGRO-ERP may provide template selection and user inputs, but should not sequence low-level anthology mutations itself
- config/profile updates remain write-pipeline outputs, preserving anthology authority and ref-surface separation

## Local tool writes and audit

Product-type creation (and other local tool CRUD) is persisted via the data engine and recorded in the **local audit log** (`private/audit/tool_actions.ndjson`), not in the request log. The request log is reserved for external resource access and negotiation (see [AGRO_ERP_INTENTION.md](AGRO_ERP_INTENTION.md) and [REQUEST_LOG_V1.md](REQUEST_LOG_V1.md)).

---

## Enablement

Set in active private config:

```json
"enabled_tools": ["config_schema", "agro_erp"]
```
