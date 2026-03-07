# Data Tool (JSON-Only Prototype Contract)

This document defines the active Data service contract for the JSON-only prototype phase.

## Scope

- FND is the first implementation target in this milestone.
- Runtime model is still JSON-only (no DB for anthology/conspectus/samras).
- Contract is structured for rollout to other runnable portals after FND validation.

## Data service routes

- `GET /portal/data` -> redirects to `GET /portal/data/anthology`
- `GET /portal/data/anthology`
- `GET /portal/data/time-series`
- `GET /portal/data/geographic`
- `GET /portal/data/advanced` (legacy-compatible route that opens Advanced NIMM overlay)

Tab state is URL-driven and not query-param driven.
Advanced NIMM controls are summarized in the right-side margin and expanded in an overlay sidebar.

## JSON runtime artifacts

Canonical runtime JSON artifacts are per-portal state files:

- `data/demo-anthology.json`
- `data/demo-conspectus.json`
- `data/demo-SAMRAS_MSN.json`
- `data/presentation/datum_icons.json`
- `private/daemon_state/data_workspace.json`

## Anthology abstraction exports (AWS)

FND tenant AWS tooling can resolve anthology-backed emailer abstractions from tenant metadata refs:

- list anchor example: `10-0-1` (`emailer_list`)
- entry rows example: `9-2-*`

Preview endpoint:

- `GET /portal/api/aws/tenant/<tenant_id>/emailer_preview`

See [AWS_EMAILER_ABSTRACTION.md](AWS_EMAILER_ABSTRACTION.md) for payload contract and format semantics.

## Anthology compact row contract

Persisted anthology compact rows keep the existing array form:

```json
"11-3-1": [["11-3-1", "ref1", "mag1", "ref2", "mag2"], ["label"]]
```

Rules:

- first token is identifier
- remaining tokens are alternating `reference, magnitude`
- odd trailing token is invalid and dropped with warning

Normalized runtime/API row shape includes:

- `row_id`, `identifier`, `label`
- `pairs` (full list)
- `pair_count`
- compatibility fields: `reference`, `magnitude` (first pair)

## Value-group behavior

- `value_group == 0`
  - row is conspectus-linked
  - `magnitude` is fixed to `0` for pair normalization
  - conspectus is derived from the row's references
- `value_group >= 1`
  - one datum row may contain multiple reference/magnitude pairs

## Time Series abstraction (anthology-backed)

Time Series uses anthology+conspectus, not a new table file.

- event index anchor row: `4-0-1`
- event rows: `4-1-*`
- event refs in index are NIMM directives:
  - `inv;(med;<msn_id>-4-0-1;event_value);<row_number>`
- index keys maintained in conspectus:
  - internal: `4-0-1`
  - qualified: `<msn_id>-4-0-1`
- `4-0-1` also defines allowed event-value refs (minimum expected refs: `3-2-2`, `3-2-3`)

Event pair semantics are fixed:

1. pair 1: `point_ref` + `start_unix_s`
2. pair 2: `duration_ref` + `duration_s`

Validation:

- `start_unix_s >= 0`
- `duration_s >= 1`
- refs are normalized to `<msn_id>-<datum_address>`
- `point_ref` and `duration_ref` must be present in the `4-0-1` event-value collection

## Data API contract

Anthology endpoints:

- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/append`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/anthology/delete`

Time Series endpoints:

- `GET /portal/api/data/time_series/state`
- `POST /portal/api/data/time_series/ensure_base`
- `POST /portal/api/data/time_series/event/create`
- `POST /portal/api/data/time_series/event/update`
- `POST /portal/api/data/time_series/event/delete`
- `GET /portal/api/data/time_series/event/<event_ref>`
- `GET /portal/api/data/time_series/table/<table_id>/view?mode=normal|time_series`

## Geographic tab status

`/portal/data/geographic` is intentionally placeholder-only in this milestone.
No mutation actions are exposed there yet.

## Module ownership

- workspace logic: `portals/mycite-le_fnd/data/engine/workspace.py`
- API adapters: `portals/mycite-le_fnd/portal/api/data_workspace.py`
- JSON storage adapter: `portals/mycite-le_fnd/data/storage_json.py`
- shared compact-pair helper: `portals/_shared/portal/data_contract/anthology_pairs.py`

UI remains a consumer of API contracts; it does not directly mutate JSON files.
