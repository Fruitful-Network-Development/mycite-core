# Application Core And Adapters

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Architecture](README.md)

## Status

Canonical

## Parent Topic

[Architecture](README.md)

## Current Contract

The portal should be understood as:

- one host-agnostic application core
- bounded contexts for anthology, resources, contracts, sandbox, network, workbench, and tools
- host-agnostic application services for orchestration
- adapters for web transport, file-backed storage, and flavor/runtime composition

Routes are adapter-level translation points. They deserialize requests, call host-agnostic services, and serialize results. They are not the main architectural boundary.

The domain core owns pure logic such as:

- datum identity
- anthology normalization
- MSS compilation and decode
- sandbox compile and adapt behavior
- mediation and geometry logic
- inheritance adaptation
- internal-source derivation and read-only normalization for tool-facing config-context projections

Storage remains file-backed. The key architectural rule is isolation of responsibilities, not replacement of the storage model.

## Directional Intent

The refactor direction is toward explicit application services, repository ports, and renderer-neutral view models so the same core can serve browser and future desktop hosts without redefining semantics.

## Boundaries

This page owns high-level organization and responsibility boundaries. It does not own:

- specific page composition details
- individual route payload shapes
- tool-specific workflows
- individual runtime config fields

## Authoritative Paths / Files

- `docs/application_organization_refactor_report.md`
- `docs/PORTAL_CORE_ARCHITECTURE.md`
- `instances/_shared/portal/**`
- `instances/_shared/runtime/flavors/*`

## Source Docs

- `docs/application_organization_refactor_report.md`
- `docs/PORTAL_CORE_ARCHITECTURE.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/SANDBOX_ENGINE.md`

## Update Triggers

- Changes to shared-core versus flavor ownership
- Changes to how routing, storage, or host composition is framed
- Introduction of new bounded contexts or application-service seams
- Any proposal that makes a tool or route layer the primary architectural boundary again
