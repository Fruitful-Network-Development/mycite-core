# Live Cutover Review - 2026-04-10

## Scope

Reviewed V1/V2 isolation and live deployment posture for:

- `/srv/repo/mycite-core/MyCiteV1/`
- `/srv/repo/mycite-core/MyCiteV2/docs/archive/`
- `/srv/mycite-state/instances/`
- `/etc/systemd/system/fnd-portal.service`
- `/etc/systemd/system/tff-portal.service`
- `/etc/systemd/system/mycite-portal@.service`
- `/etc/systemd/system/paypal-proxy.service`
- `/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`

## Findings

- V1 code and deployed mirrors have been moved under `MyCiteV1/`.
- V2 code is isolated under `MyCiteV2/` and does not import V1 packages.
- Root-level legacy code directories are absent, preserving a two-directory V1/V2 isolation boundary.
- V2 post-AWS admin runtime, shell registry, AWS read-only, and AWS narrow-write tests are green.
- Live FND and TFF portal services still run the V1 Flask/Gunicorn host.
- The live `/portal` route is not yet mounted to a V2 host or V2 bridge.
- No live state file under `/srv/mycite-state/instances/` declares `MyCiteV2`, `admin.shell_entry`, or `mycite.v2.admin`.
- The portal systemd units had stale root-runtime paths. They were updated to point directly at `MyCiteV1` so live V1 hosting remains restartable without recreating root compatibility links.
- `paypal-proxy.service` had a stale root package path. It was updated to point directly at `MyCiteV1/packages`.

## Changes Applied

- Removed accidentally recreated root compatibility symlinks from the working tree and git index, preserving the explicit `MyCiteV1/` plus `MyCiteV2/` layout.
- Updated live systemd unit files to use direct `MyCiteV1` paths for working directory, repo root, portals root, and `run_portal.sh`.
- Updated `paypal-proxy.service` to use a direct `MyCiteV1/packages` working directory.
- Reloaded systemd after unit updates.

## Verification

- V2 unit tests: `35 OK`
- V2 contract tests: `10 OK`
- V2 adapter tests: `9 OK`
- V2 integration tests: `11 OK`
- V2 architecture tests: `25 OK`
- V2 runtime compile check: passed
- FND V1 app import from the new direct service path: passed
- TFF V1 app import from the new direct service path: passed
- `systemd-analyze verify` for FND, TFF, template, and PayPal units: passed
- Local health checks:
  - `http://127.0.0.1:5101/healthz` returned FND OK
  - `http://127.0.0.1:5203/healthz` returned TFF OK

## Cutover Status

Not complete.

V2 is validated as an admin runtime base, but it is not yet the deployed `/portal` web host. Pointing FND/TFF directly at `MyCiteV2/instances/_shared/runtime` would fail because V2 intentionally has runtime entrypoint callables, not a Flask/Gunicorn host or route surface.

## Required Next Change

Add one explicit deployment bridge before claiming `/portal` uses V2:

- either a V2-owned web host that serves `/portal` and public boundaries, or
- a V2-owned bridge mounted by the existing V1 host that exposes only cataloged V2 entrypoints.

That bridge must keep these constraints:

- no route-level parity porting
- no direct provider-admin fallback routes
- no dynamic registry scanning
- no duplicate AWS write state that can drift from canonical live state
- one source of truth for any V2 AWS status snapshot or migrated write target
