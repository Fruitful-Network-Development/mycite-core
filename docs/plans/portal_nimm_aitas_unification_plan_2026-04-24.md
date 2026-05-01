# Portal NIMM/AITAS Unification Plan

Date: 2026-04-24

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-24`

## Initiative and Task Mapping

- Initiative: `INIT-PORTAL-NIMM-AITAS-UNIFICATION`
- Stream: `STREAM-PORTAL-NIMM-AITAS-UNIFICATION`
- Canonical report: `docs/audits/reports/portal_nimm_aitas_unification_audit_report_2026-04-24.md`
- Task IDs:
  - `nimm-schema-definition`
  - `aitas-wrapper-context`
  - `lens-abstraction-formalization`
  - `cts-gis-staging-layer`
  - `aws-cts-lens-refactor`
  - `mutation-contract-consolidation`
  - `terminology-standardization`
  - `ui-authority-audit-tests`

## Purpose

Unify the mutation-capable portal stack for CTS-GIS and AWS-CSM under one
directive model:

- narrow shell authority
- runtime-owned mutation lifecycle
- NIMM directive script authority
- AITAS interpretation context
- stateless lens codecs
- YAML stage to preview/apply flow

The user-facing phrase `AWS-CTS` is treated as a planning/request alias in this
stream. The codebase evidence currently uses `AWS-CSM`; implementation should
either normalize the public term or document the alias where retained.

## Lifecycle and Consolidation Decision

Decision: create a new bounded stream instead of reopening completed closure
streams.

- `STREAM-REFINEMENT` remains completed and retained as the foundation record
  for NIMM/AITAS/lens/staging primitives.
- `STREAM-AWS-CSM-ALIGNMENT` remains completed for the 2026-04-23 AWS-CSM
  operating audit and operational hardening work.
- `STREAM-CTS-GIS-OPEN` remains active for source-hops/SAMRAS/datum readiness
  blockers.
- This stream closed cross-tool unification of the already-introduced
  primitives into CTS-GIS and AWS-CSM runtime behavior.

No historical file is deleted or demoted by this plan. Existing completed
reports remain canonical for their own streams; this plan is the single
canonical plan for the cross-tool NIMM/AITAS unification stream.

## Canonical Evidence Anchors

- `docs/plans/refinement.md`
- `docs/audits/reports/refinement_phase4_validation_report_2026-04-23.md`
- `docs/audits/reports/aws_csm_comprehensive_audit_report_2026-04-23.md`
- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- `docs/contracts/mutation_contract.md`
- `docs/contracts/tool_operating_contract.md`
- `MyCiteV2/packages/state_machine/nimm/directives.py`
- `MyCiteV2/packages/state_machine/aitas/context.py`
- `MyCiteV2/packages/state_machine/lens/base.py`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`

## Articulation Point Mapping

| Point | Requirement | Task owner |
| --- | --- | --- |
| 1 | Keep shell, directive script, and lens authority separate | `ui-authority-audit-tests` |
| 2 | Add minimal NIMM grammar with `nav`/`inv`/`med`/`man` aliases | `nimm-schema-definition` |
| 3 | Keep AITAS as non-mutating metadata wrapper | `aitas-wrapper-context` |
| 4 | Formalize lens codecs | `lens-abstraction-formalization` |
| 5 | Normalize operator edits into canonical raw staged values | `cts-gis-staging-layer`, `aws-cts-lens-refactor` |
| 6 | Compile staged values into NIMM directive scripts | `cts-gis-staging-layer`, `aws-cts-lens-refactor` |
| 7 | Separate mutation contract from read contract | `mutation-contract-consolidation` |
| 8 | Implement stage/validate/preview/apply/discard lifecycle | `mutation-contract-consolidation` |
| 9 | Preserve Control Panel, Workbench, Interface Panel region roles | `cts-gis-staging-layer`, `ui-authority-audit-tests` |
| 10 | Normalize terminology and aliases | `terminology-standardization` |
| 11 | Audit CTS-GIS for bespoke stage/mutation flows | `cts-gis-staging-layer` |
| 12 | Audit AWS-CSM/AWS-CTS for direct service action flows | `aws-cts-lens-refactor` |
| 13 | Update tests/docs and confidentiality coverage | `ui-authority-audit-tests` |
| 14 | Plan optional performance, duplication, and cross-tool grouping analysis | `terminology-standardization` |

## Execution Passes

### Pass 1: Audit and vocabulary

Confirm current runtime behavior and update glossary/contract notes:

- locate direct AWS-CSM action execution that bypasses NIMM envelopes
- locate CTS-GIS compatibility lifecycle names
- document `AWS-CTS` as alias or normalize to `AWS-CSM`
- verify UI components dispatch actions only

### Pass 2: Define shared grammar and contracts

Implement the canonical directive surface before changing tool behavior:

- support `nav`, `inv`, `med`, `man` alias tokens
- keep versioned schema IDs stable
- require target authority, AITAS context/envelope, and targets
- define lifecycle adapter expectations for tool-specific routes

### Pass 3: Refactor CTS-GIS and AWS-CSM

Move tool behavior onto the shared model:

- CTS-GIS YAML stage remains an operator convenience, not a write protocol
- CTS-GIS compatibility action names map to shared lifecycle actions
- AWS-CSM onboarding actions compile to NIMM manipulation envelopes
- AWS-CSM/AWS-CTS secret handling stays runtime-owned and non-persistent
- per-tool codecs become lenses or registered lens adapters

### Pass 4: Test and close

Close only after validation covers:

- NIMM parser/schema alias behavior
- AITAS merge and non-mutating behavior
- lens encode/decode/validation paths
- CTS-GIS stage/preview/apply/discard lifecycle
- AWS-CSM staged onboarding lifecycle
- UI authority boundaries and confidentiality

## Exit Criteria

- Completed: all task IDs in `INIT-PORTAL-NIMM-AITAS-UNIFICATION` are `done`
  in both YAML task boards.
- Completed: CTS-GIS and AWS-CSM use NIMM envelope + AITAS context before
  runtime mutation.
- Completed: tool-specific direct routes remain compatibility adapters to the
  shared lifecycle.
- Completed: contracts and READMEs point to this plan/report without adding
  another active plan for the same stream.
- Completed: unit, integration, architecture, and contract validations are
  recorded in the canonical report.
