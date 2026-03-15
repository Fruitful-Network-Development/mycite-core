## Portal shell UI model (context / workbench / inspector)

For portal-wide drift, consolidation, and modularization, see [MYCITE_CORE_DEVELOPMENT_REPORT.md](MYCITE_CORE_DEVELOPMENT_REPORT.md).

This document records the **intended behavior** of the shared portal shell and its layout columns. It is a design target for the FND/TFF flavors and any future portals.

### 1. Shell mental model

- **Left sidebar – context**
  - Primary role: navigation and lightweight editing for the *currently focused* context (e.g. anthology rows, contracts, tool-specific entities).
  - Contains contextual lists, filters, and a compact editor for the selected item.
  - Can be toggled open/closed via a single “Sidebar” (workbench stays stable; inspector opens from context only).
- **Center – workbench**
  - Primary role: main content and interaction surface (tables, graphs, hosted tabs, tools).
  - Must remain **visible whenever possible**; sidebars should shrink or become overlays before the workbench disappears.
  - Uses the existing `ide-workbench` container and `viewport` sections in `base.html`.
  - When the current path is a tool route (`/portal/tools/<tool_id>/...`), the shell treats the active context as that tool (that tool is highlighted in the activity bar, and the left sidebar shows the tool-use section with “Using &lt;name&gt;” and “Configure tools”), not utilities.
- **Right sidebar – inspector**
  - Primary role: optional, richer “details” pane for inspecting or editing the focused item.
  - Should **open contextually** (when a user clicks an “Inspect” affordance) rather than via a global toggle.
  - May be hidden entirely on small screens or when not in use.

In VS Code terms, the left sidebar is the Explorer/Outline plus a small editor, the center is the editor group, and the right inspector is the optional details or problems pane.

### 2. Network page sidebar policy

Navigation for the Network page (Messages, Hosted, Profile, Contracts) is **tabs only**; the left context sidebar must not duplicate these as a "Network Views" section.

- **Do not** render "Network Views" (Messages / Hosted / Profile / Contracts) in the sidebar; the page tabs control that navigation.
- **Do not** render a "Contracts" list in the sidebar; contract list and "New Contract" belong under the Contracts tab (and optionally in the inspector).
- **Do not** render "Request Logs" as a separate sidebar section; the request log is the underlying feed for the Messages tab. Messages (and Direct Messages) are filtered views over that feed; users switch via the existing kind filter (alias / p2p / log) in the Messages tab.
- **Alias Interfaces** in the sidebar: only when the portal **hosts** alias profiles (e.g. TFF). FND does not host alias profiles; it provides progeny interfaces for aliases hosted on TFF, so FND must **omit** the "Alias Interfaces" section from the Network sidebar entirely.
- **Direct Messages** (P2P channels) may remain in the sidebar as the only Network-specific context list; the right-hand inspector can show relationship/contract details for the selected thread.

Implementation: `_context_sidebar_sections(active_service)` in each flavor’s `app.py` builds the sidebar; for `active_service == "network"` it must return only the sections that match the above (e.g. Direct Messages only on FND; Alias Interfaces + Direct Messages on TFF when aliases exist).

### 3. Current implementation snapshot

Shared across FND and TFF (layout only; Network sidebar content follows §2):

- Templates:
  - `[portals/_shared/runtime/flavors/fnd/portal/ui/templates/base.html]`
  - `[portals/_shared/runtime/flavors/tff/portal/ui/templates/base.html]`
  - Both define:
    - an `.ide-activitybar` (SYSTEM/NETWORK/UTILITIES),
    - `.ide-contextsidebar`, `.ide-workbench`, and `.ide-inspector` columns,
    - a **context splitter** (`data-splitter="context"`) between context and workbench so the left sidebar is resizable like the right,
    - an **inspector splitter** (`data-splitter="inspector"`) between workbench and inspector.
    - No menubar Sidebar/Inspector toggles; the inspector opens only from context/sidebar actions.
- Shell JS:
  - `[portals/_shared/runtime/flavors/fnd/portal/ui/static/portal.js]`
  - `[portals/_shared/runtime/flavors/tff/portal/ui/static/portal.js]`
  - `initWorkbenchLayout()` configures:
    - column widths via CSS vars `--ide-context-w`, `--ide-inspector-w`,
    - `rebalanceWorkbench()` which:
      - respects `MIN_CONTEXT_WIDTH`, `MIN_INSPECTOR_WIDTH`, `MIN_WORKBENCH_WIDTH = 720`,
      - bails out entirely below `max-width: 960px`,
      - toggles the unused `ide-shell--workbench-tight` class when the workbench is too small.
  - Inspector logic:
    - uses `data-inspector-close` to close the inspector; there is no global Inspector toggle (inspector opens from context/sidebar actions only),
    - opens when the user selects a datum or uses an "Inspect" affordance from the context sidebar.
- Shell CSS:
  - `[portals/_shared/runtime/flavors/fnd/portal/ui/static/portal.css]` (and TFF copy) define:
    - high-level layout and themes,
    - activity bar, context, and workbench styling,
    - responsive behavior via `@media (max-width: 960px)` that tends to overlay the inspector on top of the workbench.
  - There is **no style definition** for `.ide-shell--workbench-tight`, so cramped layouts are not handled explicitly.

