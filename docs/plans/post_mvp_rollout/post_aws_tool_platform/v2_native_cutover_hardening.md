# V2 Native Cutover Hardening

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This is the canonical closure packet after the V2-native portal cutover.

Use it to finish the remaining hardening work without reopening V1/V2 design
ambiguity or reintroducing alternate deployment shapes.

Status: completed closure packet. Use
[../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md)
for the formal closure statement and
[../current_planning_index.md](../current_planning_index.md) for the reopened
follow-on sequence.

## Current baseline

- V2-native portal host is the live `/portal` surface for FND and TFF.
- Admin shell, AWS read-only, AWS narrow-write, and canonical live AWS profile
  mapping are implemented.
- Bridge-era cutover work remains useful history, but it is no longer the
  default implementation path.
- `srv-infra` is the sole tracked deployment-truth repo for live V2 host
  manifests.

## Canonical execution sequence

This is the only active long-term sequence for reaching canonical modular V2:

1. make `srv-infra` the sole tracked deployment authority for the live V2 portal
2. make the V2 host fail fast on missing or ambiguous deployment inputs
3. codify the portal auth and audience boundary
4. add black-box deployment smoke that proves the live V2 boundary and stale V1 path removal
5. resolve [v1_retirement_execution_ledger.md](v1_retirement_execution_ledger.md)
6. close [../../phases/11_cleanup_and_v1_retirement_review.md](../../phases/11_cleanup_and_v1_retirement_review.md)
7. only then reopen deferred client-visible slices or later tool tracks

Alternative near-term sequences are intentionally disallowed.

## Modular ownership baseline

Use [../../../contracts/v2_surface_ownership_map.md](../../../contracts/v2_surface_ownership_map.md)
as the canonical repo-shape reference.

The critical boundaries are:

- `docs/` owns semantics and planning precedence.
- `instances/_shared/portal_host/` owns HTTP transport only.
- `instances/_shared/runtime/` owns runtime composition only.
- `packages/state_machine/` owns shell legality and state behavior.
- `packages/ports/` owns contracts.
- `packages/adapters/` owns concrete IO.
- `MyCiteV1/` remains migration evidence, not a structural template.

## Canonical tracked deployment truth

The live V2 portal deployment must be readable from `srv-infra`, not inferred
from remembered server edits.

Tracked deployment truth lives in:

- `/srv/repo/srv-infra/systemd/mycite-v2-fnd-portal.service`
- `/srv/repo/srv-infra/systemd/mycite-v2-tff-portal.service`
- `/srv/repo/srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`
- `/srv/repo/srv-infra/nginx/sites-available/fruitfulnetworkdevelopment.com.conf`
- `/srv/repo/srv-infra/nginx/sites-available/trappfamilyfarm.com.conf`
- `/srv/repo/srv-infra/scripts/deploy_portal.sh`
- `/srv/repo/srv-infra/scripts/check_drift.sh`
- `/srv/repo/srv-infra/scripts/verify_v2_portal_deploy_truth.sh`
- `/srv/repo/srv-infra/runtime_service_map.json`

`mycite-core/docs/` should describe architectural ownership and contracts, then
reference these tracked manifests for deployment truth.

## Live V2 service contract

The live portal units stay explicit per tenant in this pass. The required env
contract is:

- `PORTAL_INSTANCE_ID`
- `PUBLIC_DIR`
- `PRIVATE_DIR`
- `DATA_DIR`
- `MYCITE_ANALYTICS_DOMAIN`
- `MYCITE_WEBAPPS_ROOT`
- `MYCITE_V2_AWS_STATUS_FILE`
- `MYCITE_V2_AWS_AUDIT_FILE`
- `MYCITE_V2_ADMIN_AUDIT_FILE`

The host must fail startup when those values are missing, ambiguous, or point
at invalid runtime paths. The old implicit `fnd` fallback is not allowed.

## Auth and audience boundary

Use [../../../contracts/portal_auth_and_audience_boundary.md](../../../contracts/portal_auth_and_audience_boundary.md)
as the canonical contract.

The required split is:

