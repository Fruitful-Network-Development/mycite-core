# V2 Native Portal Cutover Plan

## PROMPT:

This seem like alot of old code is still inuse and that the transition hasn't been made.
I would like you to use all these considerations above to invetigate the plan documentation and/or V2 outlines that have been partially created for the new form, and create the v2 native fixes for all of the points above.
That way v1 is completely removed from use, and all implementations and uses of the portal adopt the v2 model, with out trying to retro fix/wire.

---


## PLAN:

### Summary
Replace live `/portal` use with a V2-native host for FND and TFF, staged in parallel before traffic is switched. The live portal code will move to `MyCiteV2`; live tenant state remains in `/srv/mycite-state/instances/{fnd,tff}`. V1 may remain on disk as an archive during cutover, but it must not be imported, hosted, or used by the deployed portals.

This slice covers admin shell, AWS read-only/narrow-write, datum/data loading, and analytics path stability. Maps, AGRO, PayPal, broad analytics dashboards, progeny workbench, and other later-band tools stay out of this cutover.

### Key Changes
- Add a V2-native portal host under `MyCiteV2`, separate from the current `v1_host_bridge`.
  - Serve `GET /portal` from V2 assets/templates only.
  - Expose `GET /portal/healthz` with `schema: mycite.v2.portal.health.v1`, `host_shape: v2_native`, tenant id, state roots, datum health, analytics root, and AWS config health.
  - Keep the existing V2 admin runtime API surface:
    - `POST /portal/api/v2/admin/shell`
    - `POST /portal/api/v2/admin/aws/read-only`
    - `POST /portal/api/v2/admin/aws/narrow-write`
  - Do not expose or depend on `/portal/api/v2/admin/bridge/health` in the V2 host.

- Add a V2-native datum/data adapter.
  - Canonical source: `/srv/mycite-state/instances/{tenant}/data/system/anthology.json`.
  - Do not read from or create legacy root files like `/srv/mycite-state/instances/{tenant}/data/anthology.json`.
  - Add `GET /portal/api/v2/data/system/resource-workbench`.
  - Response schema: `mycite.v2.data.system_resource_workbench.surface.v1`.
  - Return loaded resource rows, source file paths, materialization status, warnings for missing derived payloads, and a nonzero `row_count` when the canonical anthology has rows.
  - Treat legacy root-level datum paths as health warnings only, not fallback inputs.

- Add a V2-native analytics event path resolver.
  - Canonical write root: `/srv/webapps/clients/{domain}/analytics/events/YYYY-MM.ndjson`.
  - Reject or warn on `/srv/webapps/{domain}/analytics/...`.
  - Keep analytics dashboards out of this slice; only preserve correct event write placement so visits no longer recreate stray root directories.

- Make AWS live mapping a required V2 deployment input.
  - FND must use `MYCITE_V2_AWS_STATUS_FILE=/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm/aws-csm.fnd.dylan.json`.
  - TFF must use `MYCITE_V2_AWS_STATUS_FILE=/srv/mycite-state/instances/fnd/private/utilities/tools/aws-csm/aws-csm.tff.technicalContact.json`.
  - If the file is missing or not recognized by the live AWS profile adapter, `/portal/healthz` returns unhealthy and admin AWS routes return the existing V2 runtime error envelope.
  - Narrow write remains limited to `selected_verified_sender` and must continue to audit through the configured V2 audit file.

- Deploy in parallel before switching traffic.
  - Create `mycite-v2-fnd-portal.service` on port `6101`.
  - Create `mycite-v2-tff-portal.service` on port `6203`.
  - Both services must set `MYCITE_REPO_ROOT=/srv/repo/mycite-core/MyCiteV2` or avoid `MYCITE_REPO_ROOT` entirely.
  - Both services must point `PUBLIC_DIR`, `PRIVATE_DIR`, and `DATA_DIR` at the existing `/srv/mycite-state/instances/{tenant}` directories.
  - After smoke tests pass, update the live nginx/upstream routing for `https://portal.fruitfulnetworkdevelopment.com/portal` to the V2 services.
  - Then disable the old `fnd-portal.service` and `tff-portal.service` V1 hosts.

### Tests And Acceptance
- Add V2 tests proving the portal host imports no `MyCiteV1` modules and does not use the bridge adapter.
- Add V2 route tests for `/portal`, `/portal/healthz`, admin shell, AWS read-only, AWS narrow-write, and datum resource workbench.
- Add datum adapter tests using temp live-state fixtures where `data/system/anthology.json` loads rows and root-level legacy datum files are ignored.
- Add analytics resolver tests proving all event writes land under `/srv/webapps/clients/{domain}` and never under `/srv/webapps/{domain}`.
- Add deployment checks:
  - `systemctl cat mycite-v2-fnd-portal.service mycite-v2-tff-portal.service` contains `MyCiteV2` and no `MyCiteV1`.
  - `curl` to both V2 canary ports returns `host_shape: v2_native`.
  - Datum route returns rows from live `data/system/anthology.json`.
  - AWS read-only returns the V2 runtime envelope for FND and TFF.
  - After nginx switch, `https://portal.fruitfulnetworkdevelopment.com/portal` serves the V2 shell.
  - Old V1 services are disabled and no live portal process has `MyCiteV1` in its command, cwd, or env.

