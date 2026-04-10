# Paradigm Expression Alignment

## PROMPT:

The repo now contains a real V2 shell-composition path. Do not replace it, bypass it, or regress it into a frontend-owned shell.

First read and obey:
- repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py
- repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py
- repo/mycite-core/MyCiteV2/instances/_shared/portal_host/app.py
- repo/mycite-core/MyCiteV2/instances/_shared/portal_host/templates/portal.html
- repo/mycite-core/MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js
- repo/mycite-core/MyCiteV2/docs/ontology/interface_surfaces.md
- repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf

Task:
Harden and complete the existing V2 shell-composition implementation so the V1 visual shell is fully expressed through V2-owned region contracts, without browser-owned shell truth and without deploy/config drift.

Rules:
1. Preserve the current V2 shell contract.
   - Keep `shell_composition` as the canonical source of shell state.
   - Keep shell-owned activity dispatch bodies.
   - Keep tool legality in the shell/state-machine layer.
   - Do not reintroduce fallback navigation as the real shell.

2. Remove remaining client-owned shell truth.
   - Any collapse/expand or mode transition that should be shell-owned must not exist only as a local DOM mutation.
   - If a behavior is truly presentation-only, keep it local.
   - If a behavior changes shell composition, foreground region, active tool, or inspector/workbench posture, route it through the shell contract.

3. Strengthen region semantics.
   - Replace generic JSON-document rendering where possible with explicit region payload kinds.
   - The workbench and inspector should receive structured V2 surface projections, not mostly raw dumped JSON.
   - Keep V1 visual ergonomics, but make the region payloads semantically stronger.

4. Keep the current boundary model.
   - V1 assets and visual classes may be reused.
   - V1 runtime assumptions may not be reused.
   - Tools attach to shell-defined surfaces.
   - No alternate shell state in JS.

5. Reconcile deploy reality.
   - Review whether nginx still points `/portal` and `/healthz` to old upstreams.
   - If repo changes and deploy config are not aligned, report that explicitly and fix the config if it is part of the repo scope.

Required outcomes:
- The current shell-composition path remains canonical.
- Remaining client-side shell-state drift is removed or clearly limited to presentation-only behavior.
- Activity bar, control panel, workbench, and inspector all remain driven by runtime-issued region payloads.
- AWS and datum surfaces continue to work through shell-owned dispatch.
- `/portal/system` and `/portal/static/*` remain valid.
- Nginx upstreams are checked against the intended V2 host path.
- Tests cover shell composition shape, route delivery, static asset delivery, and prevention of fake fallback shell behavior.

Acceptance criteria:
- No regression to client-owned shell truth.
- No hardcoded fallback nav as a substitute for runtime-issued activity items.
- Clear separation in the report between:
  - state-machine/runtime hardening
  - host/template/client rendering changes
  - deploy/nginx changes
  - remaining semantic gaps

Important:
Do not treat this as a restyle task.
Do not reinvent the shell contract.
Finish and harden the current V2 shell-composition implementation.

Additional alignment notes.

The repo now supports a more precise instruction vocabulary. You should stop saying “recreate the old shell in V2” as the main instruction. That wording is still too easy to satisfy cosmetically. Say instead: “harden the existing V2 shell-composition implementation until the V1 shell is only a presentation of V2-owned region contracts.”

Also, distinguish three levels of truth every time. The shell contract is owned by the state machine and runtime. Region rendering is owned by the host/template/client. Visual parity is owned by the V1-derived assets and CSS. Mixing those three is what caused the earlier drift.

The remaining weak spot is not the existence of the shell contract. It is that some shell interactions are still not fully mediated by that contract, and several surfaces are still generic JSON renderings instead of richer V2 region payloads. That is where the agent should now focus.

Operationally, keep repo completion and deployment completion separate. The code path in `mycite-core` is now substantially more aligned, but `srv-infra` still appears to point portal traffic at `5101` and `5203` . That should be treated as unresolved until changed and deployed.

