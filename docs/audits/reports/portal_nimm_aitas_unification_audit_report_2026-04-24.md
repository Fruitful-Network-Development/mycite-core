# Portal NIMM/AITAS Unification Audit Report

Date: 2026-04-24

Doc type: `audit-report`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-24`

## Initiative and Task Mapping

- Initiative: `INIT-PORTAL-NIMM-AITAS-UNIFICATION`
- Stream: `STREAM-PORTAL-NIMM-AITAS-UNIFICATION`
- Canonical plan: `docs/plans/portal_nimm_aitas_unification_plan_2026-04-24.md`
- Covered task IDs:
  - `nimm-schema-definition`
  - `aitas-wrapper-context`
  - `lens-abstraction-formalization`
  - `cts-gis-staging-layer`
  - `aws-cts-lens-refactor`
  - `mutation-contract-consolidation`
  - `terminology-standardization`
  - `ui-authority-audit-tests`

## Method

Inspected the active planning surfaces, latest AWS-CSM/CTS-GIS audit reports,
state-machine primitives, portal runtimes, and portal renderers. This report is
the canonical audit and closeout evidence for the cross-tool unification stream.

## Confirmed Foundation

The 2026-04-23 refinement phases established useful shared primitives:

- versioned NIMM directive and envelope classes in
  `MyCiteV2/packages/state_machine/nimm/directives.py` and
  `MyCiteV2/packages/state_machine/nimm/envelope.py`
- AITAS context and merge behavior in
  `MyCiteV2/packages/state_machine/aitas/context.py`
- stateless baseline lenses in
  `MyCiteV2/packages/state_machine/lens/base.py`
- staging compiler and mutation contract interface in
  `MyCiteV2/packages/state_machine/nimm/staging.py` and
  `MyCiteV2/packages/state_machine/nimm/mutation_contract.py`
- CTS-GIS reflective NIMM metadata in
  `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`

Those foundations should be extended rather than duplicated.

## Baseline Gaps And Closure Disposition

### 1. Minimal NIMM grammar aliases are not implemented

Evidence:

- `MyCiteV2/packages/state_machine/nimm/directives.py` supports long-form
  verbs: `navigate`, `investigate`, `mediate`, and `manipulate`.
- The requested minimal grammar uses `nav`, `inv`, `med`, and `man`.

Closure:

- `nimm-schema-definition` implemented alias normalization and schema guidance.

### 2. AITAS is not yet consistently wrapped around tool mutation requests

Evidence:

- CTS-GIS carries local `tool_state.aitas` and passes it into compiled stage
  envelopes in `portal_cts_gis_runtime.py`.
- AWS-CSM action handling in `portal_aws_runtime.py` accepts `action_kind` and
  `action_payload` directly without requiring a NIMM envelope with AITAS context.

Closure:

- `aitas-wrapper-context` and `aws-cts-lens-refactor` implemented cross-tool envelope use.

### 3. CTS-GIS stage flow still exposes tool-specific lifecycle names

Evidence:

- CTS-GIS action kinds include `stage_insert_yaml`, `validate_stage`,
  `preview_apply`, `apply_stage`, and `discard_stage` in
  `portal_cts_gis_runtime.py`.
- The Interface Panel renderer dispatches those same compatibility names from
  `v2_portal_inspector_renderers.js`.
- The shared mutation contract already names canonical lifecycle actions:
  `stage`, `validate`, `preview`, `apply`, and `discard`.

Closure:

- `cts-gis-staging-layer` and `mutation-contract-consolidation` implemented
  lifecycle adapter refactor and tests.

### 4. AWS-CSM still executes direct bespoke runtime actions

Evidence:

- `portal_aws_runtime.py` declares `_ALLOWED_ACTION_KINDS` and handles actions
  such as `create_domain`, `create_profile`, `stage_smtp_credentials`,
  `send_handoff_email`, and `reveal_smtp_password` directly in `_apply_action`.
- `AwsCsmOnboardingService.apply(...)` mutates profile workflow sections from
  command payloads without a NIMM envelope boundary.

Closure:

- `aws-cts-lens-refactor` implemented NIMM compilation for AWS-CSM/AWS-CTS actions.
- `mutation-contract-consolidation` implemented shared endpoint/adaptor wiring.

### 5. Lens abstraction exists but per-tool lenses are not formalized

Evidence:

- `lens/base.py` currently provides only `IdentityLens` and `TrimmedStringLens`.
- CTS-GIS stage compilation uses `TrimmedStringLens` for staged title values,
  while other CTS-GIS and AWS-CSM display/canonical transforms remain local code.

Closure:

- `lens-abstraction-formalization` implemented per-tool codecs and tests.

### 6. UI authority posture is mostly right but needs regression locks

Evidence:

- CTS-GIS Interface Panel staging UI dispatches action requests and does not
  write SQL/files directly in `v2_portal_inspector_renderers.js`.
- AWS-CSM workspace dispatches action requests from
  `v2_portal_aws_workspace.js`.
- Remaining risk is client-side inference of lifecycle legality and accidental
  introduction of mutation logic into UI code.

Closure:

- `ui-authority-audit-tests` implemented architecture, lifecycle, and smoke-adjacent
  runtime coverage.

### 7. Confidentiality is contractually improved but needs explicit tests

Evidence:

- AWS-CSM handoff email code states reusable SMTP passwords are not sent over
  handoff email in `aws_csm_onboarding_cloud.py`.
- `portal_aws_runtime.py` omits password material from audit `details` for
  `reveal_smtp_password`, but returns `ephemeral_secret` in the action response.
- `v2_portal_aws_workspace.js` renders the ephemeral secret response for
  operator handoff.

Closure:

- `aws-cts-lens-refactor` and `ui-authority-audit-tests` implemented tests that ensure
  secret-bearing values stay out of profile JSON, audit details, logs, and
  non-ephemeral response storage.

### 8. Terminology still has compatibility surfaces

Evidence:

- Contracts retain `inspector` as a compatibility alias for `Interface Panel`.
- User-facing request language uses `AWS-CTS`; the codebase uses `AWS-CSM`.

Closure:

- `terminology-standardization` implemented active-doc normalization and alias notes.

## Implementation Evidence

### `nimm-schema-definition`

Closed by extending `MyCiteV2/packages/state_machine/nimm/directives.py` with
the versioned minimal grammar aliases `nav`, `inv`, `med`, and `man`; schema
guidance in `NIMM_DIRECTIVE_GRAMMAR_V1`; and validation through
`validate_nimm_directive_payload(...)`. Unit coverage in
`MyCiteV2/tests/unit/test_nimm_phase2_foundations.py` verifies alias
normalization, invalid payload rejection, and round-trip serialization.

### `aitas-wrapper-context`

Closed by keeping AITAS as a non-mutating envelope context in
`MyCiteV2/packages/state_machine/aitas/context.py` and by compiling CTS-GIS and
AWS-CSM action paths to `NimmDirectiveEnvelope` before validate/preview/apply.
CTS-GIS preserves `tool_state.aitas` in staged envelopes; AWS-CSM creates an
`aws_csm` manipulation envelope with `archetype=aws_csm_onboarding`.

### `lens-abstraction-formalization`

Closed by adding `SamrasTitleLens`, `EmailAddressLens`, and
`SecretReferenceLens` in `MyCiteV2/packages/state_machine/lens/base.py`.
CTS-GIS title staging now uses `SamrasTitleLens`; AWS-CSM projects email and
secret-reference fields as lens metadata without granting the lenses operation
selection, permission, or transition authority.

### `cts-gis-staging-layer`

Closed by accepting canonical lifecycle action names in
`MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py` and retaining
historical CTS-GIS action names only as compatibility aliases. Staged YAML is
normalized through lenses into canonical values, compiled into NIMM
manipulation envelopes, previewed in the Workbench, and applied only through
runtime SQL authority.

### `aws-cts-lens-refactor`

Closed by treating `AWS-CTS` as a planning/request alias for AWS-CSM and by
compiling AWS-CSM action requests into `target_authority=aws_csm` NIMM
manipulation envelopes in `portal_aws_runtime.py`. Secret-bearing payload keys
are redacted in compiled envelopes, and unit coverage verifies a secret-bearing
input is not persisted to profile JSON or action details.

### `mutation-contract-consolidation`

Closed by centralizing lifecycle normalization and adapter maps in
`MyCiteV2/packages/state_machine/nimm/mutation_contract.py` and exposing the
shared host route family `/portal/api/v2/mutations/<action>` in
`MyCiteV2/instances/_shared/portal_host/app.py`. The route delegates by
`target_authority` to CTS-GIS or AWS-CSM runtime adapters while preserving the
separate read contract.

### `terminology-standardization`

Closed by updating active READMEs and contracts to prefer Interface Panel,
Workbench, Control Panel, lens, NIMM directive script, AITAS context, YAML
stage, preview, and apply. `inspector` and `AWS-CTS` remain documented
compatibility aliases only.

### `ui-authority-audit-tests`

Closed by extending architecture tests to verify mutation-capable UI sources
dispatch actions and do not contain authoritative write/service calls. CTS-GIS
unit/integration tests verify canonical lifecycle adapters and Workbench preview
reflectivity; AWS-CSM unit tests verify NIMM envelope projection and
confidentiality of secret-bearing action input.

## Lifecycle Decision

This report creates no supersession of the completed refinement or AWS-CSM
alignment reports. It is the canonical closure report for the cross-tool
unification stream and should remain paired with
`docs/plans/portal_nimm_aitas_unification_plan_2026-04-24.md`.

## Validation Log

Closure validation executed on 2026-04-24:

- YAML parse:
  - `docs/plans/contextual_system_manifest.yaml`
  - `docs/plans/contextual_system_task_board.yaml`
  - `docs/plans/planning_audit_manifest.yaml`
  - `docs/plans/planning_task_board.yaml`
- `python3 -m unittest MyCiteV2.tests.unit.test_nimm_phase2_foundations MyCiteV2.tests.unit.test_portal_aws_route_sync MyCiteV2.tests.unit.test_portal_cts_gis_actions MyCiteV2.tests.unit.test_aws_csm_onboarding_service`
  - result: pass, 22 tests
- `python3 -m unittest MyCiteV2.tests.integration.test_nimm_mutation_contract_flow MyCiteV2.tests.integration.test_portal_host_one_shell`
  - result: pass, 8 tests run, 6 skipped because Flask host dependencies are
    not available in the current dependency-light environment
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment MyCiteV2.tests.architecture.test_portal_one_shell_boundaries MyCiteV2.tests.architecture.test_state_machine_boundaries`
  - result: pass, 37 tests
- `git diff --check`
  - result: pass
