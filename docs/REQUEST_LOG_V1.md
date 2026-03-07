# Request Log v1 (Dual-Mode)

## Status

- endpoint remains `POST /portal/api/request_log`
- log naming remains `request_log`
- v1 is additive; legacy payloads are still accepted

## Primary path

- `private/request_log/<msn_id>.ndjson`

## Typed fanout path

- `private/request_log/types/<type>.ndjson`

Typed fanout occurs only for v1-mode entries.

## v1 envelope

Required fields:

- `type`: string
- `transmitter`: string (`msn-...` or `alias-...`)
- `receiver`: string
- `event_datum`: datum ref (`<datum_address>` or `<msn_id>-<datum_address>`, normalized)
- `status`: datum ref ending with `-3-1-5` or `-3-1-6`

Optional fields:

- `details`: object

Auto-defaulted fields:

- `ts_unix_ms`: current epoch milliseconds
- `msn_id`: local portal msn id

## Normalization rules

- if `event_datum` is `<datum_address>`, normalize to `<local_msn_id>-<datum_address>`
- if already qualified numeric-hyphen token with datum-address tail, preserve
- reject malformed refs with `400` and field-level error strings

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

Each typed fanout line stores non-secret envelope fields plus details pointer data:

- `type`
- `event_datum`
- `status`
- `transmitter`
- `receiver`
- `ts_unix_ms`
- `msn_id`
- `details` (object)

## Implementation files

- `portals/mycite-le_fnd/portal/services/request_log_store.py`
- `portals/mycite-le_fnd/portal/api/request_log.py`
