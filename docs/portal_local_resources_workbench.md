# Historical: Local Resources compatibility workbench

## Status

This document is retained for lineage only.

It describes the earlier `System -> Local Resources` compatibility workbench that existed before the unified `SYSTEM` page became the canonical surface. The current contract is documented in:

- `SYSTEM_WORKBENCH_ARCHITECTURE.md`
- `portal_system_page_composition.md`
- `directive_context_UI_refactor.md`

## Historical framing

The old Local Resources surface treated sandbox and local-resource inventory as a dedicated three-pane page with its own client runtime. That framing is no longer the active `SYSTEM` architecture.

Today:

- `local_resources` remains a compatibility query token only
- active portals resolve that token back into the unified `SYSTEM` shell
- sandbox and local-resource APIs still exist, but they are not presented as a current top-level `SYSTEM` tab

## Historical implementation notes

The compatibility surface was built around:

- `GET /portal/api/data/sandbox/resources`
- `GET /portal/api/data/resources/local`
- `GET /portal/api/data/sandbox/resources/<resource_id>`
- `POST /portal/api/data/sandbox/samras_workspace/view_model`

It also used:

- `portal/ui/static/tools/local_resources_workbench.js`
- `.lr-workbench__*` styles in `portal.css`

Those assets may remain in the repo for compatibility lineage, but they are not the canonical current `SYSTEM` design.
