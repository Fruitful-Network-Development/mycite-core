# Canonical Data Engine

## Canonical source

Portal data runtime is file-backed.

Canonical browser entry for the Data Tool is `/portal/data` (redirect target `/portal/tools/data_tool/home`), while `/portal/api/data/*` remains the canonical data-service API surface.

Canonical data API route registration is shared-core owned in `portals/_shared/portal/api/data_workspace.py`; flavor runtimes compose it and do not maintain divergent registrars.

External public-resource acquisition and isolate planning are shared-core services under `portals/_shared/portal/data_engine/external_resources/`. Public-resource flows are isolate/provenance-driven and distinct from relationship-scoped contract MSS context.

Canonical datum-native write intents are shared-core services under `portals/_shared/portal/data_engine/write_pipeline.py`, `field_contracts.py`, `profile_config_refs.py`, and `geometry_datums.py`.

Anthology loading uses a base+overlay merge model:

- base registry: repo `anthology-base.json`
- portal overlay: `data/anthology.json` in each portal state
- merged runtime view produced in shared core (`anthology_registry.py`, `anthology_overlay.py`, `anthology_schema.py`)

Canonical data artifacts:

- `data/anthology.json`
- `data/samras-txa.json`
- `data/samras-msn.json`
- `data/resources/local/*.json`
- `data/resources/inherited/<source_msn_id>/*.json`
- `data/resources/index.local.json`
- `data/resources/index.inherited.json`
- `data/presentation/datum_icons.json`
- request logs and hosted/network metadata under `private/network/**`

Repo `build.json` files may seed contract/network data, but anthology content remains state-owned and is not overwritten by materialization.

For the current `SYSTEM` page, the canonical file-focused workbench surface is the root-level trio:

- `anthology.json`
- `samras-txa.json`
- `samras-msn.json`

The `resources/*` registries remain engine-owned inventory and compatibility artifacts. They are not advertised as separate current `SYSTEM` tabs.

## Datum and mediation model

Canonical datum ordering remains:

1. layer
2. value group
3. iteration

Shared helpers:

- anthology normalization: `portals/_shared/portal/data_engine/anthology_normalization.py`
- mediation registry: `portals/_shared/portal/mediation/registry.py`
- MSS contract context: `docs/MSS_COMPACT_ARRAY_SPEC.md`

## Resolution order (canonical datum identity)

Datum resolution must use **canonical datum paths** (semantic identity), not storage addresses or raw MSS row order. The canonical resolution order is:

1. **Local anthology** — `datum_identity.resolve_to_local_row` with the portal’s anthology rows.
2. **Local projection/cache** — any cached or projected view keyed by canonical path.
3. **Compiled compact-array snapshot** — contract’s compiled index (`build_compiled_index` / `entries[datum_path]`); use `datum_identity.resolve_to_contract_entry` or look up by path in the index.
4. **Public contact-card export** — `public_datum_resolver` using contact-card exported datum metadata (no contract required).
5. **Remote fetch / negotiated contract** — out-of-band or future sync.

Implementations must use `datum_identity.parse_datum_path` / `to_canonical_dot` for normalization and `datum_paths_equivalent` for comparison. Do not compare datums by row address or MSS bit offset. See `portals/_shared/portal/data_engine/datum_identity.py`, `portals/_shared/portal/services/public_datum_resolver.py`, and CONTRACT_COMPACT_INDEX.md.

See also: `docs/EXTERNAL_RESOURCE_ISOLATES.md`.

## Reference model

Canonical network-facing datum refs:

- `<msn_id>.<datum>`

Compatibility policy:

- local refs remain readable
- legacy hyphen-qualified refs remain readable
- new network-facing writes use dot-qualified refs

## Daemon ownership

Daemon resolution remains owned by the Data Engine.

Canonical Data Engine daemon routes:

- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`
- `POST /portal/api/data/daemon/resolve_tokens`

These routes are retained for Data Tool and tool-package usage. NETWORK foreign datum resolution does not use a separate daemon wrapper; it resolves through contract MSS context.

## Unified SYSTEM workbench surface

Shared-core also owns the canonical route surface for the unified `SYSTEM` workbench:

- `POST /portal/api/data/system/selection_context`
- `GET /portal/api/data/system/resource_workbench`
- `POST /portal/api/data/system/mutate`
- `POST /portal/api/data/system/publish`

These routes expose one NIMM/AITAS-aware workbench model over the three canonical files. Legacy `local_resources`, `inheritance`, `workbench=anthology`, and `workbench=resources` entrypoints are compatibility aliases only.

## Shared write pipeline

UI and tool flows that perform semantic writes should use shared preview/apply routes (instead of calling low-level append directly):

- `GET /portal/api/data/write/field_contracts`
- `POST /portal/api/data/write/preview`
- `POST /portal/api/data/write/apply`
- `POST /portal/api/data/geometry/preview`
- `POST /portal/api/data/geometry/apply`

Write-intent hardening baseline:

- field contracts are engine-owned semantics (datum family, constraint family, allowed write modes, target ref-surface path, and required inputs), not just UI metadata
- geometry/property templates define required inputs, prerequisite refs, parent/child intent, and duplicate policy (`reuse_if_local_ref_exists`)
- preview/apply canonicalize write targets to semantic dot refs (`<msn_id>.<datum>`) and keep config/profile JSON as a ref surface
- apply is deterministic: ordered writes are preserved, local reuse actions are explicit, and mutation summaries separate created vs reused refs
- `contract_mss_sync` remains an engine side effect of anthology mutations; write pipeline surfaces it but does not own MSS policy

Low-level primitives still exist and remain engine-owned:

- `POST /portal/api/data/anthology/append`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/anthology/delete`

Config/profile JSON remains a reference surface into anthology datums; anthology remains the local semantic authority.

Within the unified `SYSTEM` workbench, anthology rows continue to use the direct anthology authority path, while TXA/MSN rows use staged mutate/publish behavior.

## Anthology base + overlay

Shared-core anthology modules:

- `portals/_shared/portal/data_engine/anthology_schema.py`
- `portals/_shared/portal/data_engine/anthology_registry.py`
- `portals/_shared/portal/data_engine/anthology_overlay.py`

Key rules:

- base registry rows are canonical reserved datums
- portal anthologies store local overlay rows and explicit local overrides
- runtime merge order is base first, overlay second
- merge output remains compact-row compatible for existing runtime consumers
- icon metadata stays in `data/presentation/datum_icons.json` sidecar

Migration route:

- `POST /portal/api/data/anthology/overlay/migration` (`apply=false|true`) for duplicate-base-row stripping in local overlays

Merged anthology canonical seam:

- `build_canonical_anthology_context(...)` (`portals/_shared/portal/data_engine/anthology_context.py`)
- consumed by AITAS inspect/trace/bindings, sandbox txa inherited compiler, and write preview/apply local-ref existence checks

## Shared sandbox engine

Shared core now exposes a sandbox service layer under `portals/_shared/portal/sandbox/` as the canonical integration boundary for:

- MSS form compile/decode/edit staging (`SandboxEngine.compile_mss_resource`, `decode_mss_resource`)
- MSS compact-array decode/context payloads (same service boundary as MSS form compile/decode)
- SAMRAS resource lifecycle delegation (`SandboxEngine` / route surfaces) backed by the canonical SAMRAS package under `portals/_shared/portal/samras/`
- contact-card exposed resource value generation (`SandboxEngine.generate_contact_card_public_resources`)
- inherited resource context resolution for local and foreign refs (`SandboxEngine.resolve_inherited_resource_context`)

Route surface is shared-core under `/portal/api/data/sandbox/*` (registered in `portals/_shared/portal/api/data_workspace.py`). The current `SYSTEM` page consumes sandbox and inherited-resource capabilities through the unified workbench. Older `local_resources` and `inheritance` views remain compatibility-only entrypoints.

SAMRAS hardening contract:

- canonical structural values are layer-1 values in reference to `0-0-5`
- the semantic owner is `portals/_shared/portal/samras/`
- addresses are derived from decoded structure; they are not independently authoritative
- mutation flows must decode -> derive -> mutate -> re-encode before persistence
- generic `SYSTEM` raw row creation/update for `samras-txa.json` and `samras-msn.json` is blocked; structure-aware SAMRAS actions are required instead

