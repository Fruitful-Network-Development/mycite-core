# Shell Composition

## Top-level structure

Portal pages use a fixed IDE-like shell:

1. top menu bar (`.ide-menubar`)
2. far-left global activity bar (`.ide-activitybar`)
3. left page-local **control panel** (`#portalControlPanel`, `.ide-controlpanel`)
4. central workbench (`.ide-workbench`)
5. right **Details** inspector (`.ide-inspector`)

The control panel and Details inspector are resizable. The inspector is collapsible. Width is persisted locally.

## Responsibility split

### Activity bar

- global service switching
- always visible

### Control panel

- page-local navigation and context
- current selection summaries
- lightweight supporting controls
- on `SYSTEM`, compatible mediations and file/datum context

### Workbench

- primary interactive surface
- editors, tables, graphs, hosted tools

### Details

- contextual file/datum inspection
- mediation and manipulation panels
- richer editing surfaces than the control panel
- on `SYSTEM`, reflects the active NIMM directive and current AITAS state
