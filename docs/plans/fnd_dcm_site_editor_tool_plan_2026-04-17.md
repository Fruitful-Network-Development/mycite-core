# FND-DCM Tool Plan (Manifest Site Editor in One-Shell Portal)

## Purpose

Translate the proposed manifest-driven Site Editor concept into the **current one-shell portal paradigm** used in this repo, so `FND-DCM` can be added as a `SYSTEM` child tool surface without introducing a separate CMS runtime.

This plan is implementation-oriented and maps directly to existing shell/runtime extension points.

---

## Current Paradigm Constraints (from this repo)

1. Tools are modeled as `SYSTEM` child surfaces with explicit surface ids/routes in the shell state machine.  
2. Tool defaults are interface-panel-led (`surface_posture=interface_panel_primary`) with workbench optional/secondary evidence.  
3. Routing, activity-bar visibility, and tool exposure all derive from the surface catalog + tool registry, not ad-hoc routes.  
4. Shared runtime envelope composition happens in `portal_shell_runtime.py`, where tool bundles are attached per active surface.  
5. The shell already has a generic wrapped renderer for loading/error/empty/unsupported states, which should be reused for first-pass FND-DCM bring-up.

---

## Target Tool Shape

- **Tool id:** `fnd_dcm`
- **Surface id:** `system.tools.fnd_dcm`
- **Entrypoint id:** `portal.system.tools.fnd_dcm`
- **Route:** `/portal/system/tools/fnd-dcm`
- **Label:** `FND-DCM`
- **Kind:** service/general tool (recommend service if it depends on hosted-site integrations)
- **Default posture:** `interface_panel_primary`
- **Read/write posture:** `read-write` (because draft/edit/publish are first-class)

---

## Architecture Mapping for the Site-Editor Workflow

### 1) Select/Edit/Media state model

Use tool-local body state (`tool_state`) rather than widening shell depth beyond `sandbox/file/datum/object`.

Recommended `tool_state` skeleton:

```json
{
  "active_site_id": "trappfamilyfarm.com",
  "selected_node": {
    "node_id": "pages.home.content.lead",
    "field": "heading",
    "type": "text"
  },
  "selection": {
    "manifest_path": "pages.home.content.lead.heading"
  },
  "preview": {
    "last_rendered_at": "2026-04-17T00:00:00Z",
    "url": "/portal/tools/site_builder/preview/trappfamilyfarm.com/index.html"
  },
  "draft": {
    "dirty": true,
    "version": 7
  }
}
```

### 2) Draft/Preview/Publish persistence

Adopt portal state storage convention under instance state:

- `state/<portal>/data/site_editor/projects/<site-id>/draft/manifest.json`
- `state/<portal>/data/site_editor/projects/<site-id>/assets/*`
- `state/<portal>/data/site_editor/projects/<site-id>/history/*.json`

Keep live manifest unchanged until publish.

### 3) Backend endpoints (thin wrappers)

Create/extend host endpoints:

- `GET /portal/tools/site_builder/session/:site`
- `PATCH /portal/tools/site_builder/draft`
- `POST /portal/tools/site_builder/upload`
- `POST /portal/tools/site_builder/render`
- `POST /portal/tools/site_builder/publish`
- `GET /portal/tools/site_builder/history`

Implementation should call existing render pipeline (`render_manifest.py` + `site_builder.build_site`) rather than introducing a second renderer.

### 4) UI region ownership under one-shell

- **Interface Panel (primary):** inspector/editor controls for selected manifest node.
- **Workbench (secondary):** preview iframe + optional diff/history cards.

This matches existing one-shell tool posture and avoids custom full-screen tool chrome.

---

## Concrete Repo Changes (Phase Plan)

## Phase A — Register FND-DCM surface in shell contracts

