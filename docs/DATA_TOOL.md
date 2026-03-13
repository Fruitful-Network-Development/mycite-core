# Data Workbench Contract

## Scope

Applies to:

- `portals/mycite-le_fnd`
- `portals/mycite-le_tff`

SYSTEM page hosts the anthology-first workbench.

## Canonical Runtime

Primary runtime artifacts:

- `data/anthology.json` (canonical)
- `data/presentation/datum_icons.json`
- `private/daemon_state/data_workspace.json`

Deterministic anthology ordering is enforced by shared normalization:

- `layer -> value_group -> iteration`
- `portals/_shared/portal/data_engine/anthology_normalization.py`

`demo-conspectus.json` is not a canonical navigation dependency.

## NIMM + AITAS

State facets:

- `attention`, `intention`, `temporal`, `archetype`, `spatial`

Compatibility mirror:

- legacy `spacial` remains mirrored in payloads

State phases:

- `navigate`, `focus`, `investigate`, `mediate`

Pattern hooks are active and exposed in model metadata.

## Graph + Workbench Behavior

Primary interactions:

- single click: focus summary
- double click: investigate (`abstraction_path`) + structured inspector

Graph endpoint supports controls:

- `GET /portal/api/data/anthology/graph?focus=&depth=&layout=&context=`

Context/layout:

- context: `global` / `local`
- layout: `table` / `linear` / `radial`

Workbench behavior:

- `table` is the default layout
- raw datum and abstraction-path detail stay collapsed by default until opened
- datum editing/detail is shown in the right inspector column

## API Contract (Stable)

Core endpoints:

- `GET /portal/api/data/state`
- `POST /portal/api/data/directive`
- `GET /portal/api/data/anthology/table`
- `GET /portal/api/data/anthology/graph`

Daemon endpoints:

- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`
- `POST /portal/api/data/daemon/resolve_tokens`

Legacy shim endpoints remain for compatibility.

## Ownership

Engine + adapters:

- `data/engine/workspace.py`
- `data/engine/nimm/state.py`
- `data/storage_json.py`
- `portal/api/data_workspace.py`

UI consumer:

- `portal/ui/templates/tools/partials/data_tool_shell.html`
- `portal/ui/static/tools/data_tool.js`
