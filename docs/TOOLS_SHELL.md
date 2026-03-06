# Service Shell Standard

## Purpose

All runnable portals must use one shared service-first shell:

- top-level services: `Home`, `Data`, `Network`, `Tools`, `Inbox`
- `Data` is a core service route, not a default optional tool package
- `Tools` is reserved for optional packaged capabilities

## Canonical Routes

- `GET /portal` -> redirect to `/portal/home`
- `GET /portal/home`
- `GET /portal/data`
- `GET /portal/network/contracts`
- `GET /portal/network/magnetlinks`
- `GET /portal/network/progeny`
- `GET /portal/network/alias`
- `GET /portal/tools`
- `GET /portal/inbox`

Tool package routes remain additive:

- `GET /portal/tools/<tool_id>/home`

## Runtime Contracts

Shared service metadata/runtime lives under:

- `portals/_shared/portal/core_services/`

Shared tool runtime lives under:

- `portals/_shared/portal/tools/runtime.py`

Portal wrappers must load shared runtimes via portal-local wrapper modules:

- `portal/core_services/runtime.py`
- `portal/tools/runtime.py`

## Config Conventions

`enabled_services` is optional. If missing, the default order is:

- `home`, `data`, `network`, `tools`, `inbox`

`enabled_tools` controls optional tool packages. Legacy token behavior:

- `data_tool` in `enabled_tools` is ignored with warning
- Data UI is reached from `/portal/data`

## Network Tab Model

`/portal/network/*` tabs are path-based and canonical:

- `contracts`
- `magnetlinks`
- `progeny`
- `alias`

Profile cards in relationship tabs are JSON-backed metadata surfaces.
They are non-secret, and secret-like keys are blocked from card payloads.

## UI Requirements

- Base layout includes `partials/service_header.html`
- Service navigation is route-driven, not query-param tab state
- Any local tab controls are page-local only and must not replace canonical service routes
- Alias session routes remain independent of the service shell
