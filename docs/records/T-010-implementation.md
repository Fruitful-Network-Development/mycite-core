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

# Verification report

**Task:** T-010 — Implement V2 shell-owned AWS-CSM mailbox onboarding workflow (V1 provision parity)  
**Role:** verifier  
**Date:** 2026-04-11

**Task type:** `repo_only` (host and live layers: **not applicable** per task scope).

---

## 1. Exact commands used

```text
cd /srv/repo/mycite-core && PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries MyCiteV2.tests.architecture.test_runtime_composition_boundaries MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries MyCiteV2.tests.integration.test_admin_aws_read_only_runtime MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime MyCiteV2.tests.unit.test_admin_tool_platform_contract MyCiteV2.tests.unit.test_state_machine_admin_shell MyCiteV2.tests.integration.test_admin_runtime_composition MyCiteV2.tests.integration.test_admin_runtime_platform_contracts -v
```

(This is `execution.repo_test_command` from `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` after YAML `>-` folding to one shell line.)

Supplemental repo checks (confirm acceptance; captured 2026-04-11):

```text
grep -E 'provision|admin/aws/profile' /srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/app.py; echo "exit:$?"
```

```text
exit:1
```

(`grep` exit status **1** = no lines matched; stdout empty.)

```text
grep -Ri 'mycitev1' /srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/; echo "exit:$?"
```

```text
exit:1
```

---

## 2. Exact captured stdout/stderr

### 2.1 `unittest` (canonical `repo_test_command`)

