# POC Workspace Model

## Scope

This document defines the classroom-style board-member workspace surfaces used by legal-entity portals.

## Canonical tabs

- `feed`
- `calendar`
- `people`
- `workflow` (TFF only in this milestone)

Compatibility rule:

- `tab=streams` is accepted and redirected to `tab=feed`.

## Routes

- `GET /portal/embed/progeny`
- `GET /portal/embed/board_member?member_msn_id=...&tab=feed|calendar|people`
- `GET /portal/embed/board_member?member_msn_id=...&tab=workflow` (TFF only)
- `POST /portal/embed/board_member/feed/post`
- `POST /portal/embed/board_member/calendar/event`

`/portal/embed/progeny` is a chooser surface that highlights optional `member_msn_id` matches and routes primarily to `/portal/alias/<alias_id>`.

## Event visibility allowlists

Configured in active portal config:

- `private/config.json` (canonical)
- `private/mycite-config-*.json` (legacy fallback)

Paths:

- `organization_config.default_values.stream_config.allowed_post_types`
- `organization_config.added_values.stream_config.allowed_post_types`
  - default: `post.create`, `board_notice`
- `organization_config.default_values.calendar_config.allowed_event_types`
- `organization_config.added_values.calendar_config.allowed_event_types`
  - default: `meeting`, `group_event`, `committee_meeting`

Request-log/general transmission types are intentionally excluded from board calendar/feed views.

## Local progeny seeding

If active portal config has progeny refs that do not yet exist as files, the portal auto-generates local profile records under `private/progeny/`:

- non-secret schema: `mycite.progeny.profile_card.v1`
- source marker: `source.local_only = true`
- generated records are usable in network/progeny and people-card surfaces without alias linkage

## Organization config model

Per-portal defaults and instance overrides are layered from main config:

- `organization_config.file_name` (or `organization_configuration` aliases) chooses legal-entity profile type.
- `organization_config.default_values` defines baseline behavior.
- `organization_config.added_values` defines instance additions/overrides.

Canonical channel keys: `paypal`, `aws`, `keycloak`.
