# CTS-GIS SQL Authority Assurance Report

Date: 2026-04-21

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-24`

## Purpose

Publish the blocking CTS-GIS parity/readiness gate for post-closure work: verify that the live SQL authority corpus matches the authoritative filesystem corpus, confirm CTS-GIS row-graph integrity inside the authority DB, and name the remaining provenance/readiness concerns before more CTS-GIS feature evolution.

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`
- CTS-GIS HOPS profile sources: `docs/contracts/cts_gis_hops_profile_sources.md`
- SAMRAS structural model: `docs/contracts/samras_structural_model.md`

## Upstream Audit Plans

- `docs/audits/cts_gis_source_hops_audit_plan_2026-04-20.md`
- `docs/audits/cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md`

These plans remain the upstream work records. This report is the immediate proof artifact and blocking gate for continued CTS-GIS feature work.

## Verified Authority State

Full authoritative corpus:

- `authoritative_documents = 409`
- `authoritative_rows = 3133`
- `missing_in_sql = 0`
- `extra_in_sql = 0`
- `row_mismatches = 0`

CTS-GIS authoritative subset:

- `cts_gis_documents = 406`
- `cts_gis_rows = 2233`
- `missing_in_sql = 0`
- `extra_in_sql = 0`
- `row_mismatches = 0`

CTS-GIS row-graph integrity:

- semantic hashes are populated for all `2233` CTS-GIS rows
- hyphae hashes are populated for all `2233` CTS-GIS rows
- there are no missing local references
- there are no row warnings

Live portal/runtime posture:

- `/portal/system` remains the anthology-centered reducer-owned `SYSTEM` workspace with fresh `file=anthology&verb=navigate`
- `/portal/system/tools/workbench-ui` remains a separate SQL authority inspector under `SYSTEM`
- fresh `workbench_ui` entry may intentionally prefer a CTS-GIS authoritative document without changing the reducer-owned `SYSTEM` default
- the live CTS-GIS tool surface comes up `ready`; the meaningful remaining concerns are source/projection quality and provenance clarity rather than missing SQL ingestion

## Remaining Blocking Concerns

The SQL authority assurance gate is published, but CTS-GIS feature work remains blocked until these named concerns are fixed or explicitly waived:

1. HOPS/source visual correctness still requires ongoing file-by-file verification through `docs/audits/cts_gis_source_hops_audit_plan_2026-04-20.md`.
2. Source profile `3-2-3-17-77-1-14` remains blocked because the deployed source profile is missing and no vetted reference mapping is available.
3. Runtime time-context warning behavior still needs explicit interpretation when fresh CTS-GIS entry reports missing chronological anchor space.
4. Source-precedence, geometry-authority, and projection-coherence questions remain active in the upstream CTS-GIS audit plans and must stay named rather than being treated as implied SQL-ingestion defects.

## Gate Status

- SQL/filesystem authority parity: `passed`
- CTS-GIS row-graph integrity: `passed`
- CTS-GIS provenance/readiness gate for new feature work: `blocked pending named issue closure or explicit waiver`

## Verification

Executed and reproducible verification:

