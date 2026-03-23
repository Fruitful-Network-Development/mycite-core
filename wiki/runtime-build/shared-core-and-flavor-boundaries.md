# Shared Core And Flavor Boundaries

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Runtime And Build](README.md)

## Status

Canonical

## Parent Topic

[Runtime And Build](README.md)

## Current Contract

Shared-core authority lives under `portals/_shared/portal/**`. It owns API composition, data-engine semantics, MSS and contract logic, sandbox ownership, and runtime helpers.

Flavor runtimes under `portals/_shared/runtime/flavors/*` are composition wrappers. They may carry:

- flavor flags
- behavior toggles
- enabled-tool composition
- shared shell wiring

They do not own divergent data, MSS, or shell semantics.

Canonical route and surface posture includes:

- `GET /portal/system` as the canonical `SYSTEM` surface
- `/portal/api/data/*` as the canonical data-service API
- `GET /portal/data` as the canonical Data Tool browser entry
- `NETWORK > Contracts` as the canonical contract editor

Compatibility shims may remain, but they are explicit shims and not the primary runtime model.

## Boundaries

This page owns shared-core versus flavor runtime boundaries. It does not own:

- build-spec seeding details
- hosted/progeny page behavior
- specific tool workflows
- shell-region composition in depth

## Authoritative Paths / Files

- `docs/PORTAL_CORE_ARCHITECTURE.md`
- `portals/_shared/portal/**`
- `portals/_shared/runtime/flavors/*`

## Source Docs

- `docs/PORTAL_CORE_ARCHITECTURE.md`
- `docs/application_organization_refactor_report.md`

## Update Triggers

- Changes to shared-core ownership
- Changes to flavor-runtime responsibilities
- Changes to compatibility shims or canonical entry routes
- Changes to data route registration ownership