```text
test_imports_remain_inward_core_or_state_machine_only (MyCiteV2.tests.architecture.test_state_machine_boundaries.StateMachineBoundaryTests.test_imports_remain_inward_core_or_state_machine_only) ... ok
test_source_contains_no_runtime_tool_or_sandbox_leakage (MyCiteV2.tests.architecture.test_state_machine_boundaries.StateMachineBoundaryTests.test_source_contains_no_runtime_tool_or_sandbox_leakage) ... ok
test_runtime_imports_compose_inward_layers_only (MyCiteV2.tests.architecture.test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_imports_compose_inward_layers_only) ... ok
test_runtime_source_contains_no_framework_or_legacy_provider_logic (MyCiteV2.tests.architecture.test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_source_contains_no_framework_or_legacy_provider_logic) ... ok
test_runtime_surface_stays_single_path_without_flavor_expansion (MyCiteV2.tests.architecture.test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_surface_stays_single_path_without_flavor_expansion) ... ok
test_tool_sandbox_imports_stay_orchestration_only (MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries.SandboxesToolBoundaryTests.test_tool_sandbox_imports_stay_orchestration_only) ... ok
test_live_aws_profile_file_is_mapped_at_runtime (MyCiteV2.tests.integration.test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_live_aws_profile_file_is_mapped_at_runtime) ... ok
test_missing_status_source_is_reported_explicitly (MyCiteV2.tests.integration.test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_missing_status_source_is_reported_explicitly) ... ok
test_shell_registry_entry_launches_aws_read_only_entrypoint (MyCiteV2.tests.integration.test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_shell_registry_entry_launches_aws_read_only_entrypoint) ... ok
test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged) ... ok
test_live_aws_profile_narrow_write_updates_canonical_live_artifact (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_live_aws_profile_narrow_write_updates_canonical_live_artifact) ... ok
test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit) ... ok
test_write_requires_audit_path_before_applying (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_write_requires_audit_path_before_applying) ... ok
test_internal_cannot_launch_production_read_only_via_registry_launch (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_internal_cannot_launch_production_read_only_via_registry_launch) ... ok
test_production_read_only_unchanged_for_trusted_tenant (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_production_read_only_unchanged_for_trusted_tenant) ... ok
test_registry_includes_distinct_sandbox_descriptor (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_registry_includes_distinct_sandbox_descriptor) ... ok
test_registry_surface_lists_all_catalog_tools (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_registry_surface_lists_all_catalog_tools) ... ok
test_sandbox_read_only_happy_path (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_sandbox_read_only_happy_path) ... ok
test_shell_entry_allows_internal_sandbox_surface (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_shell_entry_allows_internal_sandbox_surface) ... ok
test_trusted_tenant_cannot_launch_sandbox_slice (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_trusted_tenant_cannot_launch_sandbox_slice) ... ok
test_begin_onboarding_applies_audit_and_read_after_write (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_begin_onboarding_applies_audit_and_read_after_write) ... ok
test_confirm_verified_fail_closed_without_cloud_evidence (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_confirm_verified_fail_closed_without_cloud_evidence) ... ok
test_confirm_verified_succeeds_when_cloud_port_attests_evidence (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_confirm_verified_succeeds_when_cloud_port_attests_evidence) ... ok
test_internal_audience_cannot_launch_onboarding_slice (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_internal_audience_cannot_launch_onboarding_slice) ... ok
test_registry_includes_onboarding_tool_for_trusted_tenant (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_registry_includes_onboarding_tool_for_trusted_tenant) ... ok
test_replay_verification_forward_is_policy_blocked (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_replay_verification_forward_is_policy_blocked) ... ok
test_descriptor_rejects_writable_tool_without_audit_or_read_after_write (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_descriptor_rejects_writable_tool_without_audit_or_read_after_write) ... ok
test_runtime_entrypoint_catalog_is_static_and_serializable (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_runtime_entrypoint_catalog_is_static_and_serializable) ... ok
test_shared_runtime_envelope_shape_is_fixed (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_shared_runtime_envelope_shape_is_fixed) ... ok
test_tool_descriptors_have_stable_drop_in_shape (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_tool_descriptors_have_stable_drop_in_shape) ... ok
test_band_name_is_fixed_for_admin_band0 (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_band_name_is_fixed_for_admin_band0) ... ok
test_catalog_and_registry_are_serializable_and_shell_owned (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_catalog_and_registry_are_serializable_and_shell_owned) ... ok
test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant) ... ok
test_non_internal_audience_is_denied_for_admin_band0 (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_non_internal_audience_is_denied_for_admin_band0) ... ok
test_request_contract_rejects_invalid_schema_and_audience (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_request_contract_rejects_invalid_schema_and_audience) ... ok
test_request_defaults_to_internal_home_status (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_request_defaults_to_internal_home_status) ... ok
test_shell_chrome_round_trips_in_request_dict (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_shell_chrome_round_trips_in_request_dict) ... ok
test_shell_entry_alias_resolves_to_home_status (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_shell_entry_alias_resolves_to_home_status) ... ok
test_tool_registry_surface_is_available_and_aws_redirects_to_registry (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_tool_registry_surface_is_available_and_aws_redirects_to_registry) ... ok
test_default_admin_shell_entry_returns_internal_home_status (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_default_admin_shell_entry_returns_internal_home_status) ... ok
test_non_internal_request_is_denied_without_surface_payload (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_non_internal_request_is_denied_without_surface_payload) ... ok
test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline) ... ok
test_shell_chrome_mediates_inspector_collapse_in_tool_mode (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_shell_chrome_mediates_inspector_collapse_in_tool_mode) ... ok
test_tool_registry_surface_is_catalog_driven_and_deny_by_default (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_tool_registry_surface_is_catalog_driven_and_deny_by_default) ... ok
test_trusted_tenant_aws_read_only_slice_composes_tool_mode (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_trusted_tenant_aws_read_only_slice_composes_tool_mode) ... ok
test_current_admin_entrypoints_return_shared_envelope_shape (MyCiteV2.tests.integration.test_admin_runtime_platform_contracts.AdminRuntimePlatformIntegrationTests.test_current_admin_entrypoints_return_shared_envelope_shape) ... ok
test_tool_registry_descriptors_match_runtime_entrypoint_ids (MyCiteV2.tests.integration.test_admin_runtime_platform_contracts.AdminRuntimePlatformIntegrationTests.test_tool_registry_descriptors_match_runtime_entrypoint_ids) ... ok

----------------------------------------------------------------------
Ran 47 tests in 0.107s

OK

```

Shell exit code: **0**.

---

## 3. Acceptance mapping: pass/fail by criterion

| Criterion | Result | Notes |
|-----------|--------|-------|
| T-009 parity in code or `replay_verification_forward` deferred with documented default + tests | **pass** | `test_replay_verification_forward_is_policy_blocked`; implementation report documents omission |
| All listed V1 actions have named V2 mapping in implementation report | **pass** | `reports/T-010-implementation.md` mapping table |
| No new routes copying V1 `/portal/api/admin/aws/profile/<id>/provision` | **pass** | §1 `app.py` grep empty; v2 route `POST /portal/api/v2/admin/aws/csm-onboarding` present in repo |
| Shell composition authoritative; client JS only renders server-issued requests | **pass** | `v2_portal_shell.js` uses `submit_contract` / `contract.route` for POST body and URL |
| Band 1/2/3 (T-008) unittest modules still pass | **pass** | §2.1 includes read-only, narrow-write, sandbox modules — all `ok` |
| `execution.repo_test_command` passes independently | **pass** | §2.1, exit 0 |

