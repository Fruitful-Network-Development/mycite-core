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
- consume tool-layer sandbox context (`shell_surface=tool_mediation`) when launched from activity-bar tool entrypoints
- consume shared-core internal-source projections for read-only internal files (no direct raw filesystem ownership)
- rely on instance-led tool manifests from `private/config.json` (`tools_configuration[].name`) with runtime normalization to provider ids

A provider may not:

- invent a new top-level shell
- redefine directives
- own canonical attention state
- preserve incompatible state after attention changes
- forge event provenance to bypass shell lock rules
- bypass shared-core internal-source authority with tool-local unrestricted file reads

Compatibility routes may remain for lineage or deep linking, but they must normalize into the current `SYSTEM` model and must not define visible product framing.

## Instance-Led Tool Identity

Canonical instance manifests may use hyphenated tool slugs (for example `agro-erp`, `fnd-ebi`) while runtime/provider ids remain underscore-normalized (`agro_erp`, `fnd_ebi`) for Python package compatibility.

Runtime normalization rules:

- `tools_configuration[].name` (or legacy `tool_id`) is accepted as source token.
- hyphenated slugs normalize to underscore ids for provider import and capability matching.
- per-tool state roots and specs remain slug-oriented on disk under `private/utilities/tools/<tool-slug>/`.

## Event Provenance Contract

Selection and directive events in the shared shell must include provenance when emitted by workbench UI:

- `origin=auto_init` or `origin=auto_refresh` for automatic/default bootstrap emissions
- `origin=user_select`, `origin=user_file_focus`, or `origin=user_task_change` for explicit operator intent

Tool-layer mediation lock uses this provenance to avoid accidental replacement by automatic anthology initialization.

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
