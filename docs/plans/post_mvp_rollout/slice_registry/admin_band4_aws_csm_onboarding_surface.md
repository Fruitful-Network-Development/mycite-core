# Slice ID

`admin_band4.aws_csm_onboarding_surface`

## Status

`implemented_trusted_tenant_csm_onboarding`

## Purpose

Shell-owned, registry-backed orchestration for **trusted-tenant** canonical live AWS-CSM profile files (`mycite.service_tool.aws_csm.profile.v1`), mapping V1 provision-class actions to bounded writes with audit and read-after-write confirmation through the same visibility path as Band 1.

## Client value

Operators can progress mailbox onboarding (workflow initiation, SMTP staging handoff, verification capture paths, inbound enablement intent, confirmation steps) without V1-shaped HTTP routes or browser-owned shell state.

## Rollout band

`Admin Band 4 Trusted-Tenant AWS-CSM Onboarding`

## Exposure status

`trusted_tenant_csm_onboarding`

## Owning layers

- `packages/modules/cross_domain/aws_csm_onboarding/` — semantic transitions and policy (including explicit omission of default `replay_verification_forward`)
- `packages/ports/aws_csm_onboarding/` — profile store + cloud/evidence seams
- `packages/adapters/filesystem/aws_csm_onboarding_profile_store.py` — canonical profile persistence
- `instances/_shared/runtime/admin_aws_runtime.py` — `run_admin_aws_csm_onboarding`
- `instances/_shared/portal_host/app.py` — `POST /portal/api/v2/admin/aws/csm-onboarding` (not the V1 `/portal/api/admin/aws/profile/<id>/provision` shape)
- `instances/_shared/portal_host/static/v2_portal_shell.js` — inspector kind `csm_onboarding_form` (server-issued `submit_contract` only)

## Required ports

- `AwsCsmOnboardingProfileStorePort`
- `AwsCsmOnboardingCloudPort` (SES/S3/Route53/secrets/evidence adapters implement; default unconfigured cloud is fail-closed for evidence-gated actions)

## Required tests

- Integration: shell registry launch legality, audit + read-after-write, `replay_verification_forward` policy block, `confirm_verified` evidence gate
- Architecture: existing runtime / shell / sandbox boundary suites remain green

## Out of scope (this slice)

- Internal sandbox (Band 3) write rehearsal — remains read-only per T-008 unless a future task expands policy with docs + tests
- Legacy Lambda `replay_verification_forward` as a default operator path — omitted; optional gated compat is a separate product decision

## V1 evidence (non-authoritative)

- `MyCiteV1/instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py` — provision action dispatch (behavioral reference only)
