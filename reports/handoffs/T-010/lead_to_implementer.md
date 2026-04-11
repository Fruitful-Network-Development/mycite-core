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