# Tool Layer Mediation

`Home`: [Home](../Home.md) | `Glossary`: [Glossary](../Glossary.md) | `Parent Topic`: [Tools](README.md)

## Status

Canonical

## Purpose

Define the canonical launch and runtime contract for tool-dominant mediation surfaces that run on top of the SYSTEM sandbox without selecting a file/datum by default.

## Launch Contract

- Activity-bar or deep-link launch:
  - `GET /portal/system?mediate_tool=<tool_id>`
- Runtime bootstrap resolves sandbox context via:
  - `POST /portal/api/data/system/sandbox_context`

## Context Contract

Tool-layer mediation context uses:

- `shell_surface=tool_mediation`
- `mediation_scope=system_sandbox`
- `shell_verb=mediate`
- `attention_address=sandbox:utilities/tools/<tool_namespace>`
- `focus_depth=0`

The on-disk sandbox contract for instance-led tools is:

- `private/utilities/tools/<tool-slug>/spec.json`
- `private/utilities/tools/<tool-slug>/tool.<msn_id>.<tool-slug>.json` (anchor)
- optional tool-local members referenced by the anchor payload

Resolver behavior is compatibility-safe:

- prefer sandbox-local `spec.json`
- fallback to legacy `private/tools/<tool_id>.spec.json` only when needed

The canonical SYSTEM workbench remains available internally but is visually non-dominant while tool-layer lock is active.

## Event Provenance And Override Rules

Workbench-origin events must declare provenance:

- `auto_init`
- `auto_refresh`
- `user_select`
- `user_file_focus`
- `user_task_change`

During tool-layer lock:

- automatic/default emissions (`auto_*`) do not replace tool-layer context
- explicit user-origin events may unlock and return control to file/datum attention

## Compatibility Semantics

A mediation-only tool may appear for sandbox context when:

- `shell_surface=tool_mediation`
- `mediation_scope=system_sandbox`
- `shell_verb=mediate`
- tool capability supports config-context mediation

This rule is intentionally scoped to tool-layer contexts and must not leak into ordinary file/datum selection contexts.