---

## 4. Repo/host/live mismatches

none.

(Host and live: not applicable to acceptance for this task.)

---

## 5. Final verdict

**PASS** — Canonical unittest command exited 0 with 47/47 tests OK; repo spot-checks support route-shape and no-V1-import acceptance; no contradictions found between evidence and task acceptance for `repo_only` scope.

---

## 6. Recommended next status

`verified_pass` / `verification_result: pass` (task YAML updated). Lead may set `status: resolved` per `closure_rule` after review.

# Verifier → Lead: T-010

## Verification command (verbatim)

```text
cd /srv/repo/mycite-core && PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries MyCiteV2.tests.architecture.test_runtime_composition_boundaries MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries MyCiteV2.tests.integration.test_admin_aws_read_only_runtime MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime MyCiteV2.tests.unit.test_admin_tool_platform_contract MyCiteV2.tests.unit.test_state_machine_admin_shell MyCiteV2.tests.integration.test_admin_runtime_composition MyCiteV2.tests.integration.test_admin_runtime_platform_contracts -v
```

## Evidence summary

- Exit code **0**; **47** tests, all **OK** (runtime ~0.1s).
- Full stdout transcript is in `reports/T-010-verification.md` §5.

## Verdict

**PASS** — all task acceptance items satisfied for this `repo_only` scope; host/live not required.

## Mismatches

none

## Recommended final status

- Set task YAML: `status: verified_pass`, `verification_result: pass`, `execution.current_role: lead`, `execution.next_role: lead`.
- Lead may set `status: resolved` when satisfied with `closure_rule` (implementation + verification reports + handoffs).

# Implementer → Verifier: T-010

## Files changed (summary)

- Shell / runtime: `admin_shell.py`, `hanus_shell/__init__.py`, `runtime_platform.py`, `admin_aws_runtime.py`, `admin_runtime.py`, `portal_host/app.py`, `v2_portal_shell.js`
- Domain / ports / adapters: `packages/modules/cross_domain/aws_csm_onboarding/*`, `packages/ports/aws_csm_onboarding/*`, `packages/adapters/filesystem/aws_csm_onboarding_profile_store.py`, `packages/adapters/filesystem/__init__.py`
- Docs: `shell_region_kinds.md`, `slice_registry/admin_band4_aws_csm_onboarding_surface.md`
- Tests: new `test_admin_aws_csm_onboarding_runtime.py`; catalog-count updates in listed integration/unit tests
- Task: `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` — `repo_test_command` extended; `status` / `execution` advanced to verifier

## Commands run

Implementer ran the extended unittest set (47 tests) including architecture + updated composition/platform contracts; all passed. See `reports/T-010-implementation.md` §3 for the exact command block.

## Reports written

- `reports/T-010-implementation.md`

## Unresolved risks

- Default `AwsCsmOnboardingUnconfiguredCloudPort` does not perform real SES/S3/Route53/Lambda work; production onboarding still needs adapter implementations without changing shell contracts.
- `replay_verification_forward` is intentionally rejected at the semantic layer unless product reopens it behind an explicit gate.

## What you must verify independently

1. Run **`execution.repo_test_command` from `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` verbatim** and paste stdout/stderr into `reports/T-010-verification.md`.
2. Confirm Band 1/2/3 non-regression (same modules as in `repo_test_command`).
3. Confirm onboarding-specific tests: registry legality, `begin_onboarding` audit + read-after-write, replay policy error code, `confirm_verified` evidence fail-closed vs fake cloud pass.

## Recommended next task status

After your evidence: `verified_pass` or `verified_fail`; update `verification_result` accordingly. Task YAML `execution.current_role` should return to **lead** per `tasks/README.md` after verifier completion.


# Lead → Implementer: T-010

## Task classification

