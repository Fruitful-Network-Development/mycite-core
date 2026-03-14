# MyCite portal core: development report

This report summarizes the current state of the MyCite portal core, identifies drift and legacy code, and recommends hardening and modularization. It is intended to guide consolidation and to keep portal implementations aligned.

**Related docs:** [PORTAL_SHELL_UI.md](PORTAL_SHELL_UI.md), [HOSTED_SHELL_ALIAS.md](HOSTED_SHELL_ALIAS.md), [PORTAL_BUILD_SPEC.md](PORTAL_BUILD_SPEC.md).

---

## 1. Current layout

### 1.1 Directory structure

```
portals/
├── _shared/
│   ├── portal/                    # Core library (API, services, MSS, data_engine, tools)
│   │   ├── api/, services/, mss/, data_engine/, tools/, progeny_model/, ...
│   │   └── (no UI templates or static assets)
│   └── runtime/
│       └── flavors/
│           ├── fnd/                # FND flavor (Fruitful Network Development)
│           │   ├── app.py
│           │   ├── data/
│           │   └── portal/ (api, ui/templates, ui/static)
│           └── tff/                # TFF flavor (The Fruitful Fellowship)
│               ├── app.py
│               ├── data/
│               └── portal/ (api, ui/templates, ui/static)
├── mycite-le_fnd/, mycite-le_tff/, mycite-le_example/   # Portal roots (build.json, README)
├── runtime/                        # Entry: app.py loads flavor from PORTAL_RUNTIME_FLAVOR
└── scripts/                       # portal_build.py, etc.
```

- **`_shared/portal/`**: shared Python library only; no `base.html`, `portal.js`, or `portal.css`.
- **`_shared/runtime/flavors/{fnd,tff}/`**: each has its own `app.py`, `data/`, and `portal/` (templates, static, API, services).
- **Portal roots** are thin (build config + README); runtime is loaded from `portals/runtime/app.py` → flavor `app.py`.

### 1.2 Where key assets live

| Asset        | _shared | FND flavor | TFF flavor |
|-------------|---------|------------|------------|
| base.html   | No      | Yes        | Yes        |
| portal.js   | No      | Yes        | Yes        |
| portal.css  | No      | Yes        | Yes        |
| app.py      | No      | Yes        | Yes        |

Static files are served from each flavor’s `portal/ui/static` via Flask `static_folder` and `static_url_path="/portal/static"`.

---

## 2. Drift and duplication

### 2.1 Templates

- **base.html**: FND and TFF were structurally different (FND had an `activity_tool_nav` block, TFF did not). Both are now aligned: the same conditional block exists in both so that tool links in the activity bar are optional and structure stays identical. Keep both files in sync when changing shell layout.
- **portal.js / portal.css**: At last check these were **identical** between FND and TFF. Any fix or feature must be copied to both or they will drift. Recommendation: maintain a single canonical copy (e.g. under `_shared`) and either serve from there or copy in a build step.

### 2.2 app.py duplication

Both flavor `app.py` files contain large overlapping logic. Good candidates for shared modules:

| Area | Examples | Suggested shared location |
|------|----------|----------------------------|
| **Network/contract** | `_network_contract_items`, `_network_sidebar_alias_items`, `_network_message_feed`, `_p2p_channels`, `_request_log_channels`, `_iter_request_log_records`, `_network_placeholder_item`, contract preview/resolved refs | `_shared/portal/network_contract.py` or `_shared/runtime/shared_network.py` |
| **Sidebar/context** | `_context_sidebar_sections` (with flavor flags: e.g. show_alias_section, show_progeny), `list_aliases_for_sidebar`, alias label/format helpers | `_shared/portal/sidebar_context.py` |
| **Widget URL** | `_build_widget_url` (base URL, progeny_type, tenant/member embed paths) | `_shared/portal/embed_urls.py` or extend `progeny_embed` |
| **Profile/vault/IO** | `_read_json`, `_write_json`, anthology path, profile resolve/sanitize, `_options_public` / `_options_private`, vault inventory and contract files | `_shared/portal/app_io.py` + flavor-specific option builders |
| **Event formatting** | `_format_event_timestamp`, `_initials`, `_event_actor_label`, `_event_summary`, `_iter_string_values`, `_event_contains_any`, `_event_channel_id` | `_shared/portal/request_log_ui.py` |
| **Alias/label** | `_alias_label`, `_canonical_progeny_type`, `_extract_tenant_msn_id`, `_extract_contract_id`, `_extract_member_msn_id`, `_alias_contact_collection_ref` | `_shared/portal/alias_utils.py` |