1. Extend `MyCiteV2/packages/state_machine/portal_shell/shell.py`:
   - add constants for `FND_DCM_TOOL_SURFACE_ID`, `FND_DCM_TOOL_ENTRYPOINT_ID`, `FND_DCM_TOOL_ROUTE`
   - include in `TOOL_SURFACE_IDS` and `SYSTEM_SURFACE_IDS`
   - add surface catalog entry (`build_portal_surface_catalog`)
   - add tool registry entry (`build_portal_tool_registry_entries`)
   - map icon id in `activity_icon_id_for_surface`

2. Export new constants via `__all__` in the same module for runtime imports.

## Phase B — Runtime envelope + bundle wiring

1. Add runtime builder module:
   - `MyCiteV2/instances/_shared/runtime/portal_fnd_dcm_runtime.py`

2. In `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`:
   - import runtime builder
   - include FND-DCM in activity visibility/tool posture rows
   - dispatch `active_surface_id == system.tools.fnd_dcm` to FND-DCM bundle builder

3. Bundle payload should start with generic shape:
   - readiness
   - warnings
   - control-panel group entries for site/project selection
   - interface/workbench payload schemas already used by tool surfaces

## Phase C — Front-end renderers (minimal viable UI)

1. Add renderer file:
   - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_fnd_dcm_workspace.js`

2. Load file through host shell asset manifest in app/template wiring.

3. Hook into:
   - `v2_portal_workbench_renderers.js` for `surface_payload.kind === "fnd_dcm_workspace"`
   - `v2_portal_inspector_renderers.js` for `interface_body.kind === "fnd_dcm_inspector"`

4. Reuse `v2_portal_tool_surface_adapter.js` wrapper states for initial robustness.

## Phase D — Site editor server API + rendering integration

1. Add host API handlers in `portal_host/app.py` (or delegated helper module).
2. Implement draft patch support with strict manifest path validation.
3. Implement preview render using existing site scripts.
4. Implement publish promotion with append-only publish log.

## Phase E — Manifest compatibility refinements

1. Introduce optional manifest conventions:
   - `enabled` booleans
   - `editor` metadata hints (`label`, `type`, `visible_if`, `group`)
   - stable `id` for list objects
2. Make renderer tolerate missing metadata by deriving fallback field types.

---

## Rendering Instrumentation Strategy

For preview-select parity, augment generated HTML nodes with:

- `data-editor-node="pages.home.content.lead"`
- `data-editor-field="heading"`
- `data-editor-type="text"`

Required rule: attributes are additive and must not alter existing class/semantic output used by live site styles.

---

## Validation + Guardrails

1. **Draft path safety:** only allow updates under approved root keys (`shell`, `nav`, `pages`, `icons`, etc.).
2. **Asset safety:** validate extension/content-type and normalize destination paths.
3. **Publish safety:** require successful preview render before publish.
4. **Auditability:** record actor, timestamp, site id, changed paths, and output hash.

---

## Testing Strategy

1. Unit tests (shell contract):
   - tool registry includes `fnd_dcm`
   - route/surface resolution for `/portal/system/tools/fnd-dcm`

2. Runtime tests:
   - FND-DCM surface returns interface-panel-led composition by default
   - envelope includes expected `fnd_dcm_workspace`/inspector payload kinds

3. Integration tests:
   - GET session, PATCH draft, POST render, POST publish happy path
   - publish blocked on invalid manifest patch

4. Front-end behavior checks:
   - selecting preview node populates inspector controls
   - text/image/toggle edits persist in draft and re-render preview

---

## Minimal MVP Definition

MVP is complete when:

1. `/portal/system/tools/fnd-dcm` is reachable via activity/tool navigation.
2. User can select an element in preview and edit text + image path + `enabled` toggle.
3. Render Preview produces updated iframe output from draft manifest.
4. Publish promotes draft manifest/assets and records history.

---

## Notes on Terminology

- Keep public shell terms as: **Control Panel**, **Workbench**, **Interface Panel**.
- Keep FND-DCM internal terminology aligned to manifest concepts (`node`, `field`, `path`, `draft`, `publish`).
- Avoid introducing alternate nav/focus depth models; use existing one-shell focus stack plus tool-local state.
