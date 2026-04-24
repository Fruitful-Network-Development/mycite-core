# AWS-CSM Operating Alignment Audit Plan

Date: 2026-04-23

Doc type: `audit-plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Initiative and Task Mapping

- Initiative: `INIT-AWS-CSM-ALIGNMENT`
- Task IDs:
  - `TASK-AWS-CSM-ALIGN-001`
  - `TASK-AWS-CSM-ALIGN-002`
  - `TASK-AWS-CSM-ALIGN-003`
  - `TASK-AWS-CSM-ALIGN-004`
  - `TASK-AWS-CSM-ALIGN-005`
  - `TASK-AWS-CSM-ALIGN-006`
  - `TASK-AWS-CSM-ALIGN-007`
  - `TASK-AWS-CSM-ALIGN-008`
  - `TASK-AWS-CSM-ALIGN-009`
  - `TASK-AWS-CSM-ALIGN-010`

## Purpose

Establish one canonical AWS-CSM alignment stream that converts the 2026-04-23
comprehensive audit into a tracked execution queue with explicit contract
updates, runtime/UI parity work, and report-backed closure evidence.

## Canonical Contract Links

- `docs/contracts/surface_catalog.md`
- `docs/contracts/route_model.md`
- `docs/contracts/tool_operating_contract.md`
- `docs/contracts/mutation_contract.md`

## Scope

1. Audit and baseline publication for AWS-CSM architecture/UX conformance.
2. NIMM/AITAS migration contract design for AWS-CSM onboarding actions.
3. Cross-domain user grouping query/runtime model definition.
4. Shell adapter/fallback/navigation parity hardening for AWS renderer paths.
5. Operational onboarding reliability hardening from live-run realities.

## Baseline Findings Anchors

- `docs/audits/reports/aws_csm_comprehensive_audit_report_2026-04-23.md`
- `docs/audits/reports/tools_ui_implementation_mismatch_report_2026-04-16.md`
- `docs/audits/reports/performance_weight_speed_report_2026-04-16.md`
- `docs/audits/reports/aws_csm_onboarding_operational_realities_report_2026-04-23.md`

## Operational Realities Backlog (2026-04-23)

Observed while executing manual onboarding against live AWS state:

1. Runtime dependency mismatch can block action execution (`boto3` not available in one execution context).
2. Domain readiness convergence required explicit SES identity and DNS synchronization during onboarding.
3. Verification-forward routing captured the confirmation message, but automatic forward behavior required manual fallback confirmation.
4. Secret handoff posture needs explicit policy to avoid routine plaintext SMTP credential transmission.
5. Manual AWS interventions can leave profile/domain state artifacts stale unless reconciled.

These realities map to:

- `TASK-AWS-CSM-ALIGN-005`
- `TASK-AWS-CSM-ALIGN-006`
- `TASK-AWS-CSM-ALIGN-007`
- `TASK-AWS-CSM-ALIGN-008`
- `TASK-AWS-CSM-ALIGN-009`
- `TASK-AWS-CSM-ALIGN-010`

## Execution Sequence

1. Publish canonical stream plan/report and ensure YAML synchronization.
2. Produce contract delta draft for NIMM/AITAS onboarding directives.
3. Define and review cross-domain user grouping query semantics.
4. Implement adapter/fallback/navigation parity hardening and regression tests.
5. Execute operational realities backlog for dependency, forwarder, handoff, and reconciliation hardening.
6. Publish follow-on closure report and transition lifecycle as appropriate.

## Contract Delta Drafts (2026-04-23)

### `TASK-AWS-CSM-ALIGN-002` draft

- Canonical directive verbs for onboarding execution remain mutation-class:
  `manipulate` (with action granularity carried as `action_kind` in payload).
- Canonical envelope fields for AWS-CSM actions:
  - `schema=mycite.v2.nimm.envelope.v1`
  - `directive.target_authority=aws_csm`
  - `directive.payload.action_kind`
  - `directive.payload.action_payload`
  - `aitas.attention/intention/time/archetype/scope`
- Route/contract deltas are captured in:
  - `docs/contracts/route_model.md`
  - `docs/contracts/tool_operating_contract.md`

### `TASK-AWS-CSM-ALIGN-003` draft

- Added cross-domain user grouping query semantics:
  - `view=users`
  - `user_group=<group_id>`
  - `user=<user_key>`
- Runtime projection contract (read-only posture):
  - grouped `user_rows` contain `user_key`, associated domains/profiles,
    verification status summaries, and canonical navigation requests
  - mutation remains action-contract-only (`POST /portal/api/v2/system/tools/aws-csm/actions`)
    and is not enabled through grouped-user projection rendering.

## Evidence Targets

- `docs/audits/reports/aws_csm_comprehensive_audit_report_2026-04-23.md`
- `docs/audits/reports/aws_csm_onboarding_operational_realities_report_2026-04-23.md`
- Follow-on implementation evidence under `docs/audits/reports/`
- Updated contracts and test artifacts tied to task-level acceptance criteria

## Exit Criteria

- Each `TASK-AWS-CSM-ALIGN-*` item is `done` in both task boards.
- Contract deltas and runtime/UI parity changes are evidenced and test-backed.
- Canonical stream pointers remain singular (one active plan + one active report).
