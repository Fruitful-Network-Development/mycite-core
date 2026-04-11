# Slice ID

`admin_band0.v2_deployment_bridge`

## Status

`implemented_internal_bridge`

## Record-only note

This slice is already implemented. Keep this file only as slice-spec history.
Use [../../../records/15-cut_over.md](../../../records/15-cut_over.md) for the implemented bridge record and [../current_planning_index.md](../current_planning_index.md) for current active planning.
The V1-host mount has now been removed from active apps; the retained bridge
adapter is quarantined historical evidence only. See
[../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md).

## Historical purpose

Make the tested V2 admin runtime reachable from the live portal boundary without recreating V1 route or package drift.

## Client value

This is the operational cutover slice that turns V2 from a tested runtime base into a deployable admin surface.

## Rollout band

`Admin Band 0 Internal Admin Replacement`

## Exposure status

`internal-only`

## Historical owning layers

- `MyCiteV2/instances/_shared/runtime/` remained the V2 runtime owner
- `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py` carried the bridge-era transport adapter
- `MyCiteV1/instances/_shared/runtime/flavors/*/app.py` temporarily mounted the bridge during cutover; that mount is now removed

## Required ports

- none for shell entry
- live-state adapter seam required before trusted-tenant AWS exposure

## Historical adapters

- one portal runtime bridge adapter: `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py`
- one live AWS profile mapping adapter before `admin.aws.narrow_write` was exposed against live state

## Historical runtime composition

- called the existing V2 runtime entrypoints:
  - `admin.shell_entry`
  - `admin.aws.read_only`
  - `admin.aws.narrow_write`
- did not add a second shell entry
- did not add uncataloged runtime entrypoints

## Retained evidence

- bridge route tests: `MyCiteV2/tests/integration/test_v2_deployment_bridge_shape_b.py` now run only with `MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS=1`
- historical architecture checks: `MyCiteV2/tests/architecture/test_v2_deployment_bridge_boundaries.py` now run only with `MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS=1`
- active retirement guard: `MyCiteV2/tests/architecture/test_v1_retirement_boundaries.py`
- native-host regression truth: `MyCiteV2/tests/integration/test_v2_native_portal_host.py`

## Historical client exposure gates

- starts internal-only
- cannot expose trusted-tenant AWS read-only until live-state mapping is explicit
- cannot expose AWS narrow-write until read-after-write and audit use the canonical live artifact

Historical gate result:

- `admin.shell_entry`, `admin.aws.read_only`, and `admin.aws.narrow_write` were mounted through the V1 host bridge during cutover.
- The canonical live boundary has since moved to the V2-native host.
- The bridge itself is retained only for retirement evidence and record replay.

## Out of scope

- Maps
- AGRO-ERP
- PayPal
- analytics
- newsletter-admin route parity
- sandbox/workbench parity
- root compatibility symlinks

## Retained drift evidence

- `/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`
- `MyCiteV1/instances/_shared/runtime/flavors/fnd/app.py`
- `MyCiteV1/instances/_shared/runtime/flavors/tff/app.py`

Warnings:

- do not make V1 own V2 shell legality
- do not recreate V1 provider-admin routes in V2
- do not use root-level package compatibility links
- do not make a generated V2 status snapshot the write authority

## Historical resolution

- Shape B was the bridge-era cutover shape.
- Route surface:
  - `GET /portal/api/v2/admin/bridge/health`
  - `POST /portal/api/v2/admin/shell`
  - `POST /portal/api/v2/admin/aws/read-only`
  - `POST /portal/api/v2/admin/aws/narrow-write`
- The active V1 host mount has been removed, and the remaining bridge module is quarantined.
