# AWS-CSM Operational Recovery Plan

Date: 2026-04-24

Doc type: `recovery-plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Initiative and Task Mapping

- Initiative: `INIT-AWS-CSM-OPERATIONAL-RECOVERY`
- Task IDs:
  - `TASK-AWS-CSM-RECOVERY-001`
  - `TASK-AWS-CSM-RECOVERY-002`
  - `TASK-AWS-CSM-RECOVERY-003`
  - `TASK-AWS-CSM-RECOVERY-004`
  - `TASK-AWS-CSM-RECOVERY-005`
  - `TASK-AWS-CSM-RECOVERY-006`
  - `TASK-AWS-CSM-RECOVERY-007`

## Purpose

Re-open AWS-CSM delivery as a new active stream focused on deployed-FND recovery:
restore per-domain onboarding management, enforce personal-email confirmation
forwarding, expose deterministic onboard status, reduce AWS-CSM load latency, and
remove residual JSON/legacy duplication that conflicts with SQL MOS authority.

## Lifecycle Decision

- Existing completed stream `STREAM-AWS-CSM-ALIGNMENT` remains closure evidence.
- New work is tracked in new active stream
  `STREAM-AWS-CSM-OPERATIONAL-RECOVERY` to avoid rewriting closure history.
- Canonical active artifacts for the new stream:
  - Plan: `docs/plans/aws_csm_operational_recovery_plan_2026-04-24.md`
  - Report: `docs/audits/reports/aws_csm_operational_recovery_audit_report_2026-04-24.md`

## Commit-History Recovery Anchors

Recent branch history suggests potential drift windows between completed alignment
and currently observed deployed behavior:

- `455f270` (`YAML stage and excuted unification`)
- `520c349` (`Refienment of YAML tasks ... aws service tool considerations`)
- `ea2abd8` (`Completion of shell, lense, script, state boundies ...`)
- `4b1d197` (`One-shell post-unification cleanup and compatibility retirement ...`)

`TASK-AWS-CSM-RECOVERY-001` now narrows these windows as follows:

- `852eb0f` is the shell-family/runtime migration checkpoint. It changes runtime
  packaging, but does not remove the AWS-CSM onboarding surface.
- `520c349` is the highest-risk live-operability window. It adds fail-closed
  runtime dependency enforcement, auto domain-readiness convergence, structured
  verification-forward decisions, and empty-state rendering changes.
- `455f270` adds NIMM/AITAS action-envelope wiring and canonical mutation endpoint
  metadata without removing legacy `action_kind` + `action_payload` handling.

Audit conclusion: current source control shows additive AWS-CSM onboarding/runtime
work, not removal of the per-domain onboarding panel. The recovery gap is therefore
more likely deployment/runtime/data-state mismatch than source deletion.

## Scope

1. Commit-history and deployment-drift recovery audit for AWS-CSM.
2. Interface Panel per-domain user onboarding management restoration.
3. Personal-email SMTP instruction and confirmation-forward delivery workflow.
4. Explicit onboard-state projection and UI indicator.
5. Performance pass for fallback/safeguard bloat and load latency.
6. Residual datum JSON path and duplicated legacy code retirement plan.
7. Deployed host/runtime parity verification for action hosts and promoted assets.

## Execution Sequence

1. `TASK-AWS-CSM-RECOVERY-001` complete: commit-window audit narrowed drift to
   deployment/runtime/data-state mismatch, with `520c349` and `455f270` identified
   as the main verification windows.
2. `TASK-AWS-CSM-RECOVERY-002` complete: the onboarding panel now keeps the
   per-domain add-user flow, personal-email handoff destination, and auditable
   handoff dispatch metadata (`sent_to`, `message_id`, `sent_at`) visible without
   persisting reusable SMTP secrets in profile JSON.
3. `TASK-AWS-CSM-RECOVERY-003` complete: mailbox projections and the interface
   panel now expose deterministic onboarding states and summaries using one
   canonical projection: `pending`, `forwarded`, `confirmed`, and `onboard`.
4. `TASK-AWS-CSM-RECOVERY-005` complete: active AWS-CSM runtime projections now
   read mailbox and newsletter operational JSON through shared filesystem
   adapters instead of bespoke file scans, while `tool.*.aws-csm.json`,
   `spec.json`, `newsletter.*.profile.json`, `newsletter.*.contacts.json`, and
   `private/config.json` remain explicit non-datum/config exceptions.
5. `TASK-AWS-CSM-RECOVERY-007` complete: the repo now emits canonical AWS-CSM
   source-surface fingerprints for runtime/JS/cloud surfaces, and deployed FND
   private state has been exercised against those surfaces to confirm tool
   exposure, domain/profile projection parity, and fail-closed dependency
   remediation when guarded actions run without `boto3`.
6. `TASK-AWS-CSM-RECOVERY-004` complete: local AWS-CSM runtime measurements
   against promoted FND private state now sit around 10-11 ms median with p95
   under 23 ms, and the workspace renderer uses delegated root listeners
   instead of rerender-time per-control rebinding loops.
7. Publish closure-progress evidence under `TASK-AWS-CSM-RECOVERY-006`.

## Acceptance-Evidence Anchors

- `docs/audits/reports/aws_csm_operational_recovery_audit_report_2026-04-24.md`
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_aws_workspace.js`
- `MyCiteV2/packages/adapters/event_transport/aws_csm_onboarding_cloud.py`
- `MyCiteV2/packages/adapters/event_transport/aws_csm_inbound_capture_lambda.py`
- `MyCiteV2/tests/unit/test_portal_aws_route_sync.py`
- `docs/audits/reports/performance_weight_speed_report_2026-04-16.md`

## Canonical Contract Links

- `docs/contracts/surface_catalog.md`
- `docs/contracts/route_model.md`
- `docs/contracts/tool_operating_contract.md`
- `docs/contracts/mutation_contract.md`
