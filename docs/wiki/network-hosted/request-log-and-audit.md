# Request Log And Audit

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Network And Hosted](README.md)

## Status

Canonical

## Parent Topic

[Network And Hosted](README.md)

## Current Contract

The request log is the append-only record for external and cross-portal events. It is not the catch-all log for local tool or local data-engine actions.

Current v1 posture is additive:

- endpoint remains `POST /portal/api/request_log`
- legacy payloads are still accepted
- canonical log naming remains `request_log`

Current storage paths are:

- `private/request_log/<msn_id>.ndjson`
- `private/request_log/types/<type>.ndjson`

The v1 envelope requires:

- `type`
- `transmitter`
- `receiver`
- `event_datum`
- `status`

It may also carry non-secret `details`.

Canonical write normalization uses dot-qualified datum refs where possible.

Security boundary:

- do not persist secrets, tokens, passwords, private keys, HMAC keys, API keys, or symmetric keys in request-log payloads

Boundary rule:

- use request-log for external sends, receives, acknowledgements, and other cross-portal evidence
- use local audit logging for local tool CRUD and local data-engine actions

## Boundaries

This page owns request-log and local-audit separation. It does not own:

- compact-array revision protocol in detail
- hosted shell layout
- local business-logic mutation semantics
- provider credential storage

## Authoritative Paths / Files

- `instances/_shared/portal/services/request_log_store.py`
- request-log API surfaces under runtime flavor portal APIs
- local audit logging under `portal.services.local_audit_log`

## Source Docs

- `docs/REQUEST_LOG_V1.md`
- `docs/CONTRACT_UPDATE_PROTOCOL.md`
- `docs/HOSTED_SESSIONS.md`

## Update Triggers

- Changes to request-log payload shape
- Changes to normalization or security rules
- Changes to typed fanout handling
- Changes to the boundary between request-log and local audit logging
