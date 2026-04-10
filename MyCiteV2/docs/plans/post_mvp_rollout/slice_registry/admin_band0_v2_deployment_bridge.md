# Slice ID

`admin_band0.v2_deployment_bridge`

## Status

`specified_not_implemented`

## Purpose

Make the tested V2 admin runtime reachable from the live portal boundary without recreating V1 route or package drift.

## Client value

This is the operational cutover slice that turns V2 from a tested runtime base into a deployable admin surface.

## Rollout band

`Admin Band 0 Internal Admin Replacement`

## Exposure status

`internal-only`

## Owning layers

- `MyCiteV2/instances/_shared/runtime/` remains the V2 runtime owner
- `MyCiteV2/packages/adapters/portal_runtime/` may own a V2 host adapter if Shape A is chosen
- `MyCiteV1/instances/_shared/runtime/flavors/*/app.py` may receive a tiny bridge mount only if Shape B is chosen

## Required ports

- none for shell entry
- live-state adapter seam required before trusted-tenant AWS exposure

## Required adapters

- one portal runtime bridge or host adapter
- one live AWS profile mapping adapter before `admin.aws.narrow_write` is exposed against live state

## Required runtime composition

- must call the existing V2 runtime entrypoints:
  - `admin.shell_entry`
  - `admin.aws.read_only`
  - `admin.aws.narrow_write`
- must not add a second shell entry
- must not add uncataloged runtime entrypoints

## Required tests

- bridge route or host-adapter tests
- unknown-slice denial tests
- audience denial tests
- no-secret payload tests
- no dynamic discovery or package scanning architecture tests
- V2 Admin Band 0, AWS read-only, and AWS narrow-write regression tests

## Client exposure gates

- starts internal-only
- cannot expose trusted-tenant AWS read-only until live-state mapping is explicit
- cannot expose AWS narrow-write until read-after-write and audit use the canonical live artifact

## Out of scope

- Maps
- AGRO-ERP
- PayPal
- analytics
- newsletter-admin route parity
- sandbox/workbench parity
- root compatibility symlinks

## V1 evidence and drift warnings

- `/etc/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`
- `/etc/systemd/system/fnd-portal.service`
- `/etc/systemd/system/tff-portal.service`
- `MyCiteV1/instances/_shared/runtime/flavors/fnd/app.py`
- `MyCiteV1/instances/_shared/runtime/flavors/tff/app.py`

Warnings:

- do not make V1 own V2 shell legality
- do not recreate V1 provider-admin routes in V2
- do not use root-level package compatibility links
- do not make a generated V2 status snapshot the write authority

## Implementation ordering

1. confirm bridge shape
2. mount `admin.shell_entry`
3. add bridge tests and architecture checks
4. add live AWS read-only state mapping
5. expose `admin.aws.read_only`
6. add canonical live write mapping
7. expose `admin.aws.narrow_write`

## Frozen questions

- whether Shape A or Shape B is the preferred first production bridge
- exact route names for the bridge surface
- exact field mapping from live AWS profile JSON to V2 AWS status snapshot
