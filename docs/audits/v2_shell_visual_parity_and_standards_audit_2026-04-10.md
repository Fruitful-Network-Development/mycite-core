# V2 Shell Visual Parity and Interface Surface Standards Audit

**Date:** 2026-04-10
**Scope:** Portal host template, CSS, JS shell renderer, admin runtime composition, nginx routing, deep-linking, and adherence to V2 standardized interface surface paradigm.

---

## 1. Problem Statement

The live portal at `portal.fruitfulnetworkdevelopment.com/portal` renders an unstyled status-dashboard page instead of the IDE-like shell layout (dark activity bar, control panel sidebar, workbench, inspector panel) visible in the V1 portal. The V2 paradigm was intended to preserve V1's visual arrangement while anchoring shell state in the runtime/composition layer rather than browser JavaScript.

Additionally, visiting `/portal/system` (a V1 deep-link) either redirects to sign-in or bootstraps to the generic home view, not to the intended system context. The V2 standardized interface surface goal --- modular, runtime-driven, composition-anchored regions --- was not fully realized in the deployed portal.

---

## 2. Audit Findings

### 2.1 Visual gap: deployed portal vs. repo

| Aspect | Deployed (screenshot) | Repo V2 template |
|--------|----------------------|-------------------|
| Layout | Flat white status cards, raw JSON | IDE grid: menubar + activity bar + control panel + workbench + inspector |
| CSS | Not loading or different template | `portal.css` (6600+ lines) includes full `.ide-*` layout, themes (paper/ocean/forest/midnight), dark sidebar, grid shell |
| JS | Minimal or absent | `v2_portal_shell.js` renders all regions from `shell_composition` |
| Activity bar | Absent | Dark column with runtime-driven nav items |
| Control panel | Absent | Sidebar with Admin surfaces / Shell-registered tools / Datum sections |

**Root cause:** The running service does not match the repo. Either the deployed unit is an older revision, or nginx upstream routes `/portal` to the V1 service (5101) instead of the V2 service (6101). The repo CSS and template produce the V1-like IDE layout when served correctly (verified via Flask test client and static route verification).

**Evidence:** `GET /portal/static/portal.css` returns 200 with correct CSS in test client. Template includes `data-portal-shell-driver="v2-composition"` and all IDE structural elements.

### 2.2 Deep-linking was missing

Prior state:
- `/portal`, `/portal/home`, `/portal/system` all rendered the same bootstrap request: `requested_slice_id: admin_band0.home_status`.
- No URL slug resolved to tool surfaces (AWS, datum, registry).
- V1's `/portal/system/mediate_tool-aws_platform_admin` had no V2 equivalent.

This violated the V2 paradigm: URL-addressable interface surfaces are a baseline requirement for modular development, because developers and operators need to link directly to specific tool surfaces.

### 2.3 Control panel included non-launchable tools

The `_control_panel_region` function emitted entries for all registered tools, including non-launchable (gated) ones with `shell_request: null`. The JS rendered these as clickable links that silently did nothing, violating the principle that shell-emitted navigation must be actionable or visibly gated.

### 2.4 Health endpoint lacked static bundle verification

The `/healthz` endpoint reported `ok: true` without checking that `portal.css` and `v2_portal_shell.js` exist on disk. A broken deploy (missing static files) would pass health checks but render an unstyled shell.

### 2.5 Nginx had no explicit static location

The nginx config for `portal.fruitfulnetworkdevelopment.com` routed all `/portal/*` through a single `location ^~ /portal` block. While this works, a future edit to that block (e.g. changing upstream logic) could silently break static asset delivery. Static assets deserve an explicit, defended routing rule.

### 2.6 Interface surface contract is implicit

The V2 paradigm promises "standardized interfacing surfaces for modularly separated components." In practice:

