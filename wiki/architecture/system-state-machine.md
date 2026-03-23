# System State Machine

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Architecture](README.md)

## Status

Canonical

## Parent Topic

[Architecture](README.md)

## Current Contract

`SYSTEM` is developed as one reflective state machine over canonical attention targets. The user is not conceptually "on a page mode"; the machine is attending to a subject and projecting UI from that state.

The canonical subject hierarchy is:

- file
- datum
- facet

Recommended attention grammar:

- `file:<file_id>`
- `datum:<file_id>/<datum_id>`
- `facet:<file_id>/<datum_id>/<facet_kind>/<facet_ref?>`

The persistent directive set is:

- `navigate`
- `investigate`
- `mediate`
- `manipulate`

The recommended canonical state fields are:

- `attention`
- `directive`
- `archetype_context`
- `time_context`
- `mutation_mode`

Reset behavior is part of the contract. File changes clear datum and facet attention plus incompatible provider state. Datum exit clears facet and contextual state that no longer applies. Directive changes do not reset attention by default.

Derived UI follows state, not the other way around:

- control panel summarizes context and compatible mediations
- center workbench is the canonical operator surface
- Details reflects the active directive and subject
- AITAS is a projection of state, not a separate state authority

## Directional Intent

Future work should extend the attention grammar, event model, and derived UI rules rather than reintroduce tabs, alternate shells, or ad hoc parallel interaction systems.

Facet-level manipulation, richer time mediation, and deeper archetype context remain intentionally incomplete, but the conceptual backbone is already fixed.

## Boundaries

This page defines the machine model for `SYSTEM`. It does not own:

- wire formats for MSS
- SAMRAS structural encoding rules
- build-spec authority
- hosted or alias session models

## Authoritative Paths / Files

- `docs/development_declaration_state_machine.md`
- `docs/directive_context_UI_refactor.md`
- `portals/_shared/portal/api/data_workspace.py`
- `portals/_shared/portal/data_engine/aitas_context.py`

## Source Docs

- `docs/development_declaration_state_machine.md`
- `docs/directive_context_UI_refactor.md`
- `docs/portal_system_page_composition.md`
- `docs/AITAS_CONTEXT_MODEL.md`

## Update Triggers

- Changes to attention grammar or directive set
- Changes to reset rules or mutation posture
- Changes to how provider state interacts with file or datum changes
- Any visible reframe of `SYSTEM` away from a single stateful workbench
