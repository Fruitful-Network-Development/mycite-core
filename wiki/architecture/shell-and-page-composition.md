# Shell And Page Composition

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Architecture](README.md)

## Status

Canonical

## Parent Topic

[Architecture](README.md)

## Current Contract

The canonical `SYSTEM` shell has stable visible regions:

- menu bar
- activity bar
- control panel
- workbench
- Details

Within `SYSTEM`, the page composition contract is:

- one center workbench surface
- no visible anthology/resources split
- no visible Local Resources or Inheritance tabs
- no second inspector column inside the center workbench

The canonical file set for the unified workbench is:

- `anthology.json`
- `samras-txa.json`
- `samras-msn.json`

Default attention starts at `anthology.json`. File switching belongs to `Navigate`. Datum selection moves the workbench from file focus to datum focus. `Manipulate` exposes create and delete affordances at file focus and editing affordances at datum focus.

Canonical shell and service routes are:

- `GET /portal` -> `/portal/system`
- `GET /portal/system`
- `GET /portal/network`
- `GET /portal/utilities`
- `GET /portal/data` -> `/portal/system`

The visible activity bar always includes the three primary services:

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

Optional tools may also contribute first-class activity-bar entries when:

- the tool is enabled for the portal instance (`tools_configuration`)
- the tool is `mediation_only`
- the tool declares an icon for activity rendering

Activity-bar tool entries launch into `SYSTEM` using the canonical query contract:

- `GET /portal/system?mediate_tool=<tool_id>`

This launch enters a **tool-dominant mediation layer** at sandbox depth (no file selected). The data workbench remains present in core logic but is visually non-dominant while the tool layer is locked.

Current staged defaults:

- FND `fnd_ebi` mediation renders analytics profile/domain surfaces.
- TFF `agro_erp` mediation defaults to an empty dual-pane scaffold:
  - `Spatial` (left operational pane + right contextual companion)
  - `Chronological` (left operational pane + right contextual companion), now including a first-pass time-address selector facet that emits canonical mixed-radix addresses for SYSTEM context (`system_state.aitas.time`)

Time remains a facet/state dimension of the unified shell, not a second shell:

- `time` context activates only when a mediated view explicitly sets it
- provider UIs may select addresses, but canonical parsing/comparison/normalization belongs to shared core code
- provider filtering calls service routes and receives resolved visibility state, instead of owning range semantics in the browser

Tool discovery is still available through `SYSTEM -> Mediate`, and tool configuration remains under `UTILITIES`.

Legacy aliases and compatibility entrypoints may still normalize into the current shell, but they are hidden compatibility redirects rather than visible tool-home destinations.

## Boundaries

This page owns visible shell and page composition. It does not own:

- low-level data mutation semantics
- provider-specific mediated views
- contract editing semantics on `NETWORK`
- build materialization rules

## Authoritative Paths / Files

- `docs/portal_shell_contract.md`
- `docs/portal_system_page_composition.md`
- `docs/module_system_contract.md`
- `docs/PORTAL_SHELL_UI.md`
- `docs/SHELL_COMPOSITION.md`
- `portals/_shared/runtime/flavors/*/portal/ui/templates/services/system.html`

## Source Docs

- `docs/portal_shell_contract.md`
- `docs/portal_system_page_composition.md`
- `docs/module_system_contract.md`
- `docs/PORTAL_SHELL_UI.md`
- `docs/SHELL_COMPOSITION.md`

## Update Triggers

- Changes to visible shell regions
- Changes to the canonical file set in `SYSTEM`
- Changes to the default selection, file switcher, or manipulate affordance rules
- Any attempt to add visible split workbench views back into `SYSTEM`
