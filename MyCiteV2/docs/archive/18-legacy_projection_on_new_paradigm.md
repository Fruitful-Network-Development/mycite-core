# Projection of Legacy Shell In New Paradigm

## PROMPT:

You are to implement the V1 portal shell as a V2-native shell composition, not as a V1-styled HTML page with ad hoc JS.

Read and obey these repo authorities first:
- repo/mycite-core/MyCiteV2/docs/ontology/interface_surfaces.md
- repo/mycite-core/MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py
- repo/mycite-core/MyCiteV2/instances/_shared/runtime/admin_runtime.py
- repo/mycite-core/MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md
- repo/mycite-core/MyCiteV1/instances/_shared/runtime/flavors/fnd/portal/ui/templates/base.html
- repo/mycite-core/MyCiteV2/docs/archive/17-v2_ui_and_aws_domains.md

Objective:
Manifest the V1 shell paradigm inside V2 correctly. The result must preserve the V1 visual language and shell ergonomics, but its composition, modal state, and tool legality must be owned by V2 shell surfaces and runtime envelopes.

Non-negotiable architectural rules:
1. Do not implement a fake shell in browser JS.
   - No shadow shell state.
   - No hardcoded fallback nav that substitutes for shell catalog.
   - No direct UI-owned legality model.
   - No browser-owned modal truth.

2. The shell must own:
   - active surface / slice
   - shell composition mode
   - which region is foregrounded
   - whether control panel and inspector are collapsed
   - what tool may launch
   - what payload each region receives

3. V1 parity is presentation only.
   - V1 CSS classes, layout regions, icons, and shell ergonomics may be reused.
   - V1 route assumptions, V1 runtime assumptions, and V1 service ownership must not be reused.

4. Tools must attach to shell-defined surfaces.
   - AWS, datum/resource workbench, and future tools are projections inside shell-owned composition.
   - They may not define alternate shell state.
   - They may not bypass the shell-owned registry.

Required outcome:
Rework V2 so that the old V1 shell is expressed as a V2 shell composition contract.

Implement this in four layers.

Layer A — Shell state model
Create or extend a V2 shell state model so the shell can explicitly describe:
- active service or active surface
- active tool slice
- shell composition mode: system | tool
- foreground shell region
- control panel state
- inspector state
- region payload contracts for:
  - activity bar
  - control panel
  - workbench
  - inspector

The shell state must be serialized from the V2 runtime, not inferred only in HTML or JS.

Layer B — Runtime envelope
Extend the relevant runtime entrypoints so the runtime envelope returns enough structured surface payload to drive:
- activity navigation
- control panel sections
- workbench content descriptor
- inspector content descriptor
- launchable tool entries
- active selection state
- any region layout mode required for the old V1 shell behavior

Do not return only home-status JSON blobs for the UI to improvise with.
Do not use the shell only as a catalog fetch.
The runtime must project an actual shell composition.

Layer C — Host/template/client
Refactor the V2 portal host so:
- portal.html is a shell renderer, not a logic owner
- /portal/static serves the V1 visual assets needed for parity
- JS is thin and only:
  - requests the shell envelope
  - dispatches user actions back into approved V2 routes
  - renders the returned region payloads
  - never invents shell truth locally

The visual shell should match V1:
- ide-menubar
- ide-activitybar
- ide-controlpanel
- center workbench
- inspector / interface panel
- theme behavior
- splitters and modal emphasis where appropriate

But all region content must come from V2 shell-owned state.

Layer D — Deployment reality
Also review the actual upstream/deploy path.
Do not claim completion if repo changes exist but nginx or service routing still sends /portal to the wrong upstream.
Check both repos where applicable:
- repo/mycite-core
- repo/srv-infra

