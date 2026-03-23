# Directive / Context UI Refactor Audit

## Refactor goal

This report records the current framing of the unified `SYSTEM` workbench after the directive/context UI refactor.

It is a supporting document, not the canonical contract. Use it as the audit and navigation layer across the docs and active portal implementations.

The canonical `SYSTEM` framing is now:

- one unified workbench on `/portal/system`
- one visible left **control panel**
- one visible right **Details** inspector
- persistent top-left NIMM directives
- a shared AITAS state strip that reflects file focus vs datum focus

## Audit findings

### Active portal state

The active portal flavors, `fnd` and `tff`, both already render the same unified `SYSTEM` shell:

- `services/system.html` in both flavors uses the same control panel / Details / unified workbench framing
- both flavors present `Navigate`, `Investigate`, `Mediate`, and `Manipulate` as the persistent directive cluster
- both flavors present the `SYSTEM` page as a file-aware workbench over `anthology.json`, `samras-txa.json`, and `samras-msn.json`

### Documentation drift found

The main drift before this audit fell into three groups:

1. canonical docs that still described `SYSTEM` as tabbed or split
2. supporting docs that already matched the new framing but were not consistently indexed
3. stale docs that still read like active architecture for Local Resources or the old anthology-first workbench

### Compatibility internals still present

Some compatibility internals remain intentionally in the runtime:

- `local_resources` and `inheritance` query values
- `workbench=anthology` and `workbench=resources`
- legacy compatibility scripts and styles for older resource workbench flows

These remain for compatibility and lineage only. They are not the current visible `SYSTEM` product model.

## Current architecture summary

### Shell and regions

- **Control panel**: current file/datum summary plus compatible mediations
- **Workbench**: the canonical layered table for `anthology.json`, `samras-txa.json`, and `samras-msn.json`
- **Details**: active NIMM directive content for file focus or datum focus

### Directive model

The workbench always exposes:

- `Navigate`
- `Investigate`
- `Mediate`
- `Manipulate`

These directives are persistent controls, not temporary overlays or alternate page tabs.

### AITAS model

The visible `SYSTEM` state machine is currently driven by:

- `Attention`
- `Intention`
- `Time`
- `Archetype`
- `Spacial`

In the current implementation:

- file focus means attention is on a canonical file and `spacial = 1`
- datum focus means attention is on a selected datum and `spacial = 2`
- `Time` and much of `Archetype` remain placeholder facets

### Mutation model

- `anthology.json` uses direct anthology authority
- `samras-txa.json` and `samras-msn.json` use staged mutate/publish behavior
- create/delete affordances appear only during `Manipulate`

## Compatibility boundary

The following are compatibility entrypoints, not current `SYSTEM` navigation:

- `?tab=local_resources`
- `?tab=inheritance`
- `?workbench=anthology`
- `?workbench=resources`

The following APIs remain valid, but should not be mistaken for separate current `SYSTEM` tabs:

- `GET /portal/api/data/resources/local`
- `GET /portal/api/data/resources/inherited`
- shared sandbox resource routes under `/portal/api/data/sandbox/*`

Historical docs are retained when they explain lineage, but they must not define the current runtime contract.

## Docs updated by this audit

### Canonical docs aligned

- `PORTAL_CORE_ARCHITECTURE.md`
- `CANONICAL_DATA_ENGINE.md`
- `DATA_TOOL.md`
- `README.md`

### Supporting docs aligned or indexed

- `SYSTEM_WORKBENCH_ARCHITECTURE.md`
- `portal_system_page_composition.md`
- `portal_shell_contract.md`
- `module_system_contract.md`
- `PORTAL_SHELL_UI.md`
- `SHELL_COMPOSITION.md`
- `AITAS_CONTEXT_MODEL.md`
- `TOOLS_SHELL.md`

### Historical docs reframed

- `portal_local_resources_workbench.md`
- `ANTHOLOGY_WORKBENCH_ARCHITECTURE.md`

## Follow-up cleanup not required for the current contract

- internal variable names in older JS still include `resources` / `anthology` naming
- compatibility-only route/tab plumbing still exists in shared registry/runtime helpers
- historical compatibility scripts remain in the repo for lineage and fallback behavior

Those are reasonable future cleanup targets, but they do not change the current visible `SYSTEM` contract.
