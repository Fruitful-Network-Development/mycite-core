# Locked Shell Composition

## Top-Level Structure

Portal pages use a fixed IDE-like shell:

1. top menu bar (`.ide-menubar`)
2. far-left global activity bar (`.ide-activitybar`) with `NETWORK`, `UTILITIES`, `SYSTEM`
3. left page-local context sidebar (`.ide-contextsidebar`)
4. central workbench (`.ide-workbench`)
5. right contextual inspector drawer (`.ide-inspector`)

The left context sidebar and right inspector are resizable. The inspector is collapsible and its width is persisted locally.

Primary template:

- `portals/mycite-le_fnd/portal/ui/templates/base.html`
- mirrored in TFF package

Primary styling:

- `portals/mycite-le_fnd/portal/ui/static/portal.css`
- mirrored in TFF package

## Responsibility Split

### Activity Bar (global)

- global service/page switching
- always visible
- not page-specific content editing
- `PERIPHERALS` is no longer a primary activity; legacy routes redirect into `NETWORK` or `UTILITIES`

### Context Sidebar (page-local)

- page-local list/filter/navigation groups
- selection lists (aliases/request logs/P2P on NETWORK)
- datum editor content for `SYSTEM`
- utility tab navigation for `UTILITIES`

### Workbench (center)

- main interactive surface
- editors, graph navigation, conversation/workflow content

### Inspector (right)

- contextual detail/investigation panels
- profile/contact-card details
- abstraction path/investigation payloads
- should be treated as contextual drawer, not a center-content replacement
