# Request Log and Contracts (Canonical)

This is the active contract for request logging and contract-related audit behavior.

## Boundary model

- public anonymous surface: `GET /<msn_id>.json`
- portal-only authenticated surface: `/portal/**`
- signed machine-to-machine surface: `/api/**`

## Request log stores

Primary append-only log:

- `private/request_log/<msn_id>.ndjson`

Typed supplemental logs:

- `private/request_log/types/<type>.ndjson`

Contract metadata (non-secret only):

- `private/contracts/contract-<contract_id>.json`

## Storage rules

- NDJSON append-only writes
- one JSON object per line
- no secret material in log entries
- forbidden examples: private keys, passwords, API tokens, symmetric key material

## Request log API

- `POST /portal/api/request_log`

The endpoint is dual-mode:

- legacy payloads remain accepted
- v1 payload validation/normalization is applied when v1 fields are present

## Request log v1 fields

Required in v1 mode:

- `type`
- `transmitter`
- `receiver`
- `event_datum`
- `status`

Defaulted if missing:

- `ts_unix_ms`
- `msn_id`

Optional:

- `details` (object)

Validation:

- `event_datum` normalized to `<msn_id>-<datum_address>` when given as `<datum_address>`
- `status` must reference `...-3-1-5` or `...-3-1-6`
- `transmitter` must start with `msn-` or `alias-`

When v1 mode is used, a typed supplemental entry is also written to:

- `private/request_log/types/<type>.ndjson`

## Event linkage intent

`event_datum` should point to time-series event datums (`4-1-*` qualified refs) when available.
This keeps request-log entries correlated to the same event timeline abstraction used by Data.

## Contract lifecycle summary

- offer/proposal recorded as metadata (non-secret)
- signed transmission received and logged
- accept/decline events appended as audit entries
- secret handling remains outside repo-tracked JSON

## Current implementation files

- API route: `portals/mycite-le_fnd/portal/api/request_log.py`
- store/validation: `portals/mycite-le_fnd/portal/services/request_log_store.py`

See also:

- `docs/REQUEST_LOG_V1.md`
- `docs/TIME_SERIES_ABSTRACTION.md`