- **ID:** T-010 — Implement V2 shell-owned AWS-CSM mailbox onboarding workflow (V1 provision parity)
- **primary_type:** `repo_only` (no `live_systems`; closure via repo tests + reports per task)
- **Verifier:** required (`execution.requires_verifier: true`). After implementation, **next role is verifier**; verifier runs `execution.repo_test_command` verbatim and fills `reports/T-010-verification.md`.

## Exact files to read first

1. `reports/T-009-investigation.md` — parity table, gap classifications, sandbox vs trusted-tenant posture (**before coding**).
2. Authority stack (in order), as needed for design decisions:
   - `MyCiteV2/docs/ontology/structural_invariants.md`
   - `MyCiteV2/docs/decisions/decision_record_0012_post_aws_tool_platform_stabilization.md`
   - `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md`
3. Task contract: `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` (acceptance, `closure_rule`, `repo_test_command`).

Then work within **scope.repo_paths** from that YAML (shell, admin runtime, portal host, narrow write / visibility modules, ports, adapters, sandboxes, tests, slice registry docs).

## Exact goal

Add **registry-backed, shell-owned** AWS-CSM mailbox onboarding orchestration for **trusted-tenant canonical live profile files**: bounded writes, read-after-write, audit where writes occur, explicit fail-closed behavior when prerequisites are missing. Encode **V1-equivalent state transitions and evidence checks** (especially `confirm_verified`) in a **semantic layer** without importing MyCiteV1. **Do not** clone V1 Flask route shapes; **do not** treat browser JS as alternate shell truth — `shell_composition` and server-issued activity/dispatch remain authoritative.

## Constraints that matter

- **Domain logic** must not depend on adapters/tools/hosts in ways that violate structural invariants; keep orchestration seams via ports + test doubles in integration tests.
- **T-008 sandbox** stays **internal read-only** unless this task explicitly extends policy with slice docs + tests.
- **No** new HTTP routes copying V1 shape `/portal/api/admin/aws/profile/<id>/provision`.
- **V1** admin provision handlers are **evidence only** — no V1 structural template copy.
- **`replay_verification_forward`:** legacy Lambda compatibility — default V2 path is portal-native capture; replay is **optional, gated, or explicitly deferred** with **repo proof** (tests + documented policy in implementation report).
- Satisfy or explicitly defer (only as above) the **T-009 parity table** in code/docs/tests per acceptance.
- **Each** V1 action must have a **named V2 mapping** (verb, entrypoint, or bounded field set) documented in `reports/T-010-implementation.md`:  
  `begin_onboarding`, `prepare_send_as`, `stage_smtp_credentials`, `capture_verification`, `refresh_provider_status`, `refresh_inbound_status`, `enable_inbound_capture`, `replay_verification_forward`, `confirm_receive_verified`, `confirm_verified`.
- **Non-regression:** existing unittest modules for Band 1 / 2 / 3 AWS admin surfaces must keep passing; append new test module paths to `execution.repo_test_command` when added (e.g. onboarding integration test already named in command).
- Update **`MyCiteV2/docs/contracts/shell_region_kinds.md`** when new region kinds or submit contracts are emitted; add **slice registry** documentation for any new admin band / surface id.

## Required outputs

- Code/config/docs/tests per **required_outputs** and **implementation_requirements** in the task YAML.
- **`reports/T-010-implementation.md`** using the standard template (`reports/templates/implementation_report_template.md`) — separate repo / host / live sections; host/live may state **not applicable** for this task.
- **`reports/handoffs/T-010/implementer_to_verifier.md`** per `tasks/README.md` §8 (files changed, commands run, reports written, risks, what verifier must prove, recommended next status).

Do **not** write `verification_result: pass|fail` or mark the task **resolved** — that is verifier / lead respectively.

## Stop conditions

- Stop and set task to **`blocked`** with reasons in the implementation report and handoff if: authority conflicts are unresolved, T-008 sandbox read-only posture would be violated without explicit task-scoped policy + docs + tests, or required paths/schema are missing.
- When implementation is complete: set **`status: verification_pending`**, **`execution.current_role: verifier`**, **`execution.next_role: lead`** (verifier runs next; verifier then returns control to lead per `tasks/README.md`).

## Recommended task YAML after implementation

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`

The verifier updates `verification_result` and `status` (`verified_pass` / `verified_fail`) and writes `reports/handoffs/T-010/verifier_to_lead.md`; the lead may set **`resolved`** only per **`closure_rule`** in the task YAML.