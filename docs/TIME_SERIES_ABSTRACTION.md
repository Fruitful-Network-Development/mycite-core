# Time Series Abstraction (FND First)

## Purpose

Define the JSON-only time series model without introducing a new table file.
Time series is an anthology+conspectus abstraction.

## Canonical anchors

- event index anchor datum: `4-0-1`
- event rows: `4-1-*`

Conspectus mirrors both forms of the anchor key:

- `4-0-1`
- `<msn_id>-4-0-1`

Both keys store ordered event refs in qualified form:

- `<msn_id>-4-1-<iter>`

## Event row contract

Event rows are anthology rows with exactly two semantic pairs for time-series APIs:

1. point pair
- `reference`: point datum ref (normalized)
- `magnitude`: `start_unix_s` (integer string)

2. duration pair
- `reference`: duration datum ref (normalized)
- `magnitude`: `duration_s` (integer string)

## Reference normalization

- input `3-2-2` -> `<local_msn_id>-3-2-2`
- input `<msn_id>-3-2-3` -> preserved
- malformed values -> validation error

## API endpoints

- `GET /portal/api/data/time_series/state`
- `POST /portal/api/data/time_series/ensure_base`
- `POST /portal/api/data/time_series/event/create`
- `POST /portal/api/data/time_series/event/update`
- `POST /portal/api/data/time_series/event/delete`
- `GET /portal/api/data/time_series/event/<event_ref>`
- `GET /portal/api/data/time_series/table/<table_id>/view?mode=normal|time_series`

## Behavior

`ensure_base`:

- ensures anthology contains `4-0-1`
- recomputes conspectus index keys (`4-0-1` and qualified key)
- idempotent

`event/create`:

- allocates next `4-1-<iter>`
- validates start/duration ints
- writes anthology and recomputes conspectus index

`event/update`:

- resolves event by internal or qualified ref
- updates point/duration refs and magnitudes
- recomputes conspectus index

`event/delete`:

- removes event row from anthology
- removes event ref from both conspectus index keys via recompute

`event/<event_ref>`:

- returns event payload
- returns reverse usage list (datums referencing that event)
- returns event-enabled table summaries

## UI scope in this milestone

Data tab `Time Series` provides:

- ensure base button
- create event form
- event list
- inspect panel with update/delete
- table mode toggle (normal/time_series) for event-enabled tables

`Geographic` tab is placeholder-only.

## Rollout note

Implemented first in `mycite-le_fnd` with shared-ready normalization patterns for later rollout to other runnable portals.
