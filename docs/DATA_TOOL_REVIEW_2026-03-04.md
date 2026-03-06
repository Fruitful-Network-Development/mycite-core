# Data Tool Review (2026-03-04)

## Scope reviewed

- Tool page UX (`/portal/tools/data_tool/home`)
- Home page orientation tabs
- Alias session/profile tab messaging
- Sidebar navigation links
- Data API/controller/engine boundaries
- NIMM directive wiring (`nav/inv/med/man`)
- Presentation icon sidecar flow

## Key findings (pre-polish)

1. UI copy implied stronger finality than implemented behavior.
2. FND still had legacy `/portal/data/*` template routes wired, which can mislead development direction.
3. Icon examples/docs still assumed folder taxonomy, while active icon library had moved to mostly flat filenames.
4. Model assumptions (what is guaranteed vs evolving) were not clearly surfaced in the tool UI.

## Changes applied

1. Data Tool now has explicit prototype contract messaging in the page itself.
2. Data workspace now publishes `model_meta` (via state and dedicated model endpoint).
3. Icon relpath mode defaults to `basename` (ambiguous/flat) and supports compatibility fallback for foldered legacy relpaths.
4. FND removed legacy `/portal/data/*` UI route wiring; `/portal/data` is now a first-class service route.
5. Home, base, and alias surfaces were updated to clarify that page-local tabs are orientation UI, not stable product contract.
6. Sidecar icon mapping examples were updated to flat filenames.
7. Icon picker modal close behavior was hardened (`hidden` + explicit `display:none`, Esc close, `pageshow` cleanup) to prevent stuck overlay state.
8. Portal navigation now renders tool links directly in the sidebar from runtime metadata, so leaving Data does not depend on JS dropdown state.
9. Tool dropdown now has a no-JS-safe fallback (collapsible class toggled only when JS initializes), preventing navigation lock if script init fails.
10. FND Data Tool now exposes an anthology-first primary surface:
   - collapsible Layer -> Value Group sections
   - table rows limited to anthology datum entries
   - append flow for new datums using `<layer>-<value_group>-<next_iteration>`
11. Broader NIMM workspace controls are still available, but moved under an explicit Advanced section to avoid false assumptions during current development.
12. Anthology row editing moved into a Datum Profile modal (not inline):
   - Details tab (title/label edit)
   - Icon tab (icon selection/clear)
   - Abstraction Path tab (reference-chain view for the datum)

## Current intended flow (authoritative)

- Use the service shell header as canonical navigation.
- Treat page-local tabs as orientation/preview surfaces.
- Use API responses from `/portal/api/data/*` as behavior truth.
- Use NIMM directives for interactive state changes.
- Stage edits first, then commit.
- Keep icon metadata in `data/presentation/datum_icons.json` only.

## Remaining deliberate non-final areas

- Table/archetype inference model is still evolving.
- Pane labels/layout are still subject to iterative UX work.
- JSON storage adapter is still a prototype persistence backend.

## Next recommended development guardrails

1. When adding behavior, update `workspace.model_meta()` guarantees/non-guarantees.
2. Keep new Data Tool controls mapped to explicit directives (avoid hidden UI-only state).
3. Keep secret-bearing integration state outside portal repo paths.
4. Keep FND-only experiments under `mycite-le_fnd/data/dev/*` behind config flags.
