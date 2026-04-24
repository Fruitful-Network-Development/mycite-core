# AWS-CSM Operational Recovery Audit Report

Date: 2026-04-24

Doc type: `audit-report`
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

## Audit Objective

Translate current AWS-CSM operational concerns into a tracked recovery program
that preserves prior closure evidence while re-opening delivery for deployed-FND
parity, onboarding operability, performance hardening, and SQL MOS authority.

## Recovery Findings

1. **Per-domain user onboarding is not materially verified in deployed FND**
   - Prior stream closure states completion, but deployed behavior indicates missing
     or inaccessible per-domain user management flow.
2. **Onboarding handoff flow requires explicit personal-email routing guarantees**
   - Workflow must support: create user -> send SMTP instructions -> route
     confirmation emails to personal inbox for link completion.
3. **Onboard viability state is not reliably surfaced**
   - Runtime/UI should expose a deterministic status state after confirmation.
4. **Portal load latency remains materially high (10-20s)**
   - Additional optimization pass is required, focused on fallback/safeguard bloat.
5. **Residual JSON duplication risk is now narrowed to explicit non-datum operational metadata**
   - Active AWS-CSM runtime mailbox and newsletter projections now read through
     shared filesystem adapters instead of bespoke file scans.
   - Retained JSON artifacts are cataloged as non-datum/config exceptions:
     `tool.*.aws-csm.json`, `spec.json`, `newsletter.*.profile.json`,
     `newsletter.*.contacts.json`, and `private/config.json`.
6. **Current source does not show removal of the AWS-CSM onboarding surface**
   - The present runtime/UI still exposes domain gallery, add-user flow, onboarding
     actions, and handoff cards in source, so missing deployed behavior is more
     likely deployment/runtime/data-state drift than code-path deletion.
7. **Execution-host dependency parity is now an explicit recovery risk**
   - `520c349` introduced fail-closed runtime dependency gating for guarded AWS-CSM
     actions, and the current local audit environment reports `boto3` unavailable.
     That creates a concrete deployment-parity verification task rather than a
     speculative code-regression claim.

## Commit-History Observations

Recent commits relevant to behavior drift/reconciliation:

1. `852eb0f` (`2026-04-23`)
   - Changed `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py` during the
     one-shell family-contract migration.
   - Risk class: deployed shell/runtime packaging mismatch.
   - Verification target: confirm the deployed AWS-CSM surface still loads the
     promoted runtime contract markers and current static workspace bundle.
2. `520c349` (`2026-04-24`)
   - The only post-closure commit that touched the AWS-CSM workspace JS, onboarding
     cloud adapter, inbound capture lambda, and runtime together.
   - Added `runtime_dependency_baseline` fail-closed enforcement, structured
     verification-forward decisions, secure handoff copy, and empty-state handling.
   - Risk class: action-host dependency mismatch or stale deployed JS/runtime.
   - Verification target: exercise `create_domain`, `create_profile`,
     `send_handoff_email`, and confirmation-forward flows on the deployed host.
3. `455f270` (`2026-04-24`)
   - Added NIMM/AITAS envelope compilation, mutation lifecycle metadata, and
     canonical mutation endpoint descriptors in `portal_aws_runtime.py`.
   - Risk class: deployed action contract mismatch between old and new payload
     shapes, not feature removal.
   - Verification target: confirm deployed host accepts both legacy action payloads
     and enriched action results without dropping AWS-CSM mutations.

## Code-Surface Audit Result

- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_aws_workspace.js`
  still renders the domain gallery, add-user form, onboarding cards, and handoff
  view for selected profiles/domains.
- `MyCiteV2/packages/adapters/event_transport/aws_csm_onboarding_cloud.py`
  still preserves the personal-email handoff workflow while withholding reusable
  SMTP passwords from email delivery.
- `MyCiteV2/packages/adapters/event_transport/aws_csm_inbound_capture_lambda.py`
  now records structured forward/blocked decisions rather than silently returning.
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  still assembles the AWS-CSM workspace and action route, but now fail-closes
  guarded actions when required runtime modules are missing.
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  now projects mailbox and newsletter operational metadata through
  `FilesystemAwsCsmToolProfileStore` and `FilesystemAwsCsmNewsletterStateAdapter`
  instead of re-scanning profile/newsletter JSON files directly.
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  now emits canonical source fingerprints for the runtime, AWS-CSM workspace JS,
  and onboarding cloud adapter so deployed-FND parity checks can reference
  stable repo-side markers even though no second promoted JS/runtime bundle is
  versioned under `deployed/fnd/`.

Status linkage:

- `TASK-AWS-CSM-RECOVERY-001`: `done`
- `TASK-AWS-CSM-RECOVERY-002`: `done`
- `TASK-AWS-CSM-RECOVERY-003`: `done`
- `TASK-AWS-CSM-RECOVERY-004`: `done`
- `TASK-AWS-CSM-RECOVERY-005`: `done`
- `TASK-AWS-CSM-RECOVERY-006`: `done`
- `TASK-AWS-CSM-RECOVERY-007`: `done`

## Task-Linked Recovery Plan

### `TASK-AWS-CSM-RECOVERY-001` (done)

Commit-window and deployed-state audit completed. Result: current source still
contains the AWS-CSM onboarding and handoff surfaces; active risk is narrowed to
deployment mismatch, runtime dependency baseline, stale promoted assets, or state
divergence rather than outright source removal.

### `TASK-AWS-CSM-RECOVERY-002` (done)

Source-backed onboarding restoration is now evidenced:

- The AWS-CSM workspace still exposes the per-domain add-user flow with domain
  association and personal-email destination fields.
- Runtime handoff state now persists `handoff_email_sent_to`,
  `handoff_email_message_id`, and `handoff_email_sent_at` in workflow metadata.
- The onboarding handoff panel surfaces that dispatch metadata back to the
  operator without storing reusable SMTP passwords in profile JSON.
- End-to-end test coverage asserts the created profile, handoff dispatch
  metadata, and password redaction posture.

### `TASK-AWS-CSM-RECOVERY-003` (done)

Runtime and panel state projection is now explicit and deterministic:

- Mailbox profile projections now emit one canonical onboarding state plus summary.
- The AWS-CSM interface panel and compact mailbox cards show that canonical state
  instead of requiring operators to infer progress from raw workflow/provider/
  verification fields.
- Unit coverage now proves the projection can emit `pending`, `forwarded`,
  `confirmed`, and `onboard`.
- Surface rebuilds after actions reuse the same projection, which removes the
  prior manual-refresh ambiguity in the panel’s onboarding readout.

### `TASK-AWS-CSM-RECOVERY-004` (done)

AWS-CSM performance recovery evidence is now recorded:

- Measuring `run_portal_aws_csm(...)` against `deployed/fnd/private` produced:
  - domain gallery median `10.53 ms`, p95 `22.33 ms`
  - domain transition median `11.29 ms`, p95 `18.61 ms`
  - profile onboarding transition median `10.89 ms`, p95 `12.35 ms`
- These post-change source/runtime measurements are materially below the
  reported 10-20 second recovery baseline, which indicates the current repo-side
  AWS-CSM projection/render path is no longer the dominant latency source.
- `v2_portal_aws_workspace.js` now binds one delegated `submit` listener and one
  delegated `click` listener on the workspace root instead of rebuilding
  per-control listener sets on every rerender.
- Architecture regression coverage now locks in that delegated-binding posture
  and forbids reintroduction of the old `[data-aws-*]` rebinding loops.

### `TASK-AWS-CSM-RECOVERY-005` (done)

Residual JSON pathway and duplication audit is now evidenced:

- The active AWS-CSM runtime no longer scans mailbox profile files with bespoke
  `glob("aws-csm.*.json")` logic and instead projects mailbox rows through the
  shared `FilesystemAwsCsmToolProfileStore`.
- Newsletter workspace rows now load through
  `FilesystemAwsCsmNewsletterStateAdapter` instead of direct
  `newsletter.*.profile.json` scans in the runtime surface.
- Retained JSON artifacts are now explicitly cataloged as non-datum/config
  exceptions rather than MOS datum authority: `tool.*.aws-csm.json`, `spec.json`,
  `newsletter.*.profile.json`, `newsletter.*.contacts.json`, and
  `private/config.json`.
- Architecture and unit regressions now fail if the active AWS-CSM runtime
  reintroduces direct mailbox/newsletter file-scan patterns.

### `TASK-AWS-CSM-RECOVERY-006` (done)

Canonical closure sync is now complete:

- The contextual stream `STREAM-AWS-CSM-OPERATIONAL-RECOVERY` is now marked
  `completed` in `docs/plans/contextual_system_manifest.yaml`.
- The compatibility initiative `INIT-AWS-CSM-OPERATIONAL-RECOVERY` is now marked
  `completed` in `docs/plans/planning_audit_manifest.yaml`, with the recovery
  report recorded as the closure report.
- Contextual and compatibility task boards now mark every
  `TASK-AWS-CSM-RECOVERY-*` item `done`.
- Delegation focus has advanced to the next remaining non-done task under the
  ordering rules: `TASK-CTSGIS-BLOCKER-001`, which remains explicitly blocked.

### `TASK-AWS-CSM-RECOVERY-007` (done, injected from TASK-AWS-CSM-RECOVERY-001)

Deployed/runtime parity is now evidenced against promoted FND private state:

- `deployed/fnd/private/config.json` exposes `aws_csm.enabled: true` and mounts
  `tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json` under the FND tool configuration.
- Running `run_portal_aws_csm(...)` against `deployed/fnd/private` projects the
  active AWS-CSM surface contract with `domain_count=4`, `profile_count=20`,
  and `selected_domain_onboarding.readiness_state=ready_for_mailboxes` for
  `cvccboard.org`.
- Querying `aws-csm.cvccboard.nathan` from the same deployed private state
  surfaces `selected_profile_onboarding.onboarding_state=forwarded` and
  `handoff_email_sent_to=n8seals@gmail.com`, which matches the promoted profile
  JSON and confirms that the current runtime still renders the recovered
  onboarding handoff state on real FND data.
- The surface now publishes canonical source fingerprints for:
  - `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_aws_workspace.js`
  - `MyCiteV2/packages/adapters/event_transport/aws_csm_onboarding_cloud.py`
- Explicit waiver: the repo does not carry a second promoted JS/runtime bundle
  under `deployed/fnd/`, so asset parity is tracked through these canonical
  source fingerprints plus the deployed private-state runtime projection rather
  than by diffing two versioned JS/runtime copies.
- Guarded action execution on the available FND host remains intentionally
  fail-closed: `run_portal_aws_csm_action(... send_handoff_email ...)` returns
  `runtime_dependency_missing` because `boto3` is absent, and the action result
  exposes the remediation path to install the missing module before execution.

Observed source fingerprints:

- `portal_aws_runtime.py`: `e912a31ef2611f03420dc515eb6ef5e6a4cb2051b051370dfd05817f17d9923b`
- `v2_portal_aws_workspace.js`: `b9a216218dd047c4533a287aa948d474d44cea3d3e50e679527bdccd8e6b3cef`
- `aws_csm_onboarding_cloud.py`: `fc1d09ec6028923c1fe4fa55c9605ae76843f3d446d29a505dbc47303972e5f5`

## Lifecycle and Consolidation Notes

- Decision: **new stream added** (`STREAM-AWS-CSM-OPERATIONAL-RECOVERY`).
- Prior stream `STREAM-AWS-CSM-ALIGNMENT` remains `completed` foundation evidence.
- `STREAM-AWS-CSM-OPERATIONAL-RECOVERY` now also moves to `completed` after all
  linked recovery tasks reached `done` with synchronized contextual and
  compatibility closure evidence.
- No historical reports deleted; old and new stream boundaries are explicit.
- New task injected: `TASK-AWS-CSM-RECOVERY-007` under the same active recovery
  stream; no closed IDs were reused.

## Evidence Targets

- `docs/plans/aws_csm_operational_recovery_plan_2026-04-24.md`
- `docs/audits/reports/aws_csm_comprehensive_audit_report_2026-04-23.md`
- `docs/audits/reports/aws_csm_onboarding_operational_realities_report_2026-04-23.md`
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_aws_workspace.js`
- `MyCiteV2/packages/adapters/event_transport/aws_csm_onboarding_cloud.py`
- `MyCiteV2/packages/adapters/event_transport/aws_csm_inbound_capture_lambda.py`
- `MyCiteV2/tests/integration/test_portal_host_one_shell.py`
- `MyCiteV2/tests/unit/test_portal_aws_route_sync.py`
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- `deployed/fnd/private/config.json`
- `deployed/fnd/private/utilities/tools/aws-csm/tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json`
- `deployed/fnd/private/utilities/tools/aws-csm/aws-csm-domain.cvccboard.json`
- `deployed/fnd/private/utilities/tools/aws-csm/aws-csm.cvccboard.nathan.json`

