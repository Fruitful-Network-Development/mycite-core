# V3.4.2 UI Hydration And Alignment Audit

Date: 2026-04-13

## Scope

This audit records the gap that remained after the earlier April 13 shell
realignment pass:

- hydration failures were still visually ambiguous in the live host
- `CTS-GIS` no longer rendered with interface-panel-primary posture
- browser shell logic was still concentrated in one static bundle

## Findings

- `portal.html` exposed only a template placeholder, with no DOM-visible boot
  state for hydration progress or failure
- `portal.js` initialized only one theme selector even though the template
  rendered two
- principal-shell posture had drifted to a universal workbench-first default,
  which no longer matched the intended mediation posture for `CTS-GIS`
- the old single-file shell bundle made it too easy for tool-specific renderer
  logic to accrete inside core bootstrap code

## Resulting alignment work

- add `surface_posture` to the tool descriptor/runtime contract
- restore `CTS-GIS` as `interface_panel_primary`
- make shell collapse fallback server-issued
- split browser rendering into ordered static registries plus a thin shell core
- add a watchdog-driven fatal state for bundle and hydration failures

## Supersession note

This audit supersedes
[v2_principal_shell_realignment_2026-04-13.md](v2_principal_shell_realignment_2026-04-13.md)
as the current evidence record for April 13 shell posture alignment. The
earlier audit remains archival evidence for the intermediate realignment step.