| Contract element | Status |
|-----------------|--------|
| Region schemas (`activity_bar`, `control_panel`, `workbench`, `inspector`) | Defined in `admin_shell.py` as string constants, but not as formal contracts |
| Workbench `kind` values (`home_summary`, `tool_registry`, `datum_workbench`, `tool_placeholder`, `tool_collapsed_inspector`, `error`) | Implicitly defined by JS switch/case; no schema or docs enumerate them |
| Inspector `kind` values (`empty`, `aws_read_only_surface`, `aws_tool_error`, `narrow_write_form`, `json_document`) | Same --- implicit in JS |
| Shell composition mode (`system`, `tool`) | Defined in `shell_composition_mode_for_surface` but not documented as a contract |
| URL slug contract | Was completely absent |

This means a new tool module developer would need to read `v2_portal_shell.js` and `admin_runtime.py` to understand what workbench/inspector kinds exist and what fields each requires. That is the opposite of a standardized surface.

---

## 3. Fixes Applied

### 3.1 URL deep-linking (`app.py`)

Added `URL_SLUG_TO_SLICE_ID` mapping and `_bootstrap_request_for_slug()` helper. URL paths now resolve to the correct `requested_slice_id` and `tenant_scope`:

| URL path | Bootstrap slice | Scope |
|----------|----------------|-------|
| `/portal`, `/portal/home` | `admin_band0.home_status` | internal |
| `/portal/system` | `admin_band0.home_status` | internal |
| `/portal/system/tools` | `admin_band0.tool_registry` | internal |
| `/portal/system/aws` | `admin_band1.aws_read_only_surface` | trusted-tenant |
| `/portal/system/aws-write` | `admin_band2.aws_narrow_write_surface` | trusted-tenant |
| `/portal/system/datum` | `datum.resource_workbench` | internal |
| `/portal/system/mediate_tool-aws_platform_admin` | `admin_band1.aws_read_only_surface` | trusted-tenant (V1 compat) |
| `/portal/system/<unknown>` | `admin_band0.home_status` | internal (fallback) |

The bootstrap request is built via `build_portal_activity_dispatch_bodies()`, the same function that produces activity bar and control panel navigation bodies, ensuring the URL deep-link uses the exact same request shape the runtime expects.

### 3.2 Gated control panel entries (`admin_runtime.py`, `v2_portal_shell.js`, `portal.css`)

Non-launchable tool entries now carry `gated: true`. The JS adds `is-gated` and `aria-disabled="true"` to the link element. CSS dims gated entries to 45% opacity and sets `pointer-events: none`, making the gated state visible and non-clickable.

### 3.3 Health endpoint static bundle check (`app.py`)

Health now verifies `portal.css` and `v2_portal_shell.js` exist on disk. If either is missing:
- `portal_static_bundle.static_ok` is `false`
- Overall `ok` is `false` (503 status)
- `portal_css_size_bytes` reports actual file size for quick sanity checks

### 3.4 Nginx explicit static location (`portal.fruitfulnetworkdevelopment.com.conf`)

Added `location ^~ /portal/static/` with its own auth + upstream logic (same tenant-aware 6101/6203 selection as `/portal`). This ensures static assets are always routed to the V2 service regardless of future edits to the broader `/portal` block.

---

## 4. What the CSS and Template Already Provide (V1 Visual Parity)

The repo template and CSS already produce the V1 IDE layout. No visual changes were needed. The deployed portal looks different solely because the deployed code does not match the repo.

The CSS layout at `portal.css:3628-3900` defines:

