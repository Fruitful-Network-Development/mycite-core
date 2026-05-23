# Analytics Event Schema — `mycite.v2.analytics.event.v3`

## Purpose

One row in the analytics NDJSON log is one observed event from one
visitor at one point in time. The store is **append-only**: rows are
never rewritten in place, and insights are never persisted as the
primary source of truth. Derived views (sessions, visitor timelines,
page rankings, etc.) are computed on demand from these rows by pure
functions in `MyCiteV2.packages.core.analytics.derivations`.

This document is the contract for the v3 schema. v3 extends v2
additively — every v2 row remains a valid v3 row with the new fields
defaulted.

## Field set

Fields are stamped at one of two layers:

- **client-stamped** — set by the browser-side collector and sent in
  the `POST /__fnd/analytics/event` body.
- **server-stamped** — set inside the route handler from the request
  context (headers, cookies, IP) or the body's content.

### Server-stamped (identity + observation metadata)

| Field | Type | Notes |
|---|---|---|
| `event_id` | str | ULID-shaped, k-sortable by timestamp prefix. |
| `received_at_utc` | str | ISO-8601 server clock at write time. |
| `schema` | str | `"mycite.v2.analytics.event.v3"`. |
| `collector_version` | str | `"fnd-analytics/3.0"`. |
| `site_id` | str | Portal instance ID (e.g. `fnd`). |
| `domain` | str | Lower-cased request host. |
| `environment` | str | `prod` / `dev` / `staging`. |
| `visitor_cookie_id_hash` | str | SHA-256 of `(salt, fnd_vid cookie)`. |
| `ip_hash` | str | SHA-256 of `(salt, remote_addr)`. |
| `ip_prefix` | str | `a.b.c.0/24` for IPv4 or `aaaa:bbbb:cccc::/48` for IPv6. |
| `is_bot` | bool | Coarse classifier outcome at write time. |
| `bot_class` | str | One of `verified_search`, `ai_crawler`, `seo_tool`, `uptime_monitor`, `scraper`, `likely_bot`, or `""`. |
| `bot_evidence` | list[str] | UA-regex rule keys that fired. |
| `user_agent_raw` | str | Original UA header (bounded to `MAX_TEXT_FIELD_BYTES`). |
| **`quality_flags`** | list[str] | **NEW in v3.** Evidence tokens computed at write time. See "Quality flags" below. |

### Client-stamped (required)

| Field | Type | Notes |
|---|---|---|
| `event_type` | str | One of `KNOWN_EVENT_TYPES`. |
| `occurred_at_utc` | str | ISO-8601 browser clock when the event happened. |
| `session_id` | str | Client-side session token (30 min idle gap). |
| `page_path` | str | Path portion of the page URL. |

### Client-stamped (optional, default empty / 0 / False / [])

| Field | Type | Notes |
|---|---|---|
| `event_name` | str | Free-form sub-type (e.g. `cta_book_now`). |
| `event_index_in_session` | int | 1-based ordinal of this event within the session. |
| `page_query_hash` | str | Stable hash of the query string (raw query not persisted). |
| `page_title` | str | `document.title`. |
| **`page_url`** | str | **NEW in v3.** Absolute `window.location.href` (bounded to `MAX_TEXT_FIELD_BYTES`). |
| `referrer_url` | str | `document.referrer`. |
| `referrer_domain` | str | Host portion of `referrer_url`. |
| `origin_type` | str | Optional client classification; canonical aggregation lives in `derivations.classify_origin`. |
| `utm_source` / `utm_medium` / `utm_campaign` / `utm_content` / `utm_term` | str | Standard UTM parameters. |
| `previous_page_path` | str | The path the visitor was on before this event. |
| `time_since_previous_ms` | int | Milliseconds since the previous event in the session. |
| `active_time_ms` | int | Milliseconds the page was both visible and the tab was focused. |
| `visible_time_ms` | int | Milliseconds the page was visible. |
| `scroll_depth_percent` | int | Deepest scroll percentage observed (0-100). |
| `device_type` | str | Best-effort `mobile` / `tablet` / `desktop`. |
| `browser_name` | str | Best-effort browser name from UA hints. |
| **`os_name`** | str | **NEW in v3.** Best-effort `Windows` / `macOS` / `iOS` / `Android` / `Linux` / `Other`. |
| `viewport_width` / `viewport_height` | int | Pixels. |
| `language` | str | `navigator.language`. |
| `do_not_track` | bool | True if `navigator.doNotTrack === "1"`. |
| `properties` | dict | Free-form, bounded to `MAX_PROPERTIES_BYTES` serialised. |

## Quality flags

`quality_flags` is a list of evidence tokens the route handler attaches
at write time. They are *signals*, not conclusions. The full set
recognised by v3:

| Token | Meaning |
|---|---|
| `clock_skew` | `abs(received_at_utc - occurred_at_utc) > 60 seconds`. |
| `no_referrer_parse` | `referrer_url` is set but `referrer_domain` is empty (parser fell through). |
| `malformed_url` | `page_url` set but failed `urlparse`. |
| `zero_active_time_with_navigation` | `event_type` ∈ {`heartbeat`, `page_view`} with `active_time_ms == 0` AND `previous_page_path != page_path` (both non-empty). |
| `missing_identifier` | `visitor_cookie_id_hash` could not be set (cookie + salt both unavailable). |

Derivations may also append flags they compute (e.g. duplicate-detection at
read time), but those never land back in the on-disk row.

## Geographic / network enrichment

Deferred. v3 intentionally does **not** include `country`, `region`,
`city`, `postal_prefix`, `asn`, or `network_org`. The schema is reserved
for a future v4 once a backing GeoIP / ASN datasource is selected. The
existing `ip_prefix` token + the `detect_vpn_geo_jumps` derivation are
the only "where from?" signals today.

## Backwards compatibility

- v2 rows on disk lack `page_url`, `os_name`, and `quality_flags`. The
  derivations layer reads via `dict.get(key, default)` so missing keys
  are tolerated.
- v2 readers ignore unknown v3 keys.
- No migration of historical NDJSON files is required.

## Storage

- Path: `<private>/utilities/tools/analytics/analytics.<domain>.events.<YYYY-MM>.ndjson`.
- Format: one JSON object per line, UTF-8.
- Append-only. No row is ever rewritten in place.
- Retention: 365 days online + cold archive at
  `<private>/utilities/tools/analytics/archive/`.
- No analytics presence in `mos_authority.sqlite3` (the legacy
  `MosDatumAnalyticsSummaryAdapter` is retired).

See `mos_authority_enforcement.md` § "Allowed: append-only observation
logs" for the doctrine basis.
