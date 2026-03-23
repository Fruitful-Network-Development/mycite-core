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
- `GET /portal/data` -> `/portal/tools/data_tool/home`

The visible activity bar is reserved for the three primary services:

- `SYSTEM`
- `NETWORK`
- `UTILITIES`

Optional tools do not add their own activity-bar application entries. Tool discovery belongs to `SYSTEM -> Mediate`, while tool configuration belongs to `UTILITIES`.

Legacy aliases and compatibility entrypoints may still normalize into the current shell, but they are not part of the visible product framing.

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
