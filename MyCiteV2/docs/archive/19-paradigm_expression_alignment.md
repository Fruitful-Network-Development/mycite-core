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