Acceptance criteria:
1. The shell can render V1-style layout without any V1 runtime import.
2. The activity bar, control panel, workbench, and inspector are all driven by V2 runtime payloads.
3. Browser JS contains no fallback nav that becomes the real shell when runtime data is absent.
4. Tool launch legality remains owned by the shell registry.
5. Entering an AWS or datum tool changes shell composition through V2-approved state, not by swapping random DOM fragments.
6. /portal/system works.
7. /portal/static/* works.
8. The deployed nginx upstreams actually point to the intended V2 host.
9. Tests cover:
   - no MyCiteV1 imports in V2 host
   - shell envelope shape
   - region payload rendering expectations
   - /portal/system route
   - /portal/static asset delivery
   - no fake fallback catalog behavior
10. Return a concise report separating:
   - architectural changes
   - host/template changes
   - runtime/state-machine changes
   - nginx/deploy changes
   - remaining gaps

Important:
If the current V2 shell model is insufficient to express the old V1 modal paradigm, first extend the shell/runtime contract. Do not paper over that missing contract with client-side logic.

Additional notes to keep the agent aligned:

First, require “shell-state parity,” not “UI parity.” Your earlier prompt mostly asked for layout recreation. That lets the agent satisfy the request with V1-looking chrome. What you actually want is the V1 shell behavior recast as V2-owned state. In the repo, V2 explicitly says the shell owns serialized state and legality, and tools may not define alternate shell state. That is the authority the prompt must force the agent to obey, not just mention. See `interface_surfaces.md`, `admin_shell.py`, and `admin_runtime.py` in `MyCiteV2`.

Second, distinguish three different things that were previously blurred together. V1 style assets are acceptable to port. V1 shell semantics must be re-expressed in V2 contracts. V1 runtime assumptions must not come across at all. The prompt should make those separate. Otherwise the agent will keep importing the appearance of V1 while silently rebuilding its behavior in JS.

Third, define what “modal paradigm” means in V2 terms. In your case it should mean that the shell decides whether the workbench or interface panel is foregrounded, what the control panel is showing, and what tool surface is active. It should not mean “there is a modal-looking area in the page.” If you do not define that, the agent will keep treating modal behavior as DOM swapping.

Fourth, remove “fallback” language unless you mean a true failure path. The current V2 client hardcodes nav and behavior when the shell payload is insufficient. That turns fallback into the real architecture. If you allow that in the prompt, the agent will use it again.

Fifth, force a “cross-repo completion” section in the output. The archive notes claimed nginx had been moved to V2 ports, but the current `srv-infra` config still shows `/portal` and `/healthz` going to `5101` and `5203`, not the claimed V2 upstreams. So the agent must report repo completion and deploy completion separately, or it will keep overstating success. See `repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`.

Sixth, for AWS, keep treating it as the reference V2 tool seam, not as evidence the shell is correct. The AWS work is comparatively aligned now: the IAM inventory correctly says IAM does not encode mailbox domain, SES verification is required, and the V2 live profile now supports `allowed_send_domains`. That part is a bounded-write/read-only contract problem and is already much closer to the intended V2 pattern than the UI is.

If you want the prompt to be even harder to misread, prepend this one sentence above the main body:

```text
Do not solve this as a frontend restyle task; solve it as a V2 shell-contract implementation task whose presentation layer reuses V1 visual language.
```

For local verification after an implementation pass, run these from the repo roots.

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

The strongest single correction is this: stop asking for a recreation of the old portal layout, and start asking for a V2 shell contract that happens to render with V1 layout.


---


## OUTPUT:



## Architectural changes

- **Shell state model (`admin_shell.py`)**  
  Added versioned contracts: `ADMIN_SHELL_COMPOSITION_SCHEMA`, per-region schemas, and `DATUM_RESOURCE_WORKBENCH_SLICE_ID`.  
  Extended **`resolve_admin_shell_request`** so `trusted-tenant` can select **only** registry-backed tool slices (via `resolve_admin_tool_launch`) or **datum**; internal band-0 behavior and “AWS only via registry” gating are unchanged.  
  Added **`build_portal_activity_dispatch_bodies`** (full `POST` bodies for each nav item) and **`build_shell_composition_payload`** plus helpers for composition mode, foreground region, and inspector collapse derived from the **active surface**, not the client.

- **Runtime envelope (`runtime_platform.py`, `admin_runtime.py`)**  
  Envelopes now require a **`shell_composition`** field (may be `null` on direct AWS entrypoint responses).  
  **`run_admin_shell_entry`** takes **`portal_tenant_id`**, **`aws_status_file`**, and **`data_dir`**, and **projects** activity bar, control panel, workbench, and inspector from runtime: home/registry/datum/AWS read-only/AWS narrow-write each map to structured region payloads. Trusted-tenant AWS slices embed **`run_admin_aws_read_only`** (and narrow-write panel uses it for form defaults). **No V1 imports.**

- **Portal host (`app.py`)**  
  Passes host **`tenant_id`**, **`aws_status_file`**, and **`data_dir`** into `run_admin_shell_entry`.  
  Renders a **server-owned bootstrap** JSON (`bootstrap_shell_request`) for the initial shell `POST`.

## Host / template / client

- **`portal.html`**  
  V1-style regions kept; added `<script type="application/json" id="v2-bootstrap-shell-request">` for the initial shell request; inspector content goes through **`#v2-inspector-dynamic`**.

- **`v2_portal_shell.js`**  
  Rewritten: **only** reads `shell_composition` from the runtime envelope, applies chrome (`data-*` / workbench visibility / inspector layout), renders regions by **`kind`**, navigates with **`item.shell_request`** bodies from the server, and submits narrow writes using **`submit_contract`** from the inspector payload. **No `buildFallbackNav`, no hardcoded slice catalog.**

- **`portal.css`**  
  Added **`.v2-table`** for registry tables.

## Runtime / state machine

- Above **`admin_shell`** + **`admin_runtime`** changes; datum workbench is a first-class resolved slice for internal (and trusted-tenant when using datum id).

## Nginx / deploy

- **`srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`**: `location ^~ /portal` already uses **`6101` / `6203`** via `$portal_upstream` — aligned with the V2 portal host.  
- **Gap (unchanged):** legacy **`/portal/api/admin/aws/`** and **`/portal/api/admin/paypal/`** blocks still **`proxy_pass` to `5101`**. V2 admin JSON lives under **`/portal/api/v2/...`** and is covered by the general `/portal` upstream. If anything still calls the **old** admin paths, it will hit V1 ports until those locations are retired or repointed.

## Remaining gaps

- **Bridge / non-portal callers** of `run_admin_shell_entry` (e.g. `v1_host_bridge`) still omit `portal_tenant_id` / paths: composition defaults to **`fnd`** and **no** `data_dir` unless you extend `V2AdminBridgeConfig`.  
- **Home workbench** does not yet fold in **`/portal/healthz`**; cards are driven from **band-0 `surface_payload`** only.  
- **Menubar** menu items remain static chrome (same as V1 template style); only titles/subtitles update from composition.  
- **Legacy nginx** admin paths to **`5101`** (noted above).

## Tests

- Extended **`test_admin_runtime_composition`**, **`test_v2_native_portal_host`**, **`test_v2_native_portal_host_boundaries`** (no fallback nav / no slice constants in JS), **`test_admin_tool_platform_contract`**, and **`ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS`** usage.  
- Verified with **`/srv/venvs/fnd_portal/bin/python3`** on the modules listed above (including AWS runtime integration tests).

---