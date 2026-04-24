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
5. **Residual JSON datum presence indicates legacy duplication risk**
   - Active path should remain SQL MOS authority only; residual JSON paths must be
     cataloged and either retired or explicitly scoped as non-datum exceptions.
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

Status linkage:

- `TASK-AWS-CSM-RECOVERY-001`: `done`
- `TASK-AWS-CSM-RECOVERY-002` through `TASK-AWS-CSM-RECOVERY-006`: `pending`
- `TASK-AWS-CSM-RECOVERY-007`: `pending`

## Task-Linked Recovery Plan

### `TASK-AWS-CSM-RECOVERY-001` (done)

Commit-window and deployed-state audit completed. Result: current source still
contains the AWS-CSM onboarding and handoff surfaces; active risk is narrowed to
deployment mismatch, runtime dependency baseline, stale promoted assets, or state
divergence rather than outright source removal.

### `TASK-AWS-CSM-RECOVERY-002` (pending)

Restore clean Interface Panel onboarding surface for per-domain user creation
with personal-email destination and SMTP-credential instruction dispatch.

### `TASK-AWS-CSM-RECOVERY-003` (pending)

Add explicit onboarding state indicator in runtime projections and panel UX:
`pending`, `forwarded`, `confirmed`, and `onboard`.

### `TASK-AWS-CSM-RECOVERY-004` (pending)

Re-run AWS-CSM performance optimization pass, baseline current latency, and trim
fallback/safeguard branches to contract-required paths.

### `TASK-AWS-CSM-RECOVERY-005` (pending)

Audit and retire residual datum JSON pathways and duplicated legacy code in
active AWS-CSM/shared portal paths.

### `TASK-AWS-CSM-RECOVERY-006` (pending)

Maintain canonical recovery report continuity and sync contextual + compatibility
YAML control surfaces through execution.

### `TASK-AWS-CSM-RECOVERY-007` (pending, injected from TASK-AWS-CSM-RECOVERY-001)

Verify deployed FND runtime/asset parity for AWS-CSM action hosts so the recovery
program can distinguish code defects from host promotion/dependency drift.

## Lifecycle and Consolidation Notes

- Decision: **new stream added** (`STREAM-AWS-CSM-OPERATIONAL-RECOVERY`).
- Prior stream `STREAM-AWS-CSM-ALIGNMENT` remains `completed` foundation evidence.
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

## Validation Log

Validation commands executed for this planning-system update:

- `python3 -m unittest MyCiteV2.tests.unit.test_portal_aws_route_sync`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 - <<'PY' import importlib.util; print('boto3', bool(importlib.util.find_spec('boto3'))) PY`
- `python3 - <<'PY' ... yaml.safe_load(...) ... PY`

Result summary:

- AWS-CSM route-sync unit suite: pass (`Ran 7 tests`)
- one-shell architecture suite: pass (`Ran 22 tests`)
- contract-doc alignment suite: pass (`Ran 13 tests`)
- Local dependency probe: `boto3 False`
- YAML parse check: pass for contextual and compatibility manifests/task boards
