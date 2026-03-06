# Data Tool (NIMM Workspace)

This document defines the Data Tool contract used by:

- `mycite-ne-example`
- `mycite-le-example`
- `mycite-le_fnd`

It separates intent from implementation guidance.

## Intent

- Treat data as a datum graph, not fixed hard-coded UI tables.
- Keep the current operator surface anthology-first during this phase:
  - collapsible layers/value-groups
  - append workflow for new datum ids
- Drive interactions through NIMM directives:
  - `nav`: navigation context
  - `inv`: investigation context
  - `med`: mediation (mode/lens)
  - `man`: manipulation (stage/commit)
- Keep semantic logic in the engine, not in route handlers or templates.
- Treat UI copy/layout as provisional while the model evolves.

## Implementation Guidance

### Service surface and optional package compatibility

- Canonical Data route:
  - `GET /portal/data`
- Optional compatibility package route:
  - `GET /portal/tools/data_tool/home`
- Legacy config token behavior:
  - `data_tool` in `enabled_tools` is ignored and logged as a legacy core-service token

### Engine modules

- Storage adapter: `data/storage_json.py`
- Domain engine:
  - `data/engine/graph.py`
  - `data/engine/constraints.py`
  - `data/engine/tables.py`
  - `data/engine/lenses/*`
  - `data/engine/nimm/directives.py`
  - `data/engine/nimm/state.py`
  - `data/engine/nimm/viewmodels.py`
  - `data/engine/workspace.py`

### Controller module

- `portal/api/data_workspace.py`

Controllers are thin glue only:

- request validation
- workspace method invocation
- JSON response shaping

## State Schema

`DataViewState` keys:

- `focus_source`: `anthology | conspectus | samras | auto`
- `focus_subject`: string
- `left_pane`: `{kind, payload}`
- `right_pane`: `{kind, payload}`
- `mode`: `general | inspect | raw | inferred`
- `lens_context`: `{default, overrides}`
- `staged_edits`: map of staged cells
- `validation_errors`: list of validation messages
- `selection`: optional active row/cell/table context

Workspace state persistence (non-secret):

- `private/daemon_state/data_workspace.json`

## Directive Schema

`POST /portal/api/data/directive`

Request body:

```json
{
  "action": "nav|inv|med|man",
  "subject": "string",
  "method": "string",
  "args": {}
}
```

Optional compact input is normalized when provided (for example via `directive` string).

Response shape:

```json
{
  "ok": true,
  "state": {},
  "left_pane_vm": {},
  "right_pane_vm": {},
  "errors": [],
  "warnings": [],
  "staged_edits": []
}
```

Prototype metadata:

- `GET /portal/api/data/model`
- `GET /portal/api/data/state` also returns `model_meta`

`model_meta` is the source of truth for current guarantees/non-guarantees.

## API Endpoints

Canonical endpoints:

- `POST /portal/api/data/directive`
- `GET /portal/api/data/state`
- `POST /portal/api/data/stage_edit`
- `POST /portal/api/data/reset_staging`
- `POST /portal/api/data/commit`
- `GET /portal/api/data/anthology/table`
- `POST /portal/api/data/anthology/append`
- `GET /portal/api/data/anthology/profile/<row_id>`
- `POST /portal/api/data/anthology/profile/update`

Anthology append contract:

- Inputs: `layer`, `value_group`, `reference`, `magnitude`, optional `label`
- Behavior: compute next identifier as `<layer>-<value_group>-<iteration>` where `iteration` is max existing for that layer/group + 1
- Output: created datum metadata + refreshed anthology table view

Datum profile update contract:

- Inputs: `row_id` (or `identifier`), `label`, `icon_relpath` (empty string clears icon)
- Behavior: updates anthology row label + icon mapping and returns refreshed anthology table view

Datum profile read contract:

- Input path: `<row_id>` (or identifier token)
- Output: datum metadata + `abstraction_path` chain entries

Example-portal compatibility shims (temporary):

- `GET /portal/api/data/tables`
- `GET /portal/api/data/table/<table_id>/instances`
- `GET /portal/api/data/table/<table_id>/view`
- `POST /portal/api/data/revert_edit`
- `POST /portal/api/data/reset`

## Extension Points

### Lenses

- Baseline in examples:
  - `default` lens
  - `ascii` lens stub
- Lens extension is through `data/engine/lenses/*` and config mapping.

### FND-only experimentation

- Experimental recognizers/lenses must stay under:
  - `mycite-le_fnd/data/dev/*`
- Load only when config enables:
  - `data_tool.enable_dev_data_features = true`

Examples must not import FND dev modules.

## Current Prototype Truths

- The canonical user entrypoint for Data is `/portal/data` in the service shell.
- Optional Data tool package routes may exist for compatibility but are not the primary contract.
- API responses and engine/controller contracts are authoritative; UI labels are advisory.
- Table/archetype inference remains an evolving model and is not final ontology.
- Icon assignments are presentation sidecar metadata only and do not alter anthology semantics.
