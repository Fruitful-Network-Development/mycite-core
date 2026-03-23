# Historical: Anthology workbench architecture

## Status

This document is preserved as a historical reference.

It describes the earlier anthology-dominant workbench framing that predated the unified `SYSTEM` page. The current active contract is the one-file-at-a-time unified `SYSTEM` workbench documented in:

- `SYSTEM_WORKBENCH_ARCHITECTURE.md`
- `DATA_TOOL.md`
- `directive_context_UI_refactor.md`

## Historical framing

The older model treated anthology as the canonical workbench surface and centered graph-first anthology navigation. That is no longer the current top-level `SYSTEM` framing.

Today:

- anthology remains part of the canonical three-file `SYSTEM` workbench
- anthology graph, profile, and mutation routes still exist and are reused where appropriate
- the visible `SYSTEM` contract is no longer a separate anthology page or anthology/resources split

## Historical implementation notes

The earlier anthology-first surface was built around:

- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/graph`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/profile/update`
- `POST /portal/api/data/directive`

Those routes remain important implementation primitives, but the current UI now presents them through the unified NIMM/AITAS-driven `SYSTEM` workbench rather than through a dedicated anthology workbench.
