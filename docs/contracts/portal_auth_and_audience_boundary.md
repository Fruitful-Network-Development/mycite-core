# Portal Auth And Audience Boundary

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file defines the canonical browser-auth and audience split for the live V2
portal.

## Canonical boundary

- `srv-infra` owns the tracked deployment manifests for NGINX, oauth2-proxy,
  and the live `mycite-v2-*` portal units.
- NGINX plus oauth2-proxy own browser authentication for `portal.*`.
- NGINX injects trusted `X-Portal-User`, `X-Portal-Username`,
  `X-Portal-Roles`, and `X-Request-Id` headers only on the loopback upstream
  boundary it controls.
- `MyCiteV2/instances/_shared/portal_host/` owns HTTP transport only after
  ingress trust has already been established.
- `MyCiteV2/instances/_shared/runtime/` and
  `MyCiteV2/packages/state_machine/` own audience legality, shell legality, and
  slice legality.
- The host must fail closed when the forwarded audience is not allowed. It must
  not silently widen trust beyond the local upstream boundary.

## Canonical routes

- `/portal` and `/portal/system/*` are browser entry surfaces behind
  oauth2-proxy.
- `/portal/api/v2/...` is the only canonical admin JSON surface.
- `/portal/api/admin/control/*` is a privileged host-control surface owned by
  `srv-infra` and additionally guarded by `X-Control-Token`.
- `/portal/api/admin/fnd/*`, `/portal/api/admin/aws/*`, and
  `/portal/api/admin/paypal/*` are retired compatibility paths and must
  fail-closed.

## Deployment-truth reference

Use `srv-infra` for the tracked deployment truth:

- `/srv/repo/srv-infra/systemd/mycite-v2-fnd-portal.service`
- `/srv/repo/srv-infra/systemd/mycite-v2-tff-portal.service`
- `/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`
- `/srv/repo/srv-infra/scripts/check_drift.sh`
- `/srv/repo/srv-infra/scripts/verify_v2_portal_deploy_truth.sh`

`mycite-core/docs/` defines the contract and the architectural ownership. It
does not duplicate host-manifest authority.
