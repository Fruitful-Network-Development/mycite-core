# Internal File Sources

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical

## Parent Topic

[Tools](README.md)

## Current Contract

Internal operational files may be consumed by tools only through shared-core read-only services. Tools do not receive raw filesystem authority.

The shared-core internal-source contract currently supports:

- `json`
- `ndjson`
- `nginx_access_log`
- `nginx_error_log`
- `text` fallback

Current implementation seam:

- `_shared.portal.application.internal_sources`
- consumed by service-collection config-context assembly in `_shared.portal.application.service_tools`

## FND-EBI Pattern

`fnd_ebi` remains a service-collection tool anchored by `web-analytics.json`. Profile members such as `fnd-ebi.fnd.json` provide:

- `domain`
- `site_root`

Analytics paths are derived by shared core logic:

- `client_root = dirname(site_root)`
- `analytics_root = client_root + "/analytics"`
- `access_log = analytics_root + "/nginx/access.log"`
- `error_log = analytics_root + "/nginx/error.log"`
- `events_file = analytics_root + "/events/YYYY-MM.ndjson"` (current UTC month)

The profile JSON remains the canonical input. Full analytics file paths are derived and not duplicated in profile payloads by default.

Current FND-EBI projection from those derived sources includes:

- freshness (`last_seen_utc`) per access/error/events source when parseable
- traffic windows (`24h`, `7d`, `30d`)
- approximate unique visitors (IP-based)
- response class breakdown (`2xx/3xx/4xx/5xx`)
- bot-share and suspicious-probe counts
- top pages, referrers, and top error routes
- asset-vs-page request split
- events coverage summary and event-type counts
- explicit warning surfaces for missing/unreadable/stale/no-events/no-robots signals

## Ownership Boundary

- **Core owns:** path derivation helpers, internal-root safety, file-kind detection, read-only parsing/normalization.
- **Tool owns:** interpretation/projection of the normalized payload into mediated cards and views.
- **Shell owns:** directive and attention state; tools must not own canonical shell state.

## Read-Only Scope

This contract is read-only in current form. No mutate/apply path is introduced for internal analytics files.

## Update Triggers

- Changes to internal file-kind support
- Changes to allowed-root policy for internal reads
- Changes to profile-to-analytics derivation rules
- Any proposal to move internal file reads out of shared core

