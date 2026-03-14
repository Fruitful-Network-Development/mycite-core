## Hosted shell, alias interface, and future subject-congregation hosting

This note describes how the **hosted shell** and **alias interface** work today and how they should evolve for future subject-congregation hosting styles. For the core shell layout (context / workbench / inspector), see also `[docs/PORTAL_SHELL_UI.md](PORTAL_SHELL_UI.md)`.

### 1. Alias shell routes

On FND (and similarly on TFF), the main alias entrypoint is:

- `GET /portal/alias/<alias_id>` in `runtime/flavors/fnd/app.py`

This route:

- lists aliases for the sidebar (via `list_aliases_for_sidebar(PRIVATE_DIR)`)
- loads the alias record (`get_alias_record(PRIVATE_DIR, alias_id)`)
- derives:
  - `progeny_type` (e.g. `member`)
  - `tenant_id` / `child_msn_id`
  - `alias_host` / `host_title`
- renders `alias_shell.html` with:
  - a host/organization header
  - a widget URL pointing to the embedded member board or hosted view
  - the **alias progeny type** and **tenant id** that hosted pages use to select layout

The shell itself is intentionally thin: it knows how to render navigation and an iframe/embedded workbench, but it does not know about contracts, MSS, or analytics.

### 2. Hosted shell and subject-congregation

Hosted pages are defined by:

- `private/network/hosted.json` (normalized via `portal.hosted_model.normalize_hosted_payload`)
- per-progeny templates under `hosted.progeny.templates.*.hosted_interface`
- per-instance overrides in progeny instance files (for example FND’s member progeny with `layout: "classroom_orientation"`)

The **subject-congregation** model provides:

- a shared set of tabs (e.g. `stream`, `discover`, `calendar`, `workflow`)
- an orientation style (currently `google_classroom_reference`)
- per-progeny tab lists (for example, workflow only for member progeny)

The shell uses:

- the alias’ `progeny_type`
- the hosted payload’s templates and tabs

to decide which subject-congregation view to render.

### 3. Current breakage and direction (TFF)

On TFF, the alias interface is currently not wired to the new hosted metadata and subject-congregation defaults. Fixing it should:

- reuse the same pattern as FND:
  - alias → contract → progeny instance → hosted template
- avoid one-off patches that bypass `hosted.json` or `hosted_model`
- align tabs and layouts with the shared defaults (stream/discover/calendar/workflow) unless TFF explicitly overrides them in its own hosted payload

This means future work on TFF’s alias shell should start by:

- ensuring `private/network/hosted.json` exists and is normalized
- using `portal.hosted_model.read_hosted_payload` and `get_progeny_template`
- following the same `/portal/alias/<alias_id>` routing conventions as FND

### 4. Future subject-congregation hosting

The current style (`google_classroom_reference`) is one subject-congregation layout. Future hosting styles (for example a more minimal “board” or a multi-column dashboard) should:

- continue to use `hosted.json` as the canonical config
- define:
  - a `type` and `style`
  - a tab list and top-level pages
  - optional per-progeny overrides
- keep the alias shell generic so it:
  - reads `hosted.type` / `hosted.subject_congregation.style`
  - renders the appropriate layout (classroom, board, etc.)
  - routes tab clicks to the correct backend pages

In all cases, the **session binding** remains:

`alias` → `contract` → `progeny instance` → `hosted template` → `subject-congregation layout and tabs`.

Hosted pages (discover, calendar, workflow, etc.) remain responsible for their own data loading and inheritance rules; the shell only orchestrates which page is active and how it is framed.

For the consolidated shell design and UX checklist that apply to SYSTEM and other shell-based workbenches (including hosted alias views), see:

- `[docs/PORTAL_SHELL_UI.md](PORTAL_SHELL_UI.md)`
- `[docs/HOSTED_SESSIONS.md](HOSTED_SESSIONS.md)`

