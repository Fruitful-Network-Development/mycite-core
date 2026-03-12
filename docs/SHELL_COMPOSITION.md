# Locked Shell Composition

## Top-Level Structure

Portal pages use a fixed IDE-like shell:

1. top menu bar (`.ide-menubar`)
2. far-left global activity bar (`.ide-activitybar`)
3. left page-local context sidebar (`.ide-contextsidebar`)
4. central workbench (`.ide-workbench`)
5. right contextual inspector drawer (`.ide-inspector`)

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

### Context Sidebar (page-local)

- page-local list/filter/navigation groups
- selection lists (aliases/request logs/P2P on NETWORK)
- mode/filter controls (SYSTEM data workspace shortcuts)

### Workbench (center)

- main interactive surface
- editors, graph navigation, conversation/workflow content

### Inspector (right)

- contextual detail/investigation panels
- profile/contact-card details
- abstraction path/investigation payloads
- should be treated as contextual drawer, not a center-content replacement
