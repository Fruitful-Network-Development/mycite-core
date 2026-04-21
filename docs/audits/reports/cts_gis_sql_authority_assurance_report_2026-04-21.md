# CTS-GIS SQL Authority Assurance Report

Date: 2026-04-21

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-21`

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
