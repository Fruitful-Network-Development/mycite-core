# Implementation report

**Task:** T-010 — Implement V2 shell-owned AWS-CSM mailbox onboarding workflow (V1 provision parity)  
**Role:** implementer  
**Date:** 2026-04-11

**Task type:** `repo_only`

---

## 1. Repo findings

- Post-T-008 baseline already exposed Band 1 read-only, Band 2 narrow write, and Band 3 internal sandbox read-only via `build_admin_tool_registry_entries` and `run_admin_aws_*` entrypoints; there was no trusted-tenant onboarding orchestration slice.
- `reports/T-009-investigation.md` parity table required a new bounded-write/onboarding path, explicit `replay_verification_forward` handling, and `confirm_verified` evidence semantics without V1 imports.

---

## 2. Changes made

**Structural / runtime**

- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` — Admin Band 4 constants, `admin_band4.aws_csm_onboarding_surface`, registry entry (`admin.aws.csm_onboarding`), tool/composition mappings.
- `MyCiteV2/packages/state_machine/hanus_shell/__init__.py` — Export new symbols.
- `MyCiteV2/instances/_shared/runtime/runtime_platform.py` — Onboarding request/surface schemas, recovery reference, `AdminRuntimeEntrypointDescriptor` for `run_admin_aws_csm_onboarding`.
- `MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py` — `run_admin_aws_csm_onboarding` with launch gate, audit, read-after-write via `AwsOperationalVisibilityService` + live profile adapter.
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py` — Shell composition branch for onboarding tool; inspector `csm_onboarding_form` with server-issued `submit_contract`.
- `MyCiteV2/instances/_shared/portal_host/app.py` — `POST /portal/api/v2/admin/aws/csm-onboarding` (not the V1 provision URL shape).

**Domain module (semantic layer)**

- `MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/service.py` — Cataloged `onboarding_action` dispatch, profile merge, `AwsCsmOnboardingPolicyError` for replay omission and evidence fail-closed path.
- `MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/unconfigured_cloud.py` — Default cloud port (no evidence until adapters exist).
- `MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/__init__.py` — Package exports.

**Ports / adapters**

- `MyCiteV2/packages/ports/aws_csm_onboarding/` — `AwsCsmOnboardingProfileStorePort`, `AwsCsmOnboardingCloudPort`, command/outcome/policy types.
- `MyCiteV2/packages/adapters/filesystem/aws_csm_onboarding_profile_store.py` — Filesystem store for canonical live profile JSON.
- `MyCiteV2/packages/adapters/filesystem/__init__.py` — Re-export store.

**Template / rendering**

- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js` — `csm_onboarding_form` inspector branch (POST body from `submit_contract` only).

**Documentation**

- `MyCiteV2/docs/contracts/shell_region_kinds.md` — Band 4 tool mode + `csm_onboarding_form` contract.
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band4_aws_csm_onboarding_surface.md` — Slice registry entry.

**Tests / contracts**

- `MyCiteV2/tests/integration/test_admin_aws_csm_onboarding_runtime.py` — New integration coverage (registry, begin, replay policy, confirm_verified gates, cloud fake).
- Updated catalog cardinality expectations in: `test_admin_aws_csm_sandbox_runtime.py`, `test_admin_runtime_composition.py`, `test_admin_runtime_platform_contracts.py`, `test_admin_tool_platform_contract.py`, `test_state_machine_admin_shell.py`.
- `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` — Append onboarding test module to `execution.repo_test_command`; lifecycle → `verification_pending` / verifier.

### V1 action → V2 mapping (acceptance)

| V1 action | V2 mapping |
|-----------|------------|
| `begin_onboarding` | `POST …/v2/admin/aws/csm-onboarding` with `onboarding_action: begin_onboarding` → `workflow.initiated` + `initiated_at` on canonical profile |
| `prepare_send_as` | Same entrypoint, action `prepare_send_as` → workflow SMTP staging markers + `smtp.staging_state` |
| `stage_smtp_credentials` | Same entrypoint + `AwsCsmOnboardingCloudPort.supplemental_profile_patch` merge (e.g. handoff material); local staging markers |
| `capture_verification` | Action updates `verification` / `inbound` capture-request fields; cloud port supplies merge fragments when wired |
| `refresh_provider_status` | Action sets provider refresh markers; SES snapshot via cloud patch |
| `refresh_inbound_status` | Action sets inbound `last_refresh_requested_at` |
| `enable_inbound_capture` | Action sets inbound MX/receipt intent + workflow timestamp |
| `replay_verification_forward` | **Omitted by default:** `AwsCsmOnboardingPolicyError` code `replay_verification_forward_not_enabled` (see integration test) |
| `confirm_receive_verified` | Action sets `inbound.receive_verified` and related receive state |
| `confirm_verified` | Action merges verification/provider/workflow/inbound **only if** `AwsCsmOnboardingCloudPort.gmail_confirmation_evidence_satisfied` is true (fail-closed; integration tests) |

---

## 3. Commands run

```text
cd /srv/repo/mycite-core &&
PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest
MyCiteV2.tests.architecture.test_state_machine_boundaries
MyCiteV2.tests.architecture.test_runtime_composition_boundaries
MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries
MyCiteV2.tests.integration.test_admin_aws_read_only_runtime
MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime
MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime
MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime
MyCiteV2.tests.unit.test_admin_tool_platform_contract
MyCiteV2.tests.unit.test_state_machine_admin_shell
MyCiteV2.tests.integration.test_admin_runtime_composition
MyCiteV2.tests.integration.test_admin_runtime_platform_contracts -v
```

```text
.................................................
----------------------------------------------------------------------
Ran 47 tests in 0.079s

OK
```

---

## 4. Tests run

Same command as §3 (matches `execution.repo_test_command` in the task YAML after append).

---

## 5. Host state (deploy / install)

not applicable

---

## 6. Live HTTP / operational checks

not applicable

---

## 7. Remaining gaps or blockers

- **Production AWS IO:** `AwsCsmOnboardingUnconfiguredCloudPort` returns empty supplemental patches and denies Gmail evidence until real SES/S3/Route53/Secrets adapters implement `AwsCsmOnboardingCloudPort`; repo tests use `_FakeOnboardingCloud` only where needed.
- **Verifier:** `reports/T-010-verification.md` must be produced by the verifier with verbatim transcripts per `tasks/README.md`.

---

## 8. Recommended next status

`verification_pending` — independent verifier should run `execution.repo_test_command` verbatim and record output in `reports/T-010-verification.md`.
