# Development Plan

## Current Baseline (March 2026)

### Runnable portals

- `mycite-ne-example`
- `mycite-le-example`
- `mycite-le_fnd`
- `mycite-le_cvcc`
- `mycite-ne_mw`
- `mycite-ne_dm`

### Retained state-only folders

- `mycite-le_tff`
- `mycite-ne_mt`

### Consolidation complete in this milestone

- Service-first shell standardized across runnable portals.
- Canonical routes are now `/portal/home`, `/portal/data`, `/portal/network/*`, `/portal/tools`, `/portal/inbox`.
- `data_tool` is no longer a primary navigation surface and is ignored from `enabled_tools`.
- `mycite-ne_dg`, `mycite-ne_eb`, `mycite-ne_jt`, and `mycite-ne_ks` were retired as standalone folders.
- Their profile artifacts were migrated into CVCC internal progeny profile cards.

## Architectural Direction

### 1) Service shell first

Primary user navigation is service-based and stable:

- `Home`
- `Data`
- `Network`
- `Tools`
- `Inbox`

### 2) Tools are additive packages

Tools remain optional route packages under `/portal/tools/<tool_id>/home`.
They are not substitutes for the core service shell.

### 3) Data as core service

Data model behavior is defined by `/portal/api/data/*` contracts and NIMM directives.
UI implementation remains iterative, but route ownership is fixed at `/portal/data`.

### 4) Relationship surfaces are profile-card backed

`/portal/network/*` tabs use JSON-backed cards:

- `contracts`
- `magnetlinks`
- `progeny`
- `alias`

Secrets are not allowed in profile-card payloads.

## Next Milestones

1. Expand card editing APIs for progeny/alias with strict field allow-lists.
2. Add route-level tests for canonical service routes across all runnable portals.
3. Continue migrating legacy ad-hoc home tab content into service pages.
4. Move experimental or portal-specific UI details behind explicit package boundaries.

## Canonical References

- [`TOOLS_SHELL.md`](TOOLS_SHELL.md)
- [`DATA_TOOL.md`](DATA_TOOL.md)
- [`PROGENY_PROFILE_CARDS.md`](PROGENY_PROFILE_CARDS.md)
- [`request_log_and_contracts.md`](request_log_and_contracts.md)
