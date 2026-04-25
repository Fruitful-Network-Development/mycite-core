# Code Bloat Shell Topology Findings

Date: 2026-04-25

Doc type: `audit-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-25`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-FINDINGS-EXECUTION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-FINDINGS-EXECUTION`
- Findings task ID: `TASK-CODE-BLOAT-FINDINGS-001`
- Upstream planning task ID: `TASK-CODE-BLOAT-AUDIT-001`
- Downstream remediation task ID: `TASK-CODE-BLOAT-REMEDIATION-001`
- Source audit plan:
  `docs/audits/code_bloat_shell_topology_audit_plan_2026-04-24.md`

## Scope

Audit the live portal shell topology to determine whether residual multi-shell
entrypoints, renderer-family branches, or historical host paths are still
active enough to justify code retirement work.

## Findings

### 1. Public shell topology is single-path

- `MyCiteV2/instances/_shared/portal_host/app.py` exposes one public HTML shell
  redirect (`/portal` -> `/portal/system`), one canonical shell JSON endpoint
  (`POST /portal/api/v2/shell`), three root routes, and the canonical tool
  route family `/portal/system/tools/<tool_slug>`.
- `MyCiteV2/packages/state_machine/portal_shell/shell.py` defines one approved
  surface catalog and one approved route for each live surface.
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py` already
  proves retired split shell artifacts are absent and legacy admin/tenant shell
  routes do not exist.

Disposition: no second live public shell was found.

### 2. Shell boot is single-chain, not multi-entry

- `portal.html` embeds one shell asset manifest and loads exactly:
  - `portal.css`
  - `portal.js`
  - `v2_portal_shell.js`
  - manifest-listed internal shell modules
- `v2_portal_shell.js` is the sole shell bootstrap loader. It reads the asset
  manifest, enforces module contracts, and loads internal shell modules.
- `v2_portal_shell_core.js` is the sole client runtime dispatcher that talks to
  `/portal/api/v2/shell` and owns `loadShell()` / `loadRuntimeView()`.
- `portal.js` is a chrome/layout helper for themes, splitters, and persisted
  shell layout state. It does not own shell fetching or runtime dispatch.

Disposition: the ambiguous artifact was `portal.js`, but it is not a parallel
shell runtime. It is a shared chrome asset and should remain documented as such.

### 3. Renderer dispatch is family-first, not tool-branch-first

- `portal_shell_runtime.py` uses `_TOOL_SURFACE_BUNDLE_BUILDERS` for tool bundle
  lookup rather than per-tool shell branch trees.
- `build_shell_composition_payload()` in `shell.py` normalizes first-load
  posture through one composition authority.
- Architecture tests confirm runtime and client dispatch stay constrained to the
  three canonical region families:
  - `directive_panel`
  - `reflective_workspace`
  - `presentation_surface`

Disposition: no residual alternate renderer family was found in the active
host/runtime boundary.

### 4. Remaining compatibility surfaces are explicit and allowed

- `portal_shell_contract.md` retains `inspector` as the compatibility alias for
  the public `Interface Panel`.
- `app.py` still redirects legacy AWS slugs to the canonical `aws-csm` route.
- CTS-GIS legacy `maps` identifiers are explicitly rejected rather than silently
  routed through a historical shell path.

Disposition: compatibility posture exists, but it is bounded and testable.

## Deletion Candidate Review

No active code deletion candidate met the audit bar for shell-topology
retirement. The repo already removed the previously dangerous split-shell
artifacts; what remained was documentation drift about which static assets are
authoritative and which aliases remain compatibility-only.

## Regression Gate Posture

Required gates for this area are now:

- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- `MyCiteV2/tests/architecture/test_portal_shell_stabilization_matrix.py`
- `MyCiteV2/tests/integration/test_portal_host_one_shell.py`

The added shell-bootstrap regression asserts that:

- `portal.js` does not become a second shell fetch/dispatch surface
- `v2_portal_shell_core.js` remains the only client module that calls the
  canonical shell endpoint

## Remediation Disposition

`TASK-CODE-BLOAT-REMEDIATION-001` can close on evidence. The audit found no
unretired alternate shell runtime to delete. The corrective work was to make
the single-path topology explicit in contract, to restore composition-owned
first-load posture for interface-panel-primary tools in
`build_shell_composition_payload()`, and to add regression guards so future
drift cannot reintroduce ambiguity.
