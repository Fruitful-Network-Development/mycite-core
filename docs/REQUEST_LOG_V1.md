# Request Log v1 (Dual-Mode)

## Status

- endpoint remains `POST /portal/api/request_log`
- canonical log naming remains `request_log`
- v1 is additive; legacy payloads are still accepted

## Boundary model

- public anonymous surface: `GET /<msn_id>.json`
- portal-authenticated surface: `/portal/**`
- signed machine-to-machine surface: `/api/**`

## Storage paths

- primary append-only log: `private/request_log/<msn_id>.ndjson`
- typed fanout logs: `private/request_log/types/<type>.ndjson`

Typed fanout occurs only for v1-mode entries.

## v1 envelope

Required fields:

- `type`: string
- `transmitter`: string (`msn-...` or `alias-...`)
- `receiver`: string
- `event_datum`: datum ref (`<datum_address>`, `<msn_id>-<datum_address>`, or `<msn_id>.<datum_address>`)
- `status`: datum ref ending in `3-1-5` or `3-1-6`

Optional fields:

- `details`: object

Auto-defaulted fields:

- `ts_unix_ms`: current epoch milliseconds
- `msn_id`: local portal msn id

## Normalization rules

- datum refs are dual-read (`local`, hyphen-qualified, dot-qualified)
- canonical write format is dot-qualified (`<msn_id>.<datum_address>`)
- malformed refs return `400` with field-level error messages

## Security rules

Do not persist these key types in request logs:

- `private_key*`
- `secret`
- `token`
- `password`
- `hmac_key*`
- `api_key`
- `symmetric_key*`

## Typed supplemental payload

Each typed fanout line stores non-secret v1 envelope fields:

- `type`
- `event_datum`
- `status`
- `transmitter`
- `receiver`
- `ts_unix_ms`
- `msn_id`
- `details` (object)

## Implementation files

- `portals/_shared/portal/services/request_log_store.py`
- `portals/mycite-le_fnd/portal/api/request_log.py`