From `repo/mycite-core`:

```bash
cd /srv/repo/mycite-core
PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m pytest MyCiteV2/tests
```

From `repo/srv-infra`:

```bash
cd /srv/repo/srv-infra
grep -n "proxy_pass\|set \$portal_upstream\|healthz" nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
```

On the server after deploy:

```bash
cd /etc/nginx/sites-available
sudo nginx -t && sudo systemctl reload nginx
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/system
curl -I https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css
```

The strongest update, given the current repo, is this: the paradigm is now present enough to proceed with preserving and hardenning it, not to invent it.


---


## OUTPUT:


Here is a concise report aligned with [19-paradigm_expression_alignment.md](file:///srv/repo/mycite-core/MyCiteV2/docs/archive/19-paradigm_expression_alignment.md).

---

### State machine / runtime hardening

- **`AdminShellChrome`** (`admin_shell.py`): optional `inspector_collapsed` and `control_panel_collapsed` on **`AdminShellRequest`**, validated and serialized on `to_dict` / `from_dict`.
- **`_apply_shell_chrome_to_composition`** (`admin_runtime.py`): merges chrome into `shell_composition`, sets `requested_shell_chrome` when present, and for **tool mode + dismissed inspector** sets `foreground_shell_region` to `center-workbench` and swaps the workbench to **`kind: tool_collapsed_inspector`** (server-owned posture, not a JS guess).
- **Region payloads**
  - **Inspector**: **`aws_read_only_surface`** (structured fields + profile summary + warnings) and **`aws_tool_error`** instead of generic JSON for AWS paths.
  - **Workbench / datum**: **`datum_workbench`** now uses **`summary`**, **`warnings`**, **`rows_preview`** (no full-dump `document`); home summary no longer carries **`surface_echo`**.
- **Exports**: `AdminShellChrome` wired through `hanus_shell.__init__` and `admin_shell.__all__`.

### Host / template / client rendering

- **`portal.html`**: `data-portal-shell-driver="v2-composition"` so shared `portal.js` can defer chrome to the V2 shell path.
- **`portal.js`**: Under that driver, **does not** force the inspector open in tool mode; **Interface Panel** toggle and **Close** dispatch **`mycite:v2:inspector-toggle-request`** / **`mycite:v2:inspector-dismiss-request`** instead of owning collapse truth; activity-bar clicks no longer call **`close()`** (avoid fighting `loadShell`).
- **`v2_portal_shell.js`**: **`postShellChrome`** merges `shell_chrome` onto a clone of **`lastShellRequest`** and **`POST`s the shell**; tracks **`lastComposition`** for toggle; renders **`aws_read_only_surface`**, **`aws_tool_error`**, structured **datum** table, **`tool_collapsed_inspector`**; calls **`PortalShell.rebalanceWorkbench()`** after apply; **narrow-write** refresh uses **`cloneRequestWithoutChrome`** so the inspector can reopen; **removed** the old DOM-only inspector close handler.
- **`portal.css`**: **`.v2-surface-dl`** for AWS inspector layout.

### Deploy / nginx

- **`portal.fruitfulnetworkdevelopment.com.conf`**: Comments only — **`/healthz`** and **`location ^~ /portal`** were already on **6101 / 6203**; clarified that **`/portal/api/admin/aws/`** and **`paypal/`** remain on **5101** by design (legacy), while **V2** admin JSON is under **`/portal/api/v2/`** via the main `/portal` upstream. No `proxy_pass` change (avoids breaking legacy callers).

### Tests

- **`test_admin_runtime_composition`**: AWS inspector kind **`aws_read_only_surface`**; new **`test_shell_chrome_mediates_inspector_collapse_in_tool_mode`**.
- **`test_state_machine_admin_shell`**: **`test_shell_chrome_round_trips_in_request_dict`**.
- Existing portal / boundary tests still pass (venv `fnd_portal`).

### Remaining semantic gaps

- **Control panel** open/close is still mostly **local** (`portal.js` + localStorage); only **`shell_chrome.control_panel_collapsed`** is on the contract if you start sending it from the client later.
- **`json_document`** fallback remains for unknown inspector kinds.
- **Narrow-write result** is still a raw `<pre>` after submit (could get a typed **`narrow_write_result`** region later).
- **Operational**: confirming live **`curl -I`** on the real host is still outside repo verification.

**Three levels of truth (as requested):** shell contract = state machine + runtime (`shell_composition`, `shell_chrome`, legality); rendering = template + `v2_portal_shell.js` + `portal.js` presentation hooks; visual parity = V1 CSS/classes unchanged in spirit.

---

## PROMPT:

I am still getting a view of the portal tht has no chnages.

---


## OUTPUT


## What you’re seeing vs this repo

The page in your screenshot matches **older** HTML, not what is in `/srv/repo/mycite-core` now:

| Your screenshot | Current `portal.html` in repo |
|-----------------|----------------------------------|
| Title line **“MyCite V2”** | **“MyCite”** in the menubar |
| Static **“V2 shell”** + long paragraph in the control panel | **“Context”** + short **“Loading shell regions…”** + **build id** |
| **“Portal: V2 native”** (human-readable) | **“Portal: v2_native”** (literal `host_shape`) |

So the live host is almost certainly still running an **old build** (old wheel, old checkout, or a process that was never restarted after deploy).

The **unstyled** look means **`/portal/static/portal.css` is not being applied** (404 from wrong upstream, blocked load, or HTML served from something that is not the V2 Flask app).

## What we changed in-repo (so you can verify after deploy)

1. **`portal.html`**  
   - Assets use **fixed paths**: `/portal/static/portal.css`, `/portal/static/portal.js`, `/portal/static/v2_portal_shell.js`, logo SVG.  
   - HTML comment: `shell-template: v2-composition build=…`  
   - Activity footer line: **`build: …`** (from env, default **`not-set`** until you set it).

2. **`app.py`**  
   - **`MYCITE_V2_PORTAL_BUILD_ID`** passed into the template (set in systemd to a git SHA or release tag).

3. **`v2_portal_shell.js`**  
   - If **`POST /portal/api/v2/admin/shell`** fails (non-JSON, 401, 502, etc.), the UI shows **HTTP status + a snippet of the body** instead of hanging on “Loading…”.

## What you should do on the server

1. **Deploy** this `mycite-core` revision and **restart** the V2 portal unit (e.g. `mycite-v2-fnd-portal.service` or whatever runs gunicorn/flask on **6101**).

2. **Set a build id** (optional but useful):
   - `Environment=MYCITE_V2_PORTAL_BUILD_ID=2026-04-10-1` (or git SHA) in the unit file, then `daemon-reload` + restart.

3. **Confirm nginx** (on the box, not only in git):
   - `location ^~ /portal` → **6101** (FND) / **6203** (TFF cookie), as in your `srv-infra` snippet.

4. **Smoke checks** (after deploy):
   - `curl -sI https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css` → **200**
   - Open `/portal` → **View source** and search for **`shell-template: v2-composition`** and **`build:`** in the footer. If those are missing, you are **not** on this template.

5. In the browser **Network** tab: if **`v2_portal_shell.js`** or **`portal.css`** is red, or **`admin/shell`** returns **401/403/502**, fix auth/upstream first; the new JS will surface that in the page text.

Until the process behind **`portal.fruitfulnetworkdevelopment.com/portal`** serves this template and static files from the V2 app, the UI will **not** change no matter what is in the git repo alone.

---

## CONSIDERATION (reconciled against repo at `/srv/repo`)

An earlier **inline review** (previous version of this section) claimed that `portal.html` still had the static **“V2 shell”** paragraph, that **`MYCITE_V2_PORTAL_BUILD_ID` / `shell-template` / build footer** were missing, and that **`srv-infra` nginx** still sent **`/healthz` and `/portal` to `5101`**. That text reflected a **different tree or branch** than the canonical checkout under **`/srv/repo`** on this machine, or a search that did not hit the updated paths.

**What `/srv/repo/mycite-core` actually contains (verify locally):**

- **`portal.html`**: HTML comment `shell-template: v2-composition build={{ portal_build_id }}`; `v2-bootstrap-shell-request`; control panel title **Context** with a **runtime placeholder** (not the old long “V2 shell” blurb); activity footer includes **`build: {{ portal_build_id }}`**; static assets referenced as **`/portal/static/...`**.
- **`app.py`**: `PORTAL_BUILD_ID` from env var **`MYCITE_V2_PORTAL_BUILD_ID`** (default label **`not-set`**); `render_template(..., portal_build_id=PORTAL_BUILD_ID, bootstrap_shell_request=...)`.

**What `/srv/repo/srv-infra` actually contains** for `portal.fruitfulnetworkdevelopment.com.conf`:

- **`location = /healthz`** → **`proxy_pass http://127.0.0.1:6101/healthz`** (V2 FND portal host).
- **`location ^~ /portal`** → **`set $portal_upstream http://127.0.0.1:6101`** with **`6203`** when `portal_instance=tff`; **`proxy_pass $portal_upstream`**.
- **`5101`** remains only on **legacy** `location ^~ /portal/api/admin/paypal/` and **`/portal/api/admin/aws/`** (old paths), **not** on `/portal` or `/healthz`.

**What the screenshot still validly shows**

- **Unstyled HTML** strongly implies the **live** response path is not applying **`/portal/static/portal.css`** (404, wrong upstream, blocked request, or HTML not served by the Flask app that owns `static_url_path=/portal/static`). That is **orthogonal** to whether composition logic exists in Python.
- If **view source** on production lacks **`shell-template: v2-composition`** and **`build:`**, the **running** portal process or **deployed** nginx config **differs** from this repo revision—compare **`/etc/nginx/sites-enabled/...`** and the unit actually listening on **6101**.

**Commands (truth on disk)**

```bash
cd /srv/repo/mycite-core
grep -n "shell-template\|portal_build_id\|V2 shell\|bootstrap_shell_request" \
  MyCiteV2/instances/_shared/portal_host/templates/portal.html \
  MyCiteV2/instances/_shared/portal_host/app.py

cd /srv/repo/srv-infra
grep -n "proxy_pass\|set \$portal_upstream\|healthz" \
  nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf
```

**On the server (live vs repo)**

```bash
curl -sI https://portal.fruitfulnetworkdevelopment.com/portal/static/portal.css
curl -sI https://portal.fruitfulnetworkdevelopment.com/portal/system
# Compare HTML body to repo template; look for shell-template and build: lines.
```

**Conclusion:** The superseded review mixed accurate observations (**CSS not applied on the live site**) with **incorrect claims about the current `mycite-core` + `srv-infra` trees at `/srv/repo`**. Treat **git + deployed config** as separate: align production with this repo and fix static/upstream until `portal.css` returns **200** and the template markers appear in view source.

---

## UPDATES:


Here is a concise read on that review versus **this** workspace.

### The review was wrong about the repo at `/srv/repo`

On disk today:

- **`portal.html`** does **not** use the old static **“V2 shell”** block. The control panel is **“Context”** plus a **runtime placeholder** that mentions **`portal_build_id`**. There is an HTML comment **`shell-template: v2-composition build={{ portal_build_id }}`**, **`v2-bootstrap-shell-request`**, and **`build: {{ portal_build_id }}`** in the activity footer.
- **`app.py`** defines **`PORTAL_BUILD_ID`** from **`MYCITE_V2_PORTAL_BUILD_ID`** and passes **`portal_build_id=`** into **`render_template`** along with **`bootstrap_shell_request`**.
- **`srv-infra`** `portal.fruitfulnetworkdevelopment.com.conf` sends **`/healthz`** and **`location ^~ /portal`** to **6101 / 6203**, not 5101. **5101** is only for **legacy** **`/portal/api/admin/paypal/`** and **`/portal/api/admin/aws/`**.

So the review’s “grep comes back empty” / “nginx still 5101 for portal and healthz” / “no build wiring” statements do **not** match **`/srv/repo/mycite-core`** and **`/srv/repo/srv-infra`** as they exist here. Likely causes: another clone/branch, old commit, or paths that weren’t the ones above.

### What the review got right

- A **mostly unstyled** page is still best explained by **`/portal/static/portal.css` not being applied** on the **live** path (or HTML not coming from the V2 app that serves that static tree). That’s a **deploy/upstream/browser-network** issue, not “composition missing in Python.”
- **Production** can still diverge from **git**: you only know after **view source** (look for **`shell-template`** / **`build:`**) and **`curl -I …/portal/static/portal.css`** on the real host.

### Doc update

The **CONSIDERATION** block in **`19-paradigm_expression_alignment.md`** (lines 211–263) is **replaced** with a short **reconciled** section: it keeps the good part (CSS/live path), corrects the mistaken repo/nginx claims, and points at the same **grep/curl** checks so the file matches **`/srv/repo`** as the authority.

---


## RETURNED:


Here is what was fixed and verified.

## What was wrong (from the analysis)

- **In-app behavior was already correct**: `/portal/static/portal.css` is served by the V2 portal host with a 200 and real CSS (tests already covered this).
- **“Unstyled” in production** was consistent with **edge routing** (nginx sending `/portal` traffic to the wrong upstream) or a **broken deploy** (static files missing from the package), not with Flask’s catch-all vs static route order.
- Operators had **no signal in health** that the shell static bundle was present on disk.

## What we changed (repo)

1. **`portal_host` health** (`app.py`)  
   - Added `portal_static_bundle`: package static dir, `portal_css_present`, `portal_css_size_bytes`, `v2_portal_shell_js_present`, `static_url_path`, `static_ok`.  
   - **`ok` is now false (503)** if `portal.css` or `v2_portal_shell.js` is missing from the package — broken or partial installs fail health checks immediately.

2. **Nginx** (`srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`)  
   - Added an explicit **`location ^~ /portal/static/`** block (same auth and **6101 / 6203** upstream logic as `/portal`) so static requests are **explicitly** tied to the V2 portal, with a comment that **longest-prefix** routing keeps `/portal/static/*` on that upstream even if the broader `/portal` block is edited later.

3. **Tests** (`test_v2_native_portal_host.py`)  
   - Asserts `portal_static_bundle` and `static_ok` on a healthy instance.

## Verification

All five tests in `MyCiteV2.tests.integration.test_v2_native_portal_host` pass with `/srv/venvs/fnd_portal/bin/python3`.

## Production checklist (so the live issue stays solved)

1. Deploy this revision and **reload nginx** from `srv-infra` (so the new `/portal/static/` location is active).  
2. Ensure **`/portal` and `/portal/static/`** still target **6101** (and **6203** for TFF), not legacy **5101**.  
3. After deploy, **`GET /portal/healthz`** (or `/healthz` through nginx) should be **200** with `portal_static_bundle.static_ok: true` and a non-zero `portal_css_size_bytes`.  
4. Optionally set **`MYCITE_V2_PORTAL_BUILD_ID`** in the unit environment so the HTML footer proves which build is running.

**Bottom line:** The codebase now **fails closed** if shell CSS/JS are missing and **documents/defends** nginx routing for static assets; combined with correct upstream and deploy, the unstyled-shell symptom is addressed end-to-end.

---