- `.ide-shell` as a full-viewport flex column with CSS custom properties for region widths
- `.ide-body` as a CSS grid: `activity | controlpanel | splitter | workbench | splitter | inspector`
- `.ide-activitybar` with dark background (#222), icons filtered to light, text-based navigation
- `.ide-controlpanel` with sections, links, search, and active/gated states
- `.ide-workbench` with `pagehead` header bar and scrollable viewport
- `.ide-inspector` with header, close button, and content regions
- `.ide-menubar` with dark menubar matching V1's File/Edit/Selection/View/Go/Run/Terminal/Help layout
- Theme support via CSS custom properties: paper, ocean, forest, midnight
- Responsive splitter-drag via `portal.js` `initWorkbenchLayout()`
- Composition-mode CSS: `[data-shell-composition="tool"]` hides workbench and expands inspector

### Template features matching V1:
- Logo in activity bar links to `/portal/system`
- Session footer with tenant, build ID, sign out
- Shell toggle buttons for Context and Interface Panel
- Theme selector dropdowns in menubar and pagehead
- `data-portal-shell-driver="v2-composition"` attribute triggers V2 JS behavior in `portal.js`

---

## 5. Auth for `/portal/system`

The OAuth2 proxy redirect when visiting `/portal/system` while unauthenticated is **correct and intentional**. All `/portal/*` routes require authentication via `auth_request /oauth2/auth` in the nginx config. This has been the case since the V2 cutover (doc 16). After sign-in, the user is redirected back to the requested URL.

The apparent "regression" from V1 is that V1 may have had a different session lifetime or the user's session expired. No code change is needed; the sign-in redirect is the correct security posture.

---

## 6. Remaining Work for Full Standards Compliance

### 6.1 Document the workbench/inspector kind contract

Create a formal contract document (suggested path: `docs/contracts/shell_region_kinds.md`) enumerating:
- Each `kind` value for workbench and inspector regions
- Required fields per kind
- Which composition modes each kind is valid in
- How a new tool module should register its own kind

### 6.2 Deploy the current repo revision

The visual gap between screenshots and repo is a deploy issue. After deploy:
1. `systemctl restart` the portal service on port 6101
2. Copy `portal.fruitfulnetworkdevelopment.com.conf` from `srv-infra/nginx/sites-available/` to the live nginx and `nginx -s reload`
3. Verify: `curl -sI https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css` returns `200 text/css`
4. Verify: `curl -s https://portal.fruitfulnetworkdevelopment.com/healthz | python3 -m json.tool` shows `portal_static_bundle.static_ok: true`
5. Optionally set `MYCITE_V2_PORTAL_BUILD_ID=<git-sha>` in the systemd unit environment

### 6.3 Add region kind registration for future tool modules

When new tools are added (maps, agro ERP), they will need to define their own workbench/inspector kinds. The current system requires editing `v2_portal_shell.js` to add rendering logic for each new kind. A more modular approach would be a kind registry or a standardized rendering protocol (e.g., all kinds share a common card/table/form vocabulary).

---

## 7. Test Coverage

| Test | File | Status |
|------|------|--------|
| Health includes `portal_static_bundle` | `test_v2_native_portal_host.py` | Pass |
| `/portal/system` renders V2 template with home slice | `test_v2_native_portal_host.py` | Pass |
| Deep-link `/portal/system/tools` bootstraps to registry | `test_v2_native_portal_host.py` | Pass |
| Deep-link `/portal/system/aws` bootstraps to AWS slice | `test_v2_native_portal_host.py` | Pass |
| Deep-link `/portal/system/datum` bootstraps to datum slice | `test_v2_native_portal_host.py` | Pass |
| V1 compat `/portal/system/mediate_tool-aws_platform_admin` | `test_v2_native_portal_host.py` | Pass |
| Unknown slug falls back to home | `test_v2_native_portal_host.py` | Pass |
| Static CSS returns 200 with IDE layout classes | `test_v2_native_portal_host.py` | Pass |
| Admin shell POST returns composition with all regions | `test_v2_native_portal_host.py` | Pass |
| Boundary: no V1 imports, no fallback nav | `test_v2_native_portal_host_boundaries.py` | Pass |
| Composition: shell chrome mediates inspector | `test_admin_runtime_composition.py` | Pass |
| State machine: request contract, catalog, launch | `test_state_machine_admin_shell.py` | Pass |
