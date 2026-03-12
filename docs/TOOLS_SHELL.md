# IDE Shell Standard

## Locked Shell Layout

All runnable portals (`mycite-le_fnd`, `mycite-le_tff`, `mycite-ne_mt`) use one shared IDE-style shell in `portal/ui/templates/base.html`:

- Menu bar (visual-only): `File`, `Edit`, `Selection`, `View`, `Go`, `Run`, `Terminal`, `Help`
- Activity bar (global service navigation)
- Left context sidebar (page-aware)
- Workbench (main content)
- Right inspector/drawer (collapsible, contextual)

Persistent navigation remains on the left. Focused inspection/editing opens on the right.

## Route Model

Canonical shell routes:

- `GET /portal` -> redirect to `GET /portal/system`
- `GET /portal/system`
- `GET /portal/network`
- `GET /portal/utilities`
- `GET /portal/peripherals`

Compatibility redirects are preserved:

- `GET /portal/home` -> `/portal/system`
- `GET /portal/data` (+ legacy subpaths) -> `/portal/system`
- `GET /portal/tools` -> `/portal/peripherals?tab=tools`
- `GET /portal/inbox` -> `/portal/utilities?tab=inbox`
- `GET /portal/peripheral` -> `/portal/peripherals?tab=peripherals`
- `GET /portal/network/<legacy_tab>` -> `/portal/network?view=...`

The shell logo routes to `GET /portal/system` and uses `assets/icons/logos/fnd.svg`.

## Activity Bar

Primary activity entries are:

- `NETWORK`
- `UTILITIES`
- `PERIPHERALS`
- `SYSTEM`

Legacy top-level entries (`INBOX`, `ALIASES`, `TOOLS`, `PROGENY`) are not separate activity-bar items.

Session actions in the activity footer:

- `Switch Active Portal`
- `Sign Out`

## Page Model

### NETWORK

`NETWORK` uses a Discord-like interaction model:

- left context sections: `Alias Interfaces`, `Request Logs`, `P2P`
- workbench updates from selected alias/log/P2P item
- profile/contact-card inspection opens in the right inspector

### UTILITIES

`UTILITIES` hosts utility surfaces only:

- `Inbox`
- `Launchers` (tools mounted to `utilities`)

Utilities consume the core shell and do not redefine it.

### PERIPHERALS

`PERIPHERALS` is tabbed:

- `Tools`
- `Peripherals`
- `Progeny`
- `Configuration`
- `Vault`

Tools in this page are mounted through extension metadata (`peripherals.tools`).

### SYSTEM

`SYSTEM` is the shell home/splash context:

- left context sidebar is profile-oriented
- workbench hosts current data-facing workspace
- profile/data detail panels open in the right inspector

## Inspector Model

Global inspector runtime is provided in `portal/ui/static/portal.js` (`window.PortalInspector`):

- `open(payload)`
- `close()`
- `toggle(payload)`
- `openTemplate(templateId, title, subtitle)`

Pages inject contextual content by template or payload. Datum investigation can be opened from the data workbench and shown in this right-side inspector.

## Extension-Point Rule

Tools are mounted through shared runtime (`portals/_shared/portal/tools/runtime.py`) and must not fork shell layout/routes.

Optional per-portal manifest:

- `private/tools.manifest.json`

Supported mount targets:

- `utilities`
- `peripherals.tools`

One-off portal tools are consumers of shell slots and routes, not alternate shells.
