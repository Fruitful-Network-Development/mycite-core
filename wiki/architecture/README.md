# Architecture

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md)

## Status

Canonical topic

## Current Contract

The current portal architecture is organized around one unified `SYSTEM` workbench, a host-agnostic application core, and adapter-level routing and storage composition.

The visible portal model is:

- one `SYSTEM` workbench
- one shell with stable regions
- tools as providers inside that shell
- file-backed runtime state with shared-core semantics

## Pages

- [System State Machine](system-state-machine.md)
- [Shell And Page Composition](shell-and-page-composition.md)
- [Application Core And Adapters](application-core-and-adapters.md)
- [AITAS Context](aitas-context.md)

## Source Docs

- `docs/development_declaration_state_machine.md`
- `docs/application_organization_refactor_report.md`
- `docs/directive_context_UI_refactor.md`
- `docs/PORTAL_CORE_ARCHITECTURE.md`
- `docs/portal_shell_contract.md`
- `docs/portal_system_page_composition.md`
- `docs/AITAS_CONTEXT_MODEL.md`

## Update Triggers

- Any change to the visible `SYSTEM` interaction model
- Any change to shell regions or workbench composition
- Any refactor that moves logic between shared core, adapters, flavors, or providers