Moving these into `_shared/portal/` (or a small `_shared/runtime/` helper) would reduce duplication and keep behavior consistent. Flavor `app.py` would then call shared helpers and pass flavor-specific config (e.g. `show_alias_section=False` for FND).

### 2.3 Legacy and retired code

- **Retired tools**: `legacy_admin`, `paypal_demo` are in `RETIRED_TOOL_IDS` in `portals/scripts/portal_build.py` and still listed in each portal’s `build.json` under `peripherals.tools.enabled`. The build script filters them out so they are not activated. **Hardening:** When no longer needed, remove them from `build.json` and from `RETIRED_TOOL_IDS`; delete or archive tool directories under FND if present.
- **Legacy routes**: Redirects such as `/portal/peripherals` → `/portal/utilities`, `/portal/peripheral` → `/portal/utilities?tab=peripherals`, `/portal/tools` → `/portal/utilities?tab=tools`, and `/portal/data/<path:tab_id>` → `/portal/system` remain for backward compatibility. Document which callers (if any) still use them; consider deprecation headers or removal once unused.
- **Data workspace legacy shims**: `register_data_routes(..., include_legacy_shims=True)` on TFF registers deprecated endpoints (`/portal/api/data/tables`, `/portal/api/data/table/<id>/instances`, etc.). FND uses `include_legacy_shims=False`. **Hardening:** Migrate any TFF clients to the non-legacy data API and set TFF to `include_legacy_shims=False` so both flavors are aligned and legacy surface is minimal.
- **Legacy paths in code**: `runtime_paths.py` and other modules reference `legacy_request_log_dir`, `legacy_progeny_dir`, etc. These support migration from old layouts. Keep until migration is complete, then remove or fold into a single path strategy.
- **Contract/request log**: Contract handshake and progeny code still mention “legacy” URL and alias field migration. Document the migration state and remove legacy branches once all instances are updated.

---

## 3. Hardening recommendations

### 3.1 Already done (or in progress)

- **Network sidebar**: Navigation (Messages, Hosted, Profile, Contracts) is tabs-only; “Network Views”, “Contracts”, and “Request Logs” are no longer duplicated in the left sidebar. FND omits “Alias Interfaces”; TFF shows it only when alias records exist. See [PORTAL_SHELL_UI.md §2](PORTAL_SHELL_UI.md).
- **Alias widget URL**: `_build_widget_url` uses the request host when available so the organization session iframe works when the portal is accessed via a non-localhost URL. See [HOSTED_SHELL_ALIAS.md](HOSTED_SHELL_ALIAS.md).
- **Base template structure**: FND and TFF `base.html` now share the same activity-bar structure with an optional `activity_tool_nav` block so they can stay in sync.

### 3.2 Recommended next steps

1. **Single source for shell static assets**  
   Put canonical `portal.js` and `portal.css` in one place (e.g. `_shared/portal/ui/static/` or a dedicated `portals/shell_assets/`). Either:
   - Have the Flask app serve static from that directory when the path is `portal.js` or `portal.css` (e.g. try flavor static dir first, then shared), or
   - Add a build or sync step that copies (or symlinks) from the canonical location into each flavor’s `portal/ui/static/`.  
   This prevents shell behavior from drifting between FND and TFF.

2. **Shared base template**  
   Introduce a shared base shell template (e.g. `_shared/portal/ui/templates/base_shell.html`) that contains the common layout and blocks (including the optional `activity_tool_nav`). FND and TFF `base.html` would extend it and only override or fill blocks that differ (e.g. logo, theme). This requires adding the shared template directory to the Flask/Jinja loader so templates can `{% extends "base_shell.html" %}`.

3. **Extract shared app helpers**  
   Move the duplicated logic listed in §2.2 into `_shared/portal/` (or a small runtime shared module). Start with one area (e.g. event formatting or sidebar sections) and wire flavor `app.py` to it; then repeat for the rest. This reduces duplication and keeps behavior consistent.

4. **Align TFF with FND on data workspace**  
   Set TFF to `include_legacy_shims=False` once no clients depend on the deprecated data endpoints. Document the cutoff in the release notes or migration guide.

5. **Retired tools cleanup**  
   Remove `legacy_admin` and `paypal_demo` from `build.json` and from `RETIRED_TOOL_IDS` when they are no longer required; remove or archive their tool directories under the FND flavor.

6. **Legacy route audit**  
   List all legacy redirects and deprecated API paths; add a short “Legacy routes” section to this doc or to PORTAL_BUILD_SPEC. Plan removal or long-term deprecation and communicate to API consumers.

---

## 4. Modularization suggestions

### 4.1 Shared portal library (`_shared/portal/`)

