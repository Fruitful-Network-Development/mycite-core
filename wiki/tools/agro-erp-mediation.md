# AGRO-ERP Mediation

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical

## Parent Topic

[Tools](README.md)

## Current Contract

AGRO-ERP is an optional mediated workspace for the TFF portal. Its canonical launch path is through `SYSTEM` under `Mediate` (`/portal/system?mediate_tool=agro_erp`) at sandbox depth (no required file/datum focus).

AGRO-ERP is a thin consumer of shared services for:

- write preview and apply
- geometry mediation
- inherited resource context
- sandbox-managed draft resources
- readback summaries

Current default mediation is a dual-pane empty scaffold:

- `Spatial`
- `Chronological`

Legacy AGRO modes remain available as secondary compatibility modes:

- `Overview`
- `Taxonomy browse/select`
- `Supplier browse/select`
- `Product profile compose`
- `Supply log compose`
- `Preview/apply`

All AGRO views are mediation modes inside the shared workspace, not a separate shell.

Current MVP direction is TXA-first:

1. enter `SYSTEM`
2. switch to `Mediate`
3. load inherited txa resource context
4. preview and apply shared write flows
5. read back outputs through shared-core view models

No full txa tree should be materialized back into anthology during this workflow.

Decision-freeze topics for next-phase AGRO schema work are tracked in:

- [AGRO-ERP Datum Decision Ledger](agro-erp-datum-decision-ledger.md)

## Boundaries

This page owns the AGRO-ERP mediation role. It does not own:

- shell-level directive definitions
- low-level write-pipeline semantics
- SAMRAS structure logic
- request-log policy outside AGRO's external interaction boundary

## Authoritative Paths / Files

- `docs/AGRO_ERP_TOOL.md`
- TFF AGRO tool code under `portals/_shared/runtime/flavors/tff/portal/tools/agro_erp/`
- shared data-engine APIs under `portals/_shared/portal/`

## Source Docs

- `docs/AGRO_ERP_TOOL.md`
- `docs/AGRO_ERP_INTENTION.md`
- `docs/CANONICAL_DATA_ENGINE.md`
- `docs/SANDBOX_ENGINE.md`

## Update Triggers

- Changes to AGRO launch path or mediation role
- Changes to AGRO view set
- Changes to inherited resource or draft-plan flow
- Changes to whether AGRO owns orchestration versus shared-core semantics