- NGINX plus oauth2-proxy own browser auth.
- NGINX injects trusted `X-Portal-*` headers only on the local upstream boundary.
- V2 runtime owns audience legality and slice legality.
- `/portal/api/v2/...` is the only canonical admin JSON surface.
- `/portal/api/admin/aws/*` and `/portal/api/admin/paypal/*` are retired and
  must fail-closed.

## Verification packet

The hardening pass is not complete without black-box proof from the deployed
edge.

Required verification surfaces:

- `/srv/repo/srv-infra/scripts/check_drift.sh`
- `/srv/repo/srv-infra/scripts/verify_v2_portal_deploy_truth.sh`
- `MyCiteV2/tests/integration/test_v2_native_portal_host.py`
- `MyCiteV2/tests/architecture/test_v2_native_portal_host_boundaries.py`

The verification packet must prove:

- only `mycite-v2-*` portal units are active
- `6101` and `6203` are listening
- `5101` and `5203` are not part of the live posture
- public `portal.* /healthz` succeeds
- unauthenticated `/portal/system` is denied or redirected by oauth
- legacy `/portal/api/admin/aws/*` and `/portal/api/admin/paypal/*` fail-closed
- loopback V2 shell and AWS routes still work for FND and TFF
- analytics still resolves under `/srv/webapps/clients/<domain>/...`

## Active workstreams

### 1. Repo orientation cleanup

Make the high-traffic docs read like the current repo, not the earlier scaffold
or bridge phase.

Required outcomes:

- root repo docs no longer describe V2 as scaffold-only
- current planning docs distinguish active work from records
- bridge-era cutover docs read as history when appropriate
- canonical ownership docs point readers to V2 surfaces first

### 2. Deployment contract codification

Make the live host shape reproducible from repo-owned sources instead of
depending on remembered server-side edits.

Required outcomes:

- service names, ports, env contract, and proxy expectations are documented in one place
- repo-owned deployment manifests or equivalent tracked infra sources exist for the live V2 host
- rollback expectations are explicit
- no tracked V1-style portal unit or template unit remains as a co-equal future path

### 3. Startup fail-fast configuration

The V2 host should refuse to start when critical deployment inputs are missing
or ambiguous.

Required outcomes:

- tenant selection is explicit
- state roots are explicit
- `MYCITE_V2_AWS_STATUS_FILE` is explicit where AWS surfaces are exposed
- audit and analytics sinks are validated early enough to fail closed
- module imports remain safe for tests and library use while the WSGI entrypoint fails fast at service startup

### 4. Auth and audience boundary contract

The deployed edge must say exactly where authentication and tenant
authorization are enforced.

Required outcomes:

- one canonical document states proxy-vs-host auth responsibility
- unauthorized requests are tested at the real deployed edge or an equivalent black-box boundary
- admin shell and AWS surfaces fail closed for the wrong audience
- legacy `/portal/api/admin/aws/*` and `/portal/api/admin/paypal/*` are removed or return `410`

### 5. Black-box deployed-surface smoke

Protect the live cutover with tests that exercise the real routed surface, not
only local module imports.

Required outcomes:

- smoke coverage for `/portal` and `/portal/healthz`
- smoke coverage for shell launch and AWS read-only/narrow-write
- tenant-selection coverage for FND and TFF
- analytics path verification through the deployed portal boundary
- repo-tracked proof that legacy `5101` and `5203` are no longer part of the live path

### 6. V1 retirement review

Treat V1 removal as a controlled review, not a symbolic cleanup.

Required outcomes:

- identify any remaining live dependency on `MyCiteV1`
- identify any remaining bridge-only route or adapter still serving production needs
- archive or delete only after the V2-native replacement is proven and recorded
- resolve [v1_retirement_execution_ledger.md](v1_retirement_execution_ledger.md)

## Exit criteria

This plan is complete when:

- the top-level docs unambiguously describe a modular V2 repo
- current live deployment inputs are tracked in `srv-infra` and referenced from repo-owned contracts
- the deployed edge has black-box smoke coverage
- bridge-era cutover docs are clearly historical
- V1 retention or removal is decided through a resolved execution ledger and recorded review rather than drift
- deferred follow-on slices remain frozen until the retirement gate is closed

## Out of scope

- broad V1 parity restoration
- new bridge-only route growth
- CTS-GIS, AGRO-ERP, or unrelated follow-on tool work before hardening minimums pass