### Assumptions
- “Remove V1 from use” means remove V1 from live serving/import/runtime paths first; physical deletion of `/srv/repo/mycite-core/MyCiteV1` can be a later archival cleanup.
- Admin+Data First is the required cutover scope; later-band tools are not blockers.
- Parallel V2 is the deployment path; direct in-place replacement is avoided until V2 canary checks pass.
- No live data files are moved destructively during this slice. V2 adapts to the canonical live state layout instead.


---


## OUTPUT:

Implemented the V2 native cutover.

**What Changed**
- Added the V2-native portal host at [app.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/app.py), with:
  - `GET /portal`
  - `GET /portal/healthz`
  - `POST /portal/api/v2/admin/shell`
  - `POST /portal/api/v2/admin/aws/read-only`
  - `POST /portal/api/v2/admin/aws/narrow-write`
  - `GET /portal/api/v2/data/system/resource-workbench`
  - no V1 bridge health route; `/portal/api/v2/admin/bridge/health` returns `404`.

- Added V2-native datum loading from canonical `data/system/anthology.json` through [live_system_datum_store.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/live_system_datum_store.py). It ignores legacy root datum files instead of falling back to them.

- Added V2-native analytics path resolution and collect writing through [analytics_event_paths.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/filesystem/analytics_event_paths.py). Site visits now write under `/srv/webapps/clients/<domain>/analytics/events/YYYY-MM.ndjson`.

- Added the native portal shell template at [portal.html](/srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/templates/portal.html).

- Added focused V2 tests for datum contracts/adapters, analytics, the native host, and host isolation from V1.

**Deployment**
- Created and started:
  - [mycite-v2-fnd-portal.service](/etc/systemd/system/mycite-v2-fnd-portal.service) on `127.0.0.1:6101`
  - [mycite-v2-tff-portal.service](/etc/systemd/system/mycite-v2-tff-portal.service) on `127.0.0.1:6203`

- Updated nginx in [portal.fruitfulnetworkdevelopment.com.conf](/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf):
  - `/portal` routes to V2 FND by default.
  - `portal_instance=tff` routes to V2 TFF.
  - public `/healthz` routes to V2 FND.
  - legacy admin/FND/AWS/PayPal portal paths fail closed with `410`.
  - public JSON fallback routes to V2 FND instead of V1.

- Updated public site analytics proxy routes for FND, TFF, CVCC, and CTV to use `6101` instead of old `5101`.

- Disabled old V1 services:
  - `fnd-portal.service`: inactive, disabled
  - `tff-portal.service`: inactive, disabled

- Updated the portal control API and operational scripts so admin restart/status/log actions target the V2 services instead of accidentally reviving V1.

**Verification**
- Full V2 test suite: `122 tests OK`.
- Host control API: `py_compile` OK and service restarted active.
- Shell scripts: `bash -n` OK.
- `nginx -t`: successful, with only the pre-existing proxy header hash warning.
- Live local health:
  - FND: `v2_native fnd True 56 True`
  - TFF: `v2_native tff True 56 True`
- Datum routes now load:
  - FND: `/srv/mycite-state/instances/fnd/data/system/anthology.json`, `56` rows
  - TFF: `/srv/mycite-state/instances/tff/data/system/anthology.json`, `56` rows
- AWS read-only routes return V2 runtime envelopes for both:
  - FND sender: `dylan@fruitfulnetworkdevelopment.com`
  - TFF sender: `technicalcontact@trappfamilyfarm.com`
- No nginx or active V2 service config points at `5101`, `5203`, or `MyCiteV1`.
- No running portal process contains `MyCiteV1`.
- I sent one live analytics smoke event for TFF; it wrote to `/srv/webapps/clients/trappfamilyfarm.com/analytics/events/2026-04.ndjson`, and no new `/srv/webapps/trappfamilyfarm.com/analytics/events/2026-04.ndjson` was created.

V1 is still present on disk as an archive, but it is no longer serving the deployed portal paths.

---


## CONISDERATIONS

1. Repo and portal hardening assessment

The repo updates moved the portal from “V2-ready in principle” to an actual V2-native host shape.

