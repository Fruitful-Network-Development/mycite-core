# Development Plan

## Current Baseline (March 2026)

### Active in-repo runnable portals

- `mycite-le_fnd`
- `mycite-le_cvcc`
- `mycite-ne_mw`
- `mycite-ne_mt`
- `mycite-le_tff`

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

- canonical route-driven tabs: `Anthology`, `SAMRAS`, `Time Series`, `Geographic`
- Advanced NIMM is no longer a peer data tab in the main nav
- Advanced NIMM is shown as a right-side summary card
- Full advanced controls open in an overlay sidebar from that summary card

SAMRAS specifics:

- instance files auto-discovered by pattern `data/<msn_id>.<instance_id>.json`
- two-column editor contract: `address_id`, `title`
- right-side horizontal hierarchy view with collapse/expand (default depth 2)
- new table creation writes anthology linkage through `1-0-1` via directive refs

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

- member metadata refs in `profile_refs` select anthology-backed emailer abstractions
- canonical FND preview endpoint resolves deterministic payloads from anthology (`/portal/api/aws/member/<member_id>/emailer_preview`)
- legacy compatibility endpoint remains available (`/portal/api/aws/tenant/<tenant_id>/emailer_preview`)
- AWS proxy accepts queued `emailer_sync_preview` actions only (no direct SES send yet)

### 7) PayPal payment-processing abstraction (preview + sync queue)

- member metadata refs in `profile_refs` define client website checkout context
- canonical FND preview endpoint validates/derives checkout URLs (`/portal/api/paypal/member/<member_id>/checkout_preview`)
- legacy compatibility endpoint remains available (`/portal/api/paypal/tenant/<tenant_id>/checkout_preview`)
- PayPal proxy accepts queued `checkout_profile_sync` actions and persists non-secret checkout context

### 9) Shared datum mediation defaults

- shared mediation lives under `portals/_shared/portal/mediation/`
- default interpretations include boolean refs, char/ASCII, dns wire, text-byte formats, timestamps/spans, lengths, and coordinates
- services decode/encode through shared contracts instead of portal-specific one-off handlers

### 8) Multi-portal progeny UX reinstatement (CVCC/MW/MT/TFF)

- Local-first portal instance model remains canonical for non-FND portals (`off|local|live` managed by control API).
- CVCC and TFF provide board-member classroom surfaces:
  - tabs: `feed`, `calendar`, `people`
  - TFF adds `workflow`
- Compatibility routing keeps `tab=streams` as a redirect to `tab=feed`.
- Feed/calendar visibility is backend allowlist-driven from active portal config (`organization_config.default_values/added_values`).
- Missing progeny refs in portal configs auto-seed local profile files in `private/progeny/`.
- `private/config.json` is canonical for legal-entity page behavior defaults (with legacy fallback support).

## Next Milestones

1. Stabilize NIMM overlay UX and reduce visual noise in advanced diagnostics.
2. Add automated API tests for time-series CRUD and request-log v1 validation.
3. Add cross-portal rollout patch for SAMRAS APIs/UI after FND validation.
4. Package FND-specific tools cleanly under service/tool boundaries.
5. Expand board-workspace write controls (feed/calendar/workflow) with stricter role-group policies from organization-profile config layers.
6. Formalize tenant-specific email format policies (`dns_wire_format` vs `text_byte_email_format`) before enabling outbound send.
7. Finalize per-tenant hosted website mappings (TFF/CVCC and future tenants) for PayPal checkout URLs and webhook routes.
8. Continue staged migration from legacy `tenant`/`board_member` terminology toward canonical `member`.

## Canonical References

- [`TOOLS_SHELL.md`](TOOLS_SHELL.md)
- [`DATA_TOOL.md`](DATA_TOOL.md)
- [`SAMRAS_PAGE.md`](SAMRAS_PAGE.md)
- [`TIME_SERIES_ABSTRACTION.md`](TIME_SERIES_ABSTRACTION.md)
- [`REQUEST_LOG_V1.md`](REQUEST_LOG_V1.md)
- [`AWS_EMAILER_ABSTRACTION.md`](AWS_EMAILER_ABSTRACTION.md)
- [`PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md`](PAYPAL_PAYMENT_PROCESSING_ABSTRACTION.md)
- [`POC_WORKSPACE_MODEL.md`](POC_WORKSPACE_MODEL.md)
- [`PROGENY_PROFILE_CARDS.md`](PROGENY_PROFILE_CARDS.md)
- [`PROGENY_CONFIG_MODEL.md`](PROGENY_CONFIG_MODEL.md)
- [`DATUM_MEDIATION_DEFAULTS.md`](DATUM_MEDIATION_DEFAULTS.md)
- [`request_log_and_contracts.md`](request_log_and_contracts.md)