- `python3 -m unittest MyCiteV2.tests.unit.test_mos_program_closure`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_read_only`

Those checks now cover:

- full authoritative filesystem-vs-SQL document/row parity
- CTS-GIS subset document/row parity
- CTS-GIS row-graph integrity, including no missing local references and no row warnings
- current CTS-GIS runtime/projectable read-only behavior

## Result

The live SQL authority data needed by CTS-GIS is present and internally consistent: filesystem and SQL match across the full authoritative corpus and across the CTS-GIS subset, and CTS-GIS row semantics in the authority DB are clean. Continued CTS-GIS feature work is still blocked, but now for named provenance/readiness concerns rather than for uncertainty about whether the SQL authority corpus was fully and correctly loaded.

## Contextual planning status update (2026-04-24)

- `TASK-CTSGIS-BLOCKER-001` is now closed via explicit readiness waiver
  `WAIVER-CTSGIS-2026-04-24-001`.
- Blocking node `3-2-3-17-77-1-14` remains unresolved at the data level:
  no deployed source profile and no vetted reference mapping are available.
- Forcing synthetic source generation without vetted mapping would create a
  second authority risk and degrade source provenance guarantees, so waiver was
  selected instead of unverified repair.
- Remaining active CTS-GIS tasks are now:
  - `TASK-CTSGIS-DATUM-001` (`blocked`)
  - `TASK-CTSGIS-SAMRAS-001` (`blocked`)

## Readiness Waiver Record: `WAIVER-CTSGIS-2026-04-24-001`

Decision date: `2026-04-24`

Scope:

- readiness-gate blocker node `3-2-3-17-77-1-14`
- task closure target: `TASK-CTSGIS-BLOCKER-001`

Rationale:

- source profile for node `3-2-3-17-77-1-14` does not exist in deployed corpus
- vetted external reference mapping is unavailable in canonical audit artifacts
- applying an inferred mapping would violate contract-first provenance posture

Controls and residual risk posture:

- keep unresolved node and rationale explicitly recorded in active CTS-GIS docs
- do not treat this waiver as a resolved data repair event
- maintain blocked status for SAMRAS/datum closure tasks until their evidence
  matrices and owner approvals are published

## Validation refresh (2026-04-24)

Executed regression checks for this planning cycle:

- `python3 -m unittest MyCiteV2.tests.unit.test_nimm_phase2_foundations`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_aws_route_sync MyCiteV2.tests.unit.test_portal_cts_gis_actions MyCiteV2.tests.unit.test_aws_csm_onboarding_service`
- `python3 -m unittest MyCiteV2.tests.integration.test_nimm_mutation_contract_flow MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries`

Result: all executed suites passed; integration run reported `6` skipped tests.

## Blocker mapping refresh (2026-04-24, continuation cycle)

Selected task by priority/lexicographic rule:

- `TASK-CTSGIS-DATUM-001` (`blocked`, `p1`)

Blocker mapping:

- blocker id: `BLOCKER-CTSGIS-DATUM-MATRIX-EVIDENCE-001`
- blocker detail: publish critical/high datum drift disposition matrix plus
  deterministic ordering/editing evidence with domain-owner sign-off
- impacted tasks:
  - `TASK-CTSGIS-SAMRAS-001`

Disposition:

- no executable non-`done` tasks remain in active streams at this time
- blocked queue remains explicit and synchronized across contextual and
  compatibility task boards

## Blocker mapping refresh (2026-04-24, continuation cycle 2)

Selected task by priority/lexicographic rule:

- `TASK-CTSGIS-DATUM-001` (`blocked`, `p1`)

Observed blocker state:

- blocker id `BLOCKER-CTSGIS-DATUM-MATRIX-EVIDENCE-001` remains unresolved in
  repository evidence artifacts
- required datum drift matrix + deterministic ordering/editing evidence with
  domain-owner sign-off is still not published

Impacted task linkage:

- `TASK-CTSGIS-SAMRAS-001` remains impacted by unresolved datum evidence

Disposition:

- selected task remains `blocked`
- no actionable non-`done` task could be executed in this continuation cycle

Validation rerun for continuation cycle 2:

- `python3 -m unittest MyCiteV2.tests.unit.test_nimm_phase2_foundations` (pass)
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_aws_route_sync MyCiteV2.tests.unit.test_portal_cts_gis_actions MyCiteV2.tests.unit.test_aws_csm_onboarding_service` (pass)
- `python3 -m unittest MyCiteV2.tests.integration.test_nimm_mutation_contract_flow MyCiteV2.tests.integration.test_portal_host_one_shell` (pass, `6` skipped)
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment` (pass)
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries` (pass)
- `python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries` (pass)