Before the latest cutover review, the repo explicitly said V2 was validated but not yet serving live `/portal`; live FND and TFF were still on the V1 Flask/Gunicorn host, and the next required step was a V2-owned host or bridge (`MyCiteV2/docs/audits/live_cutover_review_2026-04-10.md`). The latest portal commit, `432d0288794446d1af62f110bcd5713d40167fe3` (“V2 Native Portal Cutover”), changes that materially: it adds a V2-native host at `MyCiteV2/instances/_shared/portal_host/app.py`, adds canonical datum loading from `data/system/anthology.json`, adds canonical analytics event pathing under `/srv/webapps/clients/<domain>/analytics/events/YYYY-MM.ndjson`, and adds host-boundary tests forbidding V1 imports and bridge reuse.

So the portal is no longer mainly blocked on architecture. The remaining work is hardening.

The highest remaining gap is deployment codification. The cutover commit reports systemd, nginx, and service-control changes, but those are described in the commit report rather than clearly represented as the canonical infra source of truth in the repo. That is the main source of future drift. The next hardening step should be to make the live `mycite-v2-fnd-portal.service`, `mycite-v2-tff-portal.service`, nginx routing, and portal control scripts repo-owned and reproducible, rather than depending on server-side edits remembered through commit notes.

The second gap is configuration fail-fast behavior. `V2PortalHostConfig.from_env()` in `MyCiteV2/instances/_shared/portal_host/app.py` still falls back to `fnd` when tenant env is absent. That is acceptable for convenience, but weak for production. For a hardened portal host, tenant selection, state roots, AWS status file, and audit file paths should be explicit and validated at startup. Right now some of that failure is deferred to health checks or route execution. In production, misconfiguration should stop the service from booting.

The third gap is security-edge certainty. The V2 host exposes admin shell and AWS endpoints, and the runtime envelope handles audience and availability decisions, but the host file itself does not show a complete edge-auth story. If auth is enforced upstream, that needs to be treated as a tested deployment contract, not an assumption. If it is not fully enforced upstream, this is the biggest unresolved operational risk. The portal should have one explicit statement of where authentication and tenant authorization are enforced, and one end-to-end test proving that unauthorized requests fail before or at the host boundary.

The fourth gap is observability depth. The new `/portal/healthz` is useful, but it is still a narrow readiness probe. It checks canonical datum loading, analytics root resolution, and AWS profile mapping. That is good enough for cutover, not for stable operations. What is still missing is stronger structured logging, request correlation, explicit startup diagnostics, audit sink writability checks, and a black-box smoke path that verifies real proxy-to-host behavior after deployment. The analytics path resolver and datum store are hardened at the code level, but you still want live probes that catch host-level regression, not just unit and integration regressions.

The fifth gap is documentation drift. `MyCiteV2/README.md` still says `packages/` holds inert placeholders only, `instances/` holds runtime composition placeholders only, and `tests/` holds planned placeholders only. That is now false. The repo contains implemented runtime, host, adapters, ports, and tests. This matters because your V2 tree is documentation-first, so stale top-level docs become an authority problem. The repo now needs one current operator/developer entry document that describes the actual V2 portal host, service names, ports, env contract, health semantics, canonical state paths, and rollback rules.

The sixth gap is end-to-end deployment regression coverage. The latest commit adds useful host, datum, analytics, and architecture-boundary tests, and the commit reports `122 tests OK`. That is solid. But those are still mostly code-level and local-host verifications. What still remains is one black-box suite for the deployed surface: `/portal`, `/portal/healthz`, `portal_instance=tff`, JSON public resource serving, admin shell launch, AWS read-only, AWS narrow-write failure modes, and analytics collect through the actual proxy path. That is the level that protects development from server drift and accidental routing regressions.

The seventh gap is UI-shell maturity. The new `portal.html` is enough as a cutover shell, but it is still a minimal status surface. For development quality, that is acceptable for now. For longer-term portal hardening, the shell should become a stable host for tool surfaces, not just a health page with a few cards. That is not the immediate blocker, but it is the next layer after operational hardening.

The eighth gap is readiness policy around datum materialization. `live_system_datum_store.py` correctly blocks legacy fallback and treats missing root-level files as warnings, which is good. But it also only warns when `data/system/sources/*.json` or `data/payloads/cache/*.json` are absent. You still need to decide whether those are legitimately optional in production or whether they should fail readiness. Right now the policy is lenient. Hardening means making that policy explicit.

The repo is therefore in a better state than before: the core cutover appears to be done, the V1 bridge path is intentionally excluded, canonical datum and analytics paths are enforced, and the portal host is now V2-native. What remains is mostly not another architectural pass. It is operational hardening.

Priority order for what still remains:
first, make deployment config fully repo-authoritative;
second, remove startup ambiguity and require explicit production config;
third, lock down and test the real auth/authorization edge;
fourth, add black-box deployed-surface smoke tests;
fifth, fix top-level V2 documentation drift.

The single next hardening move should be: codify the live systemd and nginx state as versioned infra, then add one deployment-readiness smoke suite against the actual routed `/portal` surface. That will remove the largest remaining source of drift.

---