- **Already shared**: `api/`, `services/`, `mss/`, `data_engine/`, `tools/specs.py`, `hosted_model.py`, `progeny_model/`, `datum_refs.py`, etc.
- **Add (from flavor app.py)**:
  - **network_contract.py** (or **shared_network.py**): contract list, network sidebar items, message feed, p2p/request_log channels, placeholder item.
  - **sidebar_context.py**: build context sidebar sections from a small flavor config (e.g. show_alias_section, show_progeny_in_utilities).
  - **embed_urls.py** (or inside **progeny_embed**): build embed/widget URL from alias payload and request (with fallback to 127.0.0.1 when no request).
  - **request_log_ui.py**: event timestamp, initials, actor label, summary, and any event-iteration helpers.
  - **alias_utils.py**: alias label, canonical progeny type, extract tenant/contract/member IDs, contact collection ref.

Flavor `app.py` would import these and pass flavor-specific options (e.g. `portal_instance_id`, feature flags).

### 4.2 Shell UI

- **Templates**: One shared base shell template with blocks; flavor templates extend it. Reduces duplicate layout and keeps shell behavior consistent.
- **Static**: One canonical set of shell assets (JS/CSS) with a clear update path (single copy or sync from _shared).
- **Behavior**: Documented in [PORTAL_SHELL_UI.md](PORTAL_SHELL_UI.md); implement shared `portal_shell.js` and optional `base_shell.html` as in that doc so FND and TFF stay aligned.

### 4.3 Build and runtime

- **Build**: `portal_build.py` already uses `_shared` (e.g. hosted_model). Keep build output (e.g. `private/network/hosted.json`) as the contract for runtime.
- **Runtime**: Flavor is selected by `PORTAL_RUNTIME_FLAVOR`; a single entrypoint loads the chosen flavor’s `app.py`. No change needed; optional shared “runtime common” module could hold any code that is identical across flavors and not part of `_shared/portal/`.

---

## 5. Repo and container update commands

Use these to pull back drift, apply changes, and refresh running services.

### 5.1 Git (mycite-core)

```bash
# From repo root
cd /srv/repo/mycite-core

# Ensure you're on the right branch and pull latest
git status
git checkout main   # or your working branch
git pull origin main

# After making changes: stage, commit, push
git add -A
git status
git commit -m "Consolidate portal shell, align base template, development report"
git push origin main

# If you need to force-push (e.g. after rebase) and your remote allows it:
# git push --force-with-lease origin main
```

If SSH or permissions block push, fix SSH config (e.g. `Bad owner or permissions on /etc/ssh/ssh_config.d/...`) or use HTTPS and credential helper.

### 5.2 Containers (portals stack)

From the compose project root:

```bash
cd /srv/compose/portals

# Optional: migrate any legacy admin state before rebuild
./scripts/migrate_legacy_admin_state.sh

# Rebuild and start portal services (pick what you run)
docker compose up -d --build fnd_portal
docker compose --profile portal_instances up -d --build tff_portal
docker compose --profile portal_instances up -d --build example_portal
docker compose --profile auth up -d redis_portal oauth2_proxy_portal

# Check status
docker compose ps
```

If Docker fails with permission errors (e.g. `buildx/activity`), fix ownership of `~/.docker` or run the command as the user that owns that directory.

### 5.3 Health checks after deploy

```bash
curl -fsS http://127.0.0.1:5101/healthz   # FND
curl -fsS http://127.0.0.1:5203/healthz   # TFF
curl -fsS http://127.0.0.1:5303/healthz   # Example
curl -fsS http://127.0.0.1:5120/healthz   # Control API
```

---

## 6. Summary

| Topic | Status | Action |
|-------|--------|--------|
| Network sidebar | Aligned | Tabs-only; no Network Views/Contracts/Request Logs in sidebar; FND no Alias section |
| Alias widget URL | Fixed | Uses request host so iframe connects when not on localhost |
| base.html structure | Aligned | Same optional `activity_tool_nav` block in FND and TFF |
| portal.js / portal.css | Duplicated | Identical in both flavors; add single canonical source or sync step |
| app.py helpers | Duplicated | Extract to _shared/portal (network, sidebar, embed URL, events, alias utils) |
| Legacy data shims | TFF only | Set include_legacy_shims=False on TFF when clients migrated |
| Retired tools | Filtered at build | Remove from build.json and RETIRED_TOOL_IDS when no longer needed |
| Legacy routes | Present | Audit; document; plan deprecation or removal |
| Shared base template | Not yet | Add base_shell.html and template path so flavors extend it |
| Shell static assets | Per-flavor | Serve or copy from one canonical location |

This report should be updated as consolidation and hardening work is completed.
