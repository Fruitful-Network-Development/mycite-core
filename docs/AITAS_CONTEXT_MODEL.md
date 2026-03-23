# AITAS Context Model

## Purpose

AITAS is the shared context frame used by the unified `SYSTEM` workbench:

- `Attention`
- `Intention`
- `Time`
- `Archetype`
- `Spacial`

The current implementation is intentionally lightweight. `Attention`, `Intention`, and `Spacial` now drive the visible shell/workbench state on `/portal/system`, while `Time` and much of `Archetype` remain placeholder facets.

The payload continues to use the field name `spacial` for compatibility with existing runtime/state consumers.

## SYSTEM workbench contract

The unified SYSTEM workbench uses two focus levels:

1. **File focus**
   - `attention`: active canonical file (`anthology.json`, `samras-txa.json`, or `samras-msn.json`)
   - `intention`: `idle` or the active NIMM directive
   - `time`: `null`
   - `archetype`: `null` unless an existing resolver already provides a value
   - `spacial`: `1`
2. **Datum focus**
   - `attention`: selected datum
   - `intention`: active NIMM directive
   - `time`: `null`
   - `archetype`: placeholder unless existing resolution is available
   - `spacial`: `2`

This state is emitted in the SYSTEM selection payload as `system_state.aitas`.

## Current UI usage

- The top-left floating NIMM controls on the SYSTEM workbench always show the current AITAS strip.
- The control panel and Details inspector both reflect the same file-focus or datum-focus state.
- `Navigate` at file focus is the canonical file switcher.
- `Manipulate` uses file focus for create/delete controls and datum focus for value editing.

## API surface

Relevant shared routes:

- `POST /portal/api/data/system/selection_context`
- `GET /portal/api/data/system/resource_workbench`
- `POST /portal/api/data/system/mutate`
- `POST /portal/api/data/system/publish`