Resource inventory ownership is separate from sandbox:

- resource registry/index layer: `portals/_shared/portal/data_engine/resource_registry.py`
- inherited subscription/sync layer: `portals/_shared/portal/data_engine/inherited_contract_resources.py`
- user-facing inventory routes:
  - `GET /portal/api/data/resources/local`
  - `GET /portal/api/data/resources/inherited`
  - `GET /portal/api/data/resources/inherited/subscriptions`
  - `POST /portal/api/data/resources/local/migrate_legacy_samras`
  - `POST /portal/api/data/resources/inherited/refresh`
  - `POST /portal/api/data/resources/inherited/refresh_source`
  - `POST /portal/api/data/resources/inherited/disconnect_source`

Migration boundary:

- Full SAMRAS payload rows are migrated to sandbox-managed isolated resource JSONs (for FND: `txa.samras.5-0-1`, `msn.samras.5-0-2`)
- anthology does not retain full txa/msn resource trees after extraction
- migration helper is `migrate_fnd_samras_rows_to_sandbox(...)`; it supports dry-run and apply modes

AGRO inherited-write MVP consumes published txa resource context from sandbox and stages inherited refs through shared write preview/apply. No full `4-1-*` txa subtree should be re-materialized into anthology during these flows.

## Property/polygon workspace resolution

Shared property workspace mediation is implemented in `portals/_shared/portal/data_engine/property_workspace.py`.

Current behavior:

- resolves `config.property[]` entries against merged anthology rows (`rows_by_id`)
- decodes coordinate tokens through shared mediation (`coordinate_fixed_hex`)
- emits normalized parcel records (`polygon`, `bbox_summary`, `focus_hint`, validity/warnings)
- AGRO plan routes consume this resolver output; route/template layers do not own coordinate-decoding semantics

## Runtime validation commands

Use a Flask-capable Python environment for route suites. Example from repo root:

- `python3 -m venv .venv`
- `.venv/bin/pip install flask cryptography`
- `PYTHONPATH="/srv/repo/mycite-core/portals:/srv/repo/mycite-core/portals/_shared/runtime/flavors/tff" .venv/bin/python -m unittest tests/test_data_write_pipeline_routes.py tests/test_agro_erp_tool_flow.py`
- `.venv/bin/python -m unittest tests/test_data_write_pipeline_routes.py tests/test_sandbox_engine.py`
- `.venv/bin/python -m unittest tests/test_anthology_registry_overlay.py`

Pure engine-only write tests (no Flask requirement):

- `python3 -m unittest tests/test_write_pipeline_engine.py`

## AITAS context foundation

Shared core now includes an AITAS context foundation under:

- `portals/_shared/portal/data_engine/aitas_context.py`
- `portals/_shared/portal/data_engine/archetypes.py`

Current implemented facet is **Archetype** only. Initial anchor definition:

- `ascii_babel_64`

Archetype recognition is derived from anthology-resolved chain + compiled constraint context. It is not authoritative storage and does not replace datum identity or contract MSS logic.

Shared routes:

- `GET /portal/api/data/aitas/archetypes`
- `POST /portal/api/data/aitas/archetype/inspect`
- `POST /portal/api/data/aitas/archetype/trace`
- `GET /portal/api/data/aitas/archetype/bindings`

See `docs/AITAS_CONTEXT_MODEL.md` for details.

## MSS contract sync boundary

The Data Engine is responsible for keeping anthology-derived contract context coherent after anthology mutations.

Current rule:

- after anthology compaction and VG0 synchronization, recompile `owner_mss` for local contracts with non-empty `owner_selected_refs`
- do not rewrite manual `owner_mss` values when no `owner_selected_refs` are stored

Current mutation surfaces covered:

- anthology append
- anthology delete
- anthology profile update
- time-series mutations that write anthology rows

## Storage boundary

There is no portal application database in this runtime. Portal data, hosted metadata, request logs, progeny profiles, vault state, and workbench state remain JSON/ndjson/file backed.
