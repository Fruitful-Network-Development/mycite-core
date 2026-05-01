# AWS-CSM Onboarding Operational Realities Report

Date: 2026-04-23

Doc type: `operational-reality-report`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Initiative and Task Mapping

- Initiative: `INIT-AWS-CSM-ALIGNMENT`
- Task IDs:
  - `TASK-AWS-CSM-ALIGN-005`
  - `TASK-AWS-CSM-ALIGN-006`
  - `TASK-AWS-CSM-ALIGN-007`
  - `TASK-AWS-CSM-ALIGN-008`
  - `TASK-AWS-CSM-ALIGN-009`
  - `TASK-AWS-CSM-ALIGN-010`

## Scope

Capture operational realities observed during live AWS-CSM onboarding execution
for `nathan@cvccboard.org` with personal handoff target `n8seals@gmail.com`,
and convert those realities into tracked follow-on tasks.

## Realities Observed

1. **Execution runtime dependency gap**
   - AWS-CSM runtime action execution path encountered a `boto3` dependency absence
     in one execution context, which blocked action flow until manual AWS CLI fallback.
2. **Domain readiness convergence required direct action**
   - `cvccboard.org` required explicit SES identity creation and DNS record convergence
     (DKIM/SPF/DMARC plus receipt rule) before onboarding became operational.
3. **Verification-forward path captured but auto-forward evidence was inconsistent**
   - Confirmation email capture into S3 succeeded for `nathan@cvccboard.org`.
   - Automatic forward behavior required manual fallback to guarantee operator delivery.
4. **Secret handoff posture needs stronger guardrails**
   - Current operational flow can pressure manual/urgent credential transmission patterns.
   - Secure retrieval + rotation posture should be enforced as standard practice.
5. **Manual remediations can outrun state artifacts**
   - Profile/domain JSON state required reconciliation after manual AWS interventions
     to align UI/runtime status with authoritative cloud state.

## Taskization Decisions

### `TASK-AWS-CSM-ALIGN-005`

Establish execution-host dependency baseline and fail-closed checks for AWS-CSM
actions that rely on AWS SDK/runtime components.

Status: `done` (2026-04-23 refresh)

Delivered:

- Runtime dependency baseline is now surfaced in AWS-CSM payloads via
  `runtime_dependency_baseline` and checked before action execution.
- AWS-CSM actions now fail closed with `runtime_dependency_missing` when required
  modules are unavailable.
- Dependency fail-closed behavior is regression-tested in
  `MyCiteV2/tests/unit/test_portal_aws_route_sync.py`.
- Host remediation/runbook notes are documented in
  `docs/personal_notes/ec2_awscms_admin_iam_inventory.md`.

### `TASK-AWS-CSM-ALIGN-006`

Automate domain readiness convergence so SES identity, DNS, and receipt-rule
requirements are achieved through canonical actions with deterministic outcomes.

Status: `done` (2026-04-23 refresh)

Delivered:

- `create_domain` and `refresh_domain_status` now run full convergence steps
  (`ensure_domain_identity`, `sync_domain_dns`, `ensure_domain_receipt_rule`)
  before persisting domain readiness.
- Runtime action details now include `convergence_steps` for auditable parity
  between action execution and resulting readiness state.
- Regression coverage in `MyCiteV2/tests/unit/test_portal_aws_route_sync.py` and
  `MyCiteV2/tests/integration/test_portal_host_one_shell.py` now asserts
  converged domain onboarding reaches `ready_for_mailboxes`.
- Active seeded state remains aligned with converged parity in
  `deployed/fnd/private/utilities/tools/aws-csm/aws-csm-domain.cvccboard.json`.

### `TASK-AWS-CSM-ALIGN-007`

Harden confirmation-forward behavior by improving decision visibility and ensuring
eligible confirmation messages are automatically forwarded to operator targets.

Status: `done` (2026-04-23 refresh)

Delivered:

- Lambda verification handling now returns auditable per-message
  `verification_decisions` in runtime responses, including blocked/forwarded
  reason codes and classification labels.
