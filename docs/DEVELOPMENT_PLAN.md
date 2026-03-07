# Development Plan

## Current Baseline (March 2026)

### Active in-repo portal implementation

- `mycite-le_fnd`

### Archived portal instance sources

One-off and example portal instance sources are archived outside this repo at:

- `/srv/compose/portals/unused_portal_sources/2026-03-07-fnd-only/`

Archived folders:

- `mycite-le-example`
- `mycite-le_cvcc`
- `mycite-le_tff`
- `mycite-ne-example`
- `mycite-ne_dm`
- `mycite-ne_mt`
- `mycite-ne_mw`

## Architectural Direction

### 1) Service shell first

Primary user navigation remains service-based:

- `Home`
- `Data`
- `Network`
- `Tools`
- `Inbox`

### 2) Data service with right-margin NIMM summary

Data UI baseline:

- canonical route-driven tabs: `Anthology`, `Time Series`, `Geographic`
- Advanced NIMM is no longer a peer data tab in the main nav
- Advanced NIMM is shown as a right-side summary card
- Full advanced controls open in an overlay sidebar from that summary card

### 3) JSON-only prototype model

Current runtime constraints remain locked:

- anthology/conspectus/samras are JSON-only
- anthology compact rows preserve multi-pair entries
- `value_group == 0` rows deterministically recompute conspectus references
- first-pair compatibility fields (`reference`, `magnitude`) remain during transition

### 4) Time series abstraction

Time series remains anthology-backed:

- event anchor/index: `4-0-1`
- event rows: `4-1-*`
- event semantics: `start_unix_s` + `duration_s`
- API contract documented in `TIME_SERIES_ABSTRACTION.md`

### 5) Request log v1 dual-mode

- endpoint remains `/portal/api/request_log`
- legacy payloads remain accepted
- v1 payloads enforce normalized datum refs and status refs
- typed fanout logs write to `private/request_log/types/<type>.ndjson`

### 6) AWS emailer abstraction (preview + queue)

- tenant metadata refs in `profile_refs` select anthology-backed emailer abstractions
- FND preview endpoint resolves deterministic payloads from anthology (`/portal/api/aws/tenant/<tenant_id>/emailer_preview`)
- AWS proxy accepts queued `emailer_sync_preview` actions only (no direct SES send yet)

## Next Milestones

1. Stabilize NIMM overlay UX and reduce visual noise in advanced diagnostics.
2. Add automated API tests for time-series CRUD and request-log v1 validation.
3. Package FND-specific tools cleanly under service/tool boundaries.
4. Define explicit re-introduction rules if additional in-repo portal instances are needed later.
5. Formalize tenant-specific email format policies (`dns_wire_format` vs `text_byte_email_format`) before enabling outbound send.

## Canonical References

- [`TOOLS_SHELL.md`](TOOLS_SHELL.md)
- [`DATA_TOOL.md`](DATA_TOOL.md)
- [`TIME_SERIES_ABSTRACTION.md`](TIME_SERIES_ABSTRACTION.md)
- [`REQUEST_LOG_V1.md`](REQUEST_LOG_V1.md)
- [`AWS_EMAILER_ABSTRACTION.md`](AWS_EMAILER_ABSTRACTION.md)
- [`PROGENY_PROFILE_CARDS.md`](PROGENY_PROFILE_CARDS.md)
- [`request_log_and_contracts.md`](request_log_and_contracts.md)
