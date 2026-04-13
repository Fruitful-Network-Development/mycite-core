# V2 Principal Shell Realignment Audit 2026-04-13

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

## Scope

This audit records the shell mismatch that remained after the earlier V2.3
root-shell pass and the corrected target that now aligns more closely with the
older V1 principal-panel model without reviving V1 ownership drift.

## Observed mismatch before correction

- The activity bar rendered as anonymous icon-only circles, which obscured the
  principal module set.
- The control panel was populated from a generic shell-global navigation tree,
  not a page-specific module.
- Tool surfaces still switched the shell into a tool-primary composition that
  hid the workbench and auto-promoted the interface panel.
- `CTS-GIS` was treated too much like a peer principal shell item instead of a
  Utilities-launched tool surface.

## Corrected target model

- Four stable shell modules remain present:
  - activity bar
  - control panel
  - workbench
  - interface panel
- Principal activity-bar set is:
  - portal logo
  - `NETWORK`
  - `SYSTEM`
  - `UTILITIES`
  - `AWS-CSM`
- `SYSTEM` is the default core root and owns datum-facing workbench behavior.
- `NETWORK` remains intentionally scaffolded before the first FND-EBI slice.
- `UTILITIES` owns tool/config management.
- `AWS-CSM` is the first promoted tool family.
- `CTS-GIS` remains implemented but is launched from `UTILITIES`, not pinned as a
  peer principal activity item.

## Boundary clarification

- The shell contract remains runtime-owned.
- `packages/state_machine/` remains the authority for root/service/tool
  legality.
- JS/CSS may render the shell but may not invent alternate principal modules or
  route contracts.
- `composition_mode` may remain as semantic metadata, but it is no longer
  allowed to hide the workbench or auto-promote the interface panel.
