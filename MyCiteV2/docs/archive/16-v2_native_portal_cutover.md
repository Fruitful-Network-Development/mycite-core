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

___