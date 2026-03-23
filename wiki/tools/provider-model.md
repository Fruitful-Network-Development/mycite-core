# Provider Model

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical

## Parent Topic

[Tools](README.md)

## Current Contract

Tools are providers, not shells.

A provider may:

- interpret the current attention target
- expose compatible mediated views
- contribute mediation-specific UI
- request shell events through the shared state model

A provider may not:

- invent a new top-level shell
- redefine directives
- own canonical attention state
- preserve incompatible state after attention changes

Compatibility routes may remain for lineage or deep linking, but they must normalize into the current `SYSTEM` model and must not define visible product framing.

## Boundaries

This page owns the provider contract. It does not own:

- the detailed behavior of any specific tool
- shell-region layout
- MSS or SAMRAS data structures
- build-spec enablement fields

## Authoritative Paths / Files

- `docs/development_declaration_state_machine.md`
- `docs/application_organization_refactor_report.md`
- shared runtime and provider integration code under `portals/_shared/`

## Source Docs

- `docs/development_declaration_state_machine.md`
- `docs/application_organization_refactor_report.md`
- `docs/directive_context_UI_refactor.md`

## Update Triggers

- Changes to provider activation rules
- Changes to tool-home compatibility handling
- Any proposal that gives a tool its own shell or page ontology
- Changes to how mediated views consume attention and directive state
