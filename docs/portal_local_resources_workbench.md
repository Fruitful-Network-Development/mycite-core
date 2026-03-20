# Local Resources page — sandbox resource workbench

## Intent

The **System → Local Resources** tab is no longer inventory-only. It is a **three-pane workbench**:

1. **Left:** merged list of `GET /portal/api/data/sandbox/resources` and `GET /portal/api/data/resources/local` entries  
2. **Center:** selected resource **raw JSON** (editable), **structured** row/table view, **staged file** snapshot  
3. **Right:** generic **SAMRAS** structural sidebar when the resource is SAMRAS-backed (TXA, MSN, same code path)

Canonical body is always the **sandbox resource file** under `data/sandbox/resources/<id>.json`, not root-level `samras-*.legacy.json` files. Legacy files may still exist on disk for migration; the UI is driven by **shared API** payloads.

## API (source of truth)

| Action | Route |
|--------|--------|
| List sandbox files | `GET /portal/api/data/sandbox/resources` |
| List local index | `GET /portal/api/data/resources/local` |
| Load detail + workbench VM | `GET /portal/api/data/sandbox/resources/<resource_id>` |
| Stage | `POST .../stage` |
| Save | `POST .../save` |
| Compile | `POST .../compile` |
| SAMRAS sidebar refresh | `POST /portal/api/data/sandbox/samras_workspace/view_model` |

### Enriched `GET .../sandbox/resources/<id>`

Response now includes:

- `staged_present`, `staged_payload` — from `SandboxEngine.peek_stage_payload` (`sandbox/staging/*.stage.json`)
- `workbench` — `build_resource_workbench_view_model(...)` (anthology row summaries, SAMRAS `rows_by_address`, understanding brief, rule policy keys)
- `samras_workspace` — when `is_samras_backed_resource`, from `build_samras_workspace_view_model` (generic, not TXA-only)
- Existing: `resource`, `datum_understanding`, `rule_policy_by_id` when anthology-shaped rows exist

Schema id: `mycite.portal.sandbox.resource.detail.v1`

## Implementation files

- `_shared/portal/sandbox/resource_workbench.py` — workbench view-model  
- `_shared/portal/sandbox/engine.py` — `peek_stage_payload`  
- `_shared/portal/api/data_workspace.py` — enriched GET handler  
- `fnd` / `tff` `portal/ui/templates/services/system.html` — layout  
- `fnd` / `tff` `portal/ui/static/tools/local_resources_workbench.js` — client logic  
- `fnd/portal/ui/static/portal.css` — `.lr-workbench__*` styles  

## Tests

- `tests/test_resource_workbench_vm.py` — workbench VM + `peek_stage_payload`

## Follow-ups

- Wire **browser-staged SAMRAS titles** into this page (sessionStorage) if product wants parity with Data Tool.  
- Run **save-rule evaluation** feedback inline when `datum_rules` is returned on save failures.  
- Optional **diff** view between saved resource and `staged_payload`.