## Validation Log

Validation commands executed for this planning-system update:

- `python3 -m unittest MyCiteV2.tests.unit.test_portal_aws_route_sync`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 - <<'PY' ... run_portal_aws_csm(... private_dir='deployed/fnd/private' ...) ... PY`
- `python3 - <<'PY' ... run_portal_aws_csm_action(... send_handoff_email ...) ... PY`
- `python3 - <<'PY' ... run_portal_aws_csm(...) latency samples over 25 iterations ... PY`
- `python3 - <<'PY' ... static delegated-listener count probe for v2_portal_aws_workspace.js ... PY`
- `python3 - <<'PY' ... yaml.safe_load(...) ... PY`

Result summary:

- AWS-CSM route-sync unit suite: pass (`Ran 11 tests`)
- one-shell architecture suite: pass (`Ran 23 tests`)
- contract-doc alignment suite: pass (`Ran 13 tests`)
- deployed FND private-state projection probe: pass (`tool configured/enabled`, `domain_count=4`, `profile_count=20`, `cvccboard.org` readiness and handoff state projected)
- deployed guarded-action dependency probe: pass for expected fail-closed posture (`runtime_dependency_missing`, `missing_modules=['boto3']`, remediation emitted)
- AWS-CSM latency probe against deployed FND private state: pass (`median 10.53-11.29 ms`, `p95 12.35-22.33 ms`)
- delegated-listener static probe: pass (`submit=1`, `click=1`, `[data-aws-*] querySelectorAll rebinding loops=0`)
- YAML parse check: pass for contextual and compatibility manifests/task boards
