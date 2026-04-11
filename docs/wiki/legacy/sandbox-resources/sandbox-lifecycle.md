# Sandbox Lifecycle

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Sandbox And Resources](README.md)

## Status

Canonical

## Parent Topic

[Sandbox And Resources](README.md)

## Current Contract

Sandbox is the shared-core lifecycle layer for resource logic that should not be scattered across flavor routes, templates, or tool packages.

It owns workflow for:

- MSS form compile, decode, and edit staging
- MSS compact-array decode and context payloads
- SAMRAS structure-aware mutation and persistence
- contact-card exposed resource value generation
- inherited resource context resolution
- FND SAMRAS anthology migration helpers

Primary sandbox lifecycle verbs are:

- stage
- save
- compile
- decode
- adapt
- publish

Canonical shared routes include:

- `GET /portal/api/data/sandbox/resources`
- `GET /portal/api/data/sandbox/resources/<resource_id>`
- `POST /portal/api/data/sandbox/resources/<resource_id>/stage`
- `POST /portal/api/data/sandbox/resources/<resource_id>/save`
- `POST /portal/api/data/sandbox/resources/<resource_id>/compile`
- `POST /portal/api/data/sandbox/mss/compile`
- `POST /portal/api/data/sandbox/mss/decode`
- `POST /portal/api/data/sandbox/samras/upsert`
- `GET /portal/api/data/sandbox/samras/<resource_id>/decode`

## Boundaries

This page owns lifecycle behavior. It does not own:

- cross-scope resource inventory indexes
- visible `SYSTEM` navigation or shell composition
- canonical datum identity
- hosted or contract session models

## Authoritative Paths / Files

- `docs/SANDBOX_ENGINE.md`
- `instances/_shared/portal/sandbox/`
- `instances/_shared/portal/api/data_workspace.py`

## Source Docs

- `docs/SANDBOX_ENGINE.md`
- `docs/CANONICAL_DATA_ENGINE.md`

## Update Triggers

- Changes to sandbox service boundaries
- Changes to sandbox route contracts
- Changes to stage, save, compile, or publish semantics
- Changes to sandbox-owned AGRO draft behavior
