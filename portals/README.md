# Portals Directory

`portals/` contains runnable portal implementations plus shared runtime modules.

## Runnable portal instances

- `mycite-le_fnd`
- `mycite-le_cvcc`
- `mycite-ne_mw`
- `mycite-ne_mt`
- `mycite-le_tff`

## Shared runtime/assets

- `_shared/` shared core-service and data-contract modules
- `assets/` shared icons and UI assets
- `scripts/` portal-adjacent helper scripts

## POC workspace model

- CVCC and TFF expose board-member classroom surfaces.
- Canonical tabs: `feed`, `calendar`, `people`.
- TFF adds `workflow`.
- Legacy `streams` links are compatibility redirects to `feed`.
- Event visibility is backend allowlist-driven from `organization_config.default_values/added_values` in active portal config (`private/config.json`, with legacy fallback support).

## Progeny embed landing

- Canonical chooser route: `GET /portal/embed/progeny`
- Query params:
  - `member_msn_id` (optional, highlights matching card)
  - `as_alias_id` (optional context carry)
- Primary action on each card: open `/portal/alias/<alias_id>`
- Secondary action (when available): open type-specific embed route (`board_member`, `tenant`, or `poc`)
- Landing route is intentionally read-only and does not enforce board-member allowlisting.

## Broadcast Config

- Supported config path: `private/config.json` (canonical), with `private/mycite-config-*.json` as fallback.
- Config keys:
  - `organization_config.default_values.broadcast_config`
  - `organization_config.added_values.broadcast_config`
  - `progeny_type_configs.broadcast` (optional)
- Required top-level keys:
  - `schema`
  - `type`
  - `channels`
  - `members`
  - `homepage_sections`
  - `inheritance_rules`
- Canonical channel keys: `paypal`, `aws`, `keycloak`
- Default behavior:
  - FND enables broadcast mode by default.
  - Other portals can opt in by setting `"enabled": true`.

## Local progeny behavior

Portal runtimes auto-seed missing progeny refs from active config into local profile files under `private/progeny/`.

## Shell/runtime standard

All portals follow the shared service-shell/runtime contract:

- shared service runtime: `../portals/_shared/portal/core_services/`
- shared tool runtime: `../portals/_shared/portal/tools/runtime.py`
- shell contract doc: [`../docs/TOOLS_SHELL.md`](../docs/TOOLS_SHELL.md)

## Canonical docs

- [`../README.md`](../README.md)
- [`../docs/DEVELOPMENT_PLAN.md`](../docs/DEVELOPMENT_PLAN.md)
- [`../docs/POC_WORKSPACE_MODEL.md`](../docs/POC_WORKSPACE_MODEL.md)
- [`../docs/PROGENY_PROFILE_CARDS.md`](../docs/PROGENY_PROFILE_CARDS.md)
- [`../docs/DOCUMENTATION_POLICY.md`](../docs/DOCUMENTATION_POLICY.md)
- [`../docs/request_log_and_contracts.md`](../docs/request_log_and_contracts.md)
- [`../docs/DATA_TOOL.md`](../docs/DATA_TOOL.md)
- [`../docs/TIME_SERIES_ABSTRACTION.md`](../docs/TIME_SERIES_ABSTRACTION.md)
