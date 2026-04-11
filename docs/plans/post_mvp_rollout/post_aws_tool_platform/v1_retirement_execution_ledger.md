# V1 Retirement Execution Ledger

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file is the resolved execution ledger for phasing out the V1 paradigm
after the V2-native portal cutover.

Closure record:
[../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md)

## Ledger rule

- Every remaining V1 dependency must be classified before new client-visible
  expansion work starts.
- Each row must end in exactly one disposition:
  - `remove`
  - `quarantine`
  - `retain_temporarily_with_explicit_exception`
  - `historical_only`
- No hidden V1 runtime dependency is allowed to survive outside this ledger.

## Execution sequence

1. Confirm the live V2 host, deployment contract, auth boundary, and smoke
   coverage are stable enough to judge V1 residue accurately.
2. Walk each surface below and set its disposition.
3. Remove or quarantine residue in small verified batches.
4. Record any temporary exceptions with owner, reason, and removal trigger.
5. Close [../../phases/11_cleanup_and_v1_retirement_review.md](../../phases/11_cleanup_and_v1_retirement_review.md).
6. Only then reopen deferred Band 1 or later tool work.

## Final resolution ledger

| Surface | Disposition | Owner | Current status | Rationale | Evidence or closure rule |
| --- | --- | --- | --- | --- | --- |
| `srv-infra/systemd/fnd-portal.service` | `remove` | tracked infra manifests | deleted from tracked infra; canonical service is `mycite-v2-fnd-portal.service` | V1-style unit names are no longer part of live deployment truth | `srv-infra/systemd/`, `scripts/check_drift.sh`, `scripts/verify_v2_portal_deploy_truth.sh` |
| `srv-infra/systemd/tff-portal.service` | `remove` | tracked infra manifests | deleted from tracked infra; canonical service is `mycite-v2-tff-portal.service` | V1-style unit names are no longer part of live deployment truth | `srv-infra/systemd/`, `scripts/check_drift.sh`, `scripts/verify_v2_portal_deploy_truth.sh` |
| `srv-infra/systemd/mycite-portal@.service` | `remove` | tracked infra manifests | deleted so explicit per-tenant V2 units remain the only tracked deployment shape | the templated bridge-era unit is not a co-equal V2 future path | `srv-infra/systemd/`, `runtime_service_map.json` |
| `portal.* /portal/api/admin/aws/*` | `remove` | edge routing and auth boundary | retired at the edge and fail-closed | canonical admin JSON lives only under `/portal/api/v2/...` | `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`, `scripts/verify_v2_portal_deploy_truth.sh` |
| `portal.* /portal/api/admin/paypal/*` | `remove` | edge routing and auth boundary | retired at the edge and fail-closed | canonical admin JSON lives only under `/portal/api/v2/...` | `srv-infra/nginx/sites-available/portal.fruitfulnetworkdevelopment.com.conf`, `scripts/verify_v2_portal_deploy_truth.sh` |
| implicit V2 host tenant fallback | `remove` | V2 native host | removed; `PORTAL_INSTANCE_ID` is required and must agree with `PORTAL_RUNTIME_FLAVOR` when both are set | tenant selection must stay explicit for stable modular V2 deployment | `MyCiteV2/instances/_shared/portal_host/app.py`, `MyCiteV2/tests/integration/test_v2_native_portal_host.py` |
| `MyCiteV1/` | `historical_only` | repo history and migration evidence | retained in-repo, but no live deployment or active V2 planning depends on it | V1 remains evidence, not a structural template or active dependency | [../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md), `MyCiteV2/tests/architecture/test_v1_retirement_boundaries.py` |
| V1 app bridge registrations in `MyCiteV1/instances/_shared/runtime/flavors/{fnd,tff}/app.py` | `remove` | retired V1 host apps | removed from the V1 FND and TFF apps | no active code path should present the V1 host bridge as a normal V2 surface | `MyCiteV1/instances/_shared/runtime/flavors/fnd/app.py`, `MyCiteV1/instances/_shared/runtime/flavors/tff/app.py`, `MyCiteV2/tests/architecture/test_v1_retirement_boundaries.py` |
| package-root bridge exports in `MyCiteV2/packages/adapters/portal_runtime/__init__.py` | `remove` | V2 adapter package boundary | removed; the package root exports no bridge symbols | active code must not treat the bridge as a normal V2 adapter surface | `MyCiteV2/packages/adapters/portal_runtime/__init__.py`, `MyCiteV2/tests/architecture/test_v1_retirement_boundaries.py` |
| V1-host bridge adapter `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py` | `quarantine` | V2 adapter historical evidence | retained only as direct-path bridge-era compatibility evidence; not part of the live V2 boundary | preserves cutover history while preventing package-root reuse | `MyCiteV2/packages/adapters/portal_runtime/README.md`, `MyCiteV2/tests/integration/test_v2_deployment_bridge_shape_b.py` |
| bridge-specific tests under `MyCiteV2/tests/*bridge*` | `historical_only` | test evidence | retained as cutover evidence and opt-in only behind `MYCITE_ENABLE_HISTORICAL_BRIDGE_TESTS=1` | canonical verification is native-host tests plus `srv-infra` smoke | `MyCiteV2/tests/README.md`, `MyCiteV2/tests/integration/test_v2_deployment_bridge_shape_b.py`, `MyCiteV2/tests/architecture/test_v2_deployment_bridge_boundaries.py` |
| bridge prompt in `docs/plans/post_mvp_rollout/agent_prompt_templates.md` | `remove` | active planning surfaces | rewritten as historical review guidance, not an implementation prompt | no active planning surface should point implementers toward Shape B work | `docs/plans/post_mvp_rollout/agent_prompt_templates.md`, `MyCiteV2/tests/architecture/test_v1_retirement_boundaries.py` |
| bridge-era contract and slice docs under `docs/plans/post_mvp_rollout/` | `historical_only` | planning history | retained as record-only cutover design and slice history | preserves evidence without presenting a co-equal deployment path | `deployment_bridge_contract.md`, `cutover_execution_sequence.md`, `slice_registry/admin_band0_v2_deployment_bridge.md` |
| bridge-era and cutover records under `docs/records/` | `historical_only` | completion records | kept as completion evidence only | active planning now starts from the closure record and reopened follow-on slice order | [../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md), [../current_planning_index.md](../current_planning_index.md) |

## Remaining rule

Any new V1 residue discovered after this pass must be added here before follow-on
Band 1 or later tool work resumes.

## Exit criteria

Closed on 2026-04-11. Every row has a resolved disposition, and Phase 11 now
cites the closure record instead of open retirement questions.
