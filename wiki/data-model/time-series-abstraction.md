# Time Series Abstraction

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Data Model](README.md)

## Status

Supporting

## Parent Topic

[Data Model](README.md)

## Current Contract

Time series is currently an anthology-only abstraction. It does not introduce a separate table file.

Canonical anthology anchors are:

- event index anchor datum: `4-0-1`
- event rows: `4-1-*`

Each event row carries exactly two semantic pairs for time-series APIs:

1. point pair
2. duration pair

Reference normalization accepts local and qualified refs, but canonical write form is normalized against the local MSN context.

Current shared data routes include:

- `GET /portal/api/data/time_series/state`
- `POST /portal/api/data/time_series/ensure_base`
- `POST /portal/api/data/time_series/event/create`
- `POST /portal/api/data/time_series/event/update`
- `POST /portal/api/data/time_series/event/delete`
- `GET /portal/api/data/time_series/event/<event_ref>`

`ensure_base` remains idempotent. Event create, update, and delete flows operate directly against anthology-backed time-series rows.

## Directional Intent

This abstraction is documented as FND-first but uses shared-ready normalization patterns so it can expand to other runnable portals without redefining the underlying row contract.

## Boundaries

This page owns the anthology-backed time-series abstraction. It does not own:

- separate file-backed time-series stores
- shell-level tab composition
- general-purpose event or request-log policy
- contract compact-array semantics

## Authoritative Paths / Files

- shared time-series data routes under `portals/_shared/portal/**`
- anthology-backed event rows under `data/anthology.json`

## Source Docs

- `docs/TIME_SERIES_ABSTRACTION.md`

## Update Triggers

- Changes to anthology anchors or event row shape
- Changes to normalization rules for point and duration refs
- Changes to time-series API surface
- Expansion beyond FND-first scope