Implication for users:

- **No menubar toggles** for Sidebar or Inspector; the workbench stays stable and is not squeezed when the inspector opens.
- The left sidebar holds context (e.g. System Views, Anthology Workbench); datum details and inspection are opened from the workbench or sidebar, and the right inspector shows details only when opened that way.

### 4. Target behavior (design)

#### 3.1 Controls

- **Header**
  - No Sidebar or Inspector toggles in the menubar; the context sidebar is always shown (unless collapsed by future per-page logic), and the inspector opens only via context actions (e.g. selecting a datum, or an "Inspect" action from the sidebar).
- **Left sidebar**
  - When a datum is selected in the workbench (e.g. a row in the SYSTEM Anthology table), the sidebar shows a small editor for that datum (fields, quick actions).
  - The sidebar can expose a secondary “Inspect” button/icon per item to open the full inspector when needed.
- **Inspector**
  - Opens when `open(payload)` is called by a concrete UI action (e.g. clicking “Inspect”).
  - Closes on:
    - clicking the inspector “Close” button,
    - pressing ESC while focus is inside the inspector,
    - or optionally when the focused context clears.

#### 3.2 Layout and responsiveness

- Maintain three logical regions for desktop widths:
  - **Context**: >= 220 px where possible.
  - **Workbench**: >= 720 px target; if space is limited, **do not collapse to zero**.
  - **Inspector**: >= 280 px where possible.
- `rebalanceWorkbench()` should:
  - continue to run down to a lower breakpoint (e.g. 768 px) instead of bailing at 960 px;
  - preferentially shrink inspector width, then context width, and only then consider turning a sidebar into an overlay;
  - add `ide-shell--workbench-tight` when the center column is below the ideal width, so CSS can apply tighter spacing.
- On **very small** viewports:
  - allow one of the sidebars (typically the inspector) to become an overlay,
  - keep the workbench visible as the base layer,
  - require explicit user action to show the overlay and to dismiss it.

### 5. Shared shell refactor plan (high level)

- Introduce a shared base template:
  - `[portals/_shared/portal/ui/templates/base_shell.html]`
  - Contains:
    - the menubar + layout controls,
    - activity bar,
    - context/sidebar/workbench/inspector columns and splitters.
  - Defines Jinja blocks for:
    - flavor‑specific navigation (SYSTEM/NETWORK/UTILITIES entries, icons),
    - flavor‑specific footer and brand.
- Introduce a shared JS module:
  - `[portals/_shared/portal/ui/static/portal_shell.js]`
  - Exposes `initShell({ shellSelector, contextSelector, inspectorSelector, bodySelector })` and returns:
    - `setContextOpen(bool)`, `setInspectorOpen(bool)`,
    - `rebalance()`,
    - event hooks for context/inspector open/close.
  - FND/TFF `portal.js` files become thin wrappers that:
    - call `portal_shell.initShell(...)` on DOMContentLoaded,
    - wire any flavor-specific behavior (e.g. alias filters, local tabs).
- Migration path:
  - FND/TFF `base.html` templates extend `base_shell.html` and drop duplicated layout code.
  - When changing shell behavior (e.g. inspector lifecycle), only `portal_shell.js` and `base_shell.html` need to be updated.

### 6. Context/inspector behavior (detailed)

- **Selection → context**
  - Clicking a row, node, or item in the workbench updates the left sidebar’s context editor immediately.
  - The shell provides a generic event bus or helper for tools (e.g. Anthology Workbench, AGRO‑ERP) to publish “selected datum” information.
- **Selection → inspector (optional)**
  - Tools can add an “Inspect” action that calls into `portal_shell.openInspector(payload)` which:
    - sets `data-inspector-collapsed="false"`,
    - updates the inspector header/title,
    - injects content into `#portalInspectorContent` (either via templates or client-side rendering).
  - The global *Inspector* menubar toggle is not required in this model.

### 7. Responsive & CSS notes

- Define `.ide-shell--workbench-tight` in `portal.css` to:
  - slightly reduce padding and gaps in the workbench,
  - optionally decrease font sizes for headers in tight states,
  - make the inspector header more compact.
- Adjust `@media` rules so that:
  - below ~960 px, columns can still coexist as long as the workbench is >= a configurable minimum,
  - below a smaller breakpoint (e.g. 768 px), the inspector becomes an overlay that slides over the right edge while leaving a visible workbench background.

### 8. UX checklist for SYSTEM and other workbenches

Use this checklist when evaluating or updating shell-based pages:

- **Workbench visibility**
  - [ ] On common desktop widths, the central workbench is always visible, even when both sidebar and inspector are open.
  - [ ] On smaller widths, at least one of the sidebars can be closed or overlaid without losing the ability to see and interact with the workbench.
- **Sidebar behavior**
  - [ ] Left sidebar shows navigation and a compact editor for the currently selected context.
  - [ ] Users can collapse/expand the sidebar from a single header control.
- **Inspector behavior**
  - [ ] There is no mandatory global *Inspector* toggle; inspector opens via context actions.
  - [ ] Closing the inspector does not disrupt the current selection or sidebar state.
- **Consistency across portals**
  - [ ] FND and TFF share the same base shell and JS behavior.
  - [ ] Flavor-specific differences are limited to navigation entries, branding, and default themes.