- Forwarded decisions now include `forwarded_to` and `forward_message_id` in
  both Lambda logs and returned payloads.
- Blocked cases (for example untracked recipient / unreadable capture object)
  now produce explicit structured decision records instead of silent empty
  results.
- Unit coverage in
  `MyCiteV2/tests/unit/test_aws_csm_inbound_capture_lambda.py` asserts both
  blocked decision reasons and runtime response decision reporting.

### `TASK-AWS-CSM-ALIGN-008`

Enforce secure credential handoff posture and add emergency rotation/revocation
response for any manual secret disclosure path.

Status: `done` (2026-04-23 refresh)

Delivered:

- `send_handoff_email` no longer transmits reusable SMTP passwords in email body;
  handoff now sends non-secret connection metadata and controlled-retrieval
  instructions.
- Handoff copy now embeds explicit emergency rotation/revocation sequence for
  manual disclosure events.
- Contract posture has been codified in
  `docs/contracts/tool_operating_contract.md` under AWS-CSM secure handoff
  invariants.
- Adapter regression coverage now asserts plaintext password suppression and
  presence of controlled reveal/rotation guidance.

### `TASK-AWS-CSM-ALIGN-009`

Backfill state reconciliation logic so manual AWS interventions are normalized into
profile/domain artifacts and surfaced accurately in runtime payloads.

Status: `done` (2026-04-23 refresh)

Delivered:

- `refresh_domain_status` now executes convergence + refresh as a deterministic
  reconciliation path that rewrites stale domain snapshots to authoritative
  Route53/SES/receipt posture.
- Runtime responses expose convergence step traces for reconciliation audits.
- Unit regression in `MyCiteV2/tests/unit/test_portal_aws_route_sync.py` asserts
  stale domain state is normalized back to `ready_for_mailboxes`.
- Reconciled deployed artifacts:
  - `deployed/fnd/private/utilities/tools/aws-csm/aws-csm-domain.cvccboard.json`
  - `deployed/fnd/private/utilities/tools/aws-csm/aws-csm.cvccboard.nathan.json`

### `TASK-AWS-CSM-ALIGN-010`

Add end-to-end onboarding regression coverage that exercises profile creation,
SMTP staging, confirmation capture, forwarding decisions, and operator outcomes.

Status: `done` (2026-04-23 refresh)

Delivered:

- Integration flow coverage in
  `MyCiteV2/tests/integration/test_portal_host_one_shell.py` verifies profile
  creation, SMTP staging, handoff dispatch, capture, and confirmation
  progression on one-shell routing.
- Integration blocking-condition coverage now asserts profile-scoped actions
  return `profile_required` when no profile selection is present.
- Unit regression coverage in `MyCiteV2/tests/unit/test_portal_aws_route_sync.py`
  preserves fail-closed and operator-facing error semantics on blocked paths.

## Lifecycle and Consolidation Notes

- Decision: **extend existing stream** `STREAM-AWS-CSM-ALIGNMENT`.
- No new stream was created.
- No prior AWS-CSM canonical file was demoted; this report is additive follow-on
  evidence linked from the existing canonical AWS-CSM plan.

## Evidence Targets

- `docs/audits/aws_csm_operating_alignment_audit_plan_2026-04-23.md`
- `docs/audits/reports/aws_csm_comprehensive_audit_report_2026-04-23.md`
- `deployed/fnd/private/utilities/tools/aws-csm/aws-csm-domain.cvccboard.json`
- `deployed/fnd/private/utilities/tools/aws-csm/aws-csm.cvccboard.nathan.json`
- `MyCiteV2/packages/adapters/event_transport/aws_csm_inbound_capture_lambda.py`
- `MyCiteV2/packages/adapters/event_transport/aws_csm_onboarding_cloud.py`

## Validation Log

Validation commands executed for this planning/taskization update:

- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries`

Results:

- `test_contract_docs_alignment`: pass
- `test_state_machine_boundaries`: pass
