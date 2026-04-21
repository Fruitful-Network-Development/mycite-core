# MOS SQL Cutover Execution Report

Date: 2026-04-21

Doc type: `audit`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Record the first executed Track A pass from `docs/plans/master_plan_mos.md`, including the implemented SQL authority seams, runtime cutover modes, parity evidence, and remaining blocked semantic work.

## Supersession Note

This report records the intermediate execution pass only. Final FND ingestion, SQL-only activation, directive non-inference validation, documentation cleanup, and overall closure are now captured by:

- `docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md`
- `docs/audits/reports/mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md`
- `docs/audits/reports/mos_directive_context_non_inference_validation_2026-04-21.md`
- `docs/audits/reports/mos_documentation_alignment_and_cleanup_2026-04-21.md`
- `docs/audits/reports/mos_program_closure_report_2026-04-21.md`

## Scope

Implementation scope:

- `MyCiteV2/packages/ports/portal_authority/**`
- `MyCiteV2/packages/adapters/sql/**`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`

Verification scope:

- SQL adapter tests
- portal-authority contract and boundary tests
- runtime SQL-primary behavior tests
- existing filesystem and workspace regression tests touching affected seams

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`
- CTS-GIS HOPS profile sources: `docs/contracts/cts_gis_hops_profile_sources.md`
- SAMRAS validity and mutation: `docs/contracts/samras_validity_and_mutation.md`

## Track A Outcomes

### Phase 0 — Baseline consolidation

- The authority matrix, cutover scope table, semantic gap register, and Markdown-vs-YAML authority rules are published in `docs/plans/master_plan_mos.md`.
- The companion execution index remains `docs/plans/master_plan_mos.index.yaml`.

### Phase 1 — V1 SQL authority surface definition

- The first implemented SQL authority surfaces are:
  - authoritative anthology and datum-document reads
  - system workbench snapshot reads
  - publication summary/profile-basics read/write snapshots
  - audit append/read/recent window
  - portal grants, ownership posture, and tool exposure/config metadata
- The active append surface implemented in this pass is the audit-log seam. `packages/ports/event_log/` remains a placeholder port and was not promoted into runtime authority because the repo does not yet expose an active event-log contract/runtime path to swap without inventing new behavior.
- Non-datum private filesystem assets remain outside the first cutover.
- Generalized arbitrary datum mutation remains outside the first cutover.

### Phase 2 — Shadow-mode adapter implementation

- Added a new bounded portal-authority port at `MyCiteV2/packages/ports/portal_authority/`.
- Added SQL adapters at `MyCiteV2/packages/adapters/sql/`:
  - `SqliteSystemDatumStoreAdapter`
  - `SqliteAuditLogAdapter`
  - `SqlitePortalAuthorityAdapter`
- Added runtime authority modes:
  - `filesystem`: current behavior
  - `shadow`: bootstrap and compare against SQL while preserving filesystem outward behavior
  - `sql_primary`: use SQL-backed authority for approved surfaces

### Phase 3 — Parity and rollback readiness

- SQL adapter tests compare SQL-backed reads against filesystem-backed reads for the approved datum-store surfaces.
- SQL audit tests confirm append/read/recent behavior and filesystem bootstrap import.
- SQL runtime tests confirm that `sql_primary` can bootstrap from filesystem-backed content and later use DB-backed portal grants for runtime posture.
- Filesystem adapter and portal workspace regression tests remain green on the affected runtime path.

### Phase 4 — SQL-primary promotion path

- `run_portal_shell_entry(...)` and system workspace runtime flows now accept `authority_mode` and `authority_db_file`.
- `sql_primary` is implemented as the promotion path for the approved Track A surfaces.
- Outward file/workbench behavior is preserved because the runtime still projects the same shell envelopes and workspace payload shapes.

### Phase 5 — Grant-backed posture path

- Portal scope capabilities and tool exposure posture can now be supplied from DB-backed authority when SQL authority is active.
- Hard-coded FND defaults still exist as the filesystem/fallback path, but the SQL-primary cutover path can now be grant-derived instead of default-derived.

## Validation Evidence

Executed verification:

- `python3 -m unittest MyCiteV2.tests.contracts.test_portal_authority_contracts`
- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_authority_port_boundaries`
- `python3 -m unittest MyCiteV2.tests.adapters.test_sql_datum_store_adapter`
- `python3 -m unittest MyCiteV2.tests.adapters.test_sql_audit_log_adapter`
- `python3 -m unittest MyCiteV2.tests.adapters.test_sql_portal_authority_adapter`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`
- `python3 -m unittest MyCiteV2.tests.adapters.test_filesystem_system_datum_store_adapter`
- `python3 -m unittest MyCiteV2.tests.adapters.test_filesystem_audit_log_adapter`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`

Evidence files:

- `MyCiteV2/tests/contracts/test_portal_authority_contracts.py`
- `MyCiteV2/tests/architecture/test_portal_authority_port_boundaries.py`
- `MyCiteV2/tests/adapters/test_sql_datum_store_adapter.py`
- `MyCiteV2/tests/adapters/test_sql_audit_log_adapter.py`
- `MyCiteV2/tests/adapters/test_sql_portal_authority_adapter.py`
- `MyCiteV2/tests/unit/test_portal_shell_sql_authority.py`

## Remaining Open Work

1. `SG-1` remains open because `version_hash`/MSS hashing policy is still not closed canon.
2. `SG-2` remains open because generalized hyphae derivation and stable semantic identity rules are still not closed canon.
3. `SG-3` remains open because generalized datum-file insert/delete/move remap semantics are still not closed canon.
4. `SG-4` remains open because standard-closure and compatibility retirement policy depend on the first three gates.
5. Track C remains an active design/spec track rather than an implementation blocker.

## Track B Addendum — 2026-04-21 Closure Pass

This addendum supersedes the Track B status in the historical "Remaining Open Work" list above.

- `SG-1` is now closed through `docs/plans/mos_sg1_version_identity_policy_2026-04-21.md` plus SQL-backed persistence in `datum_document_semantics`.
- `SG-2` is now closed through `docs/plans/mos_sg2_hyphae_derivation_policy_2026-04-21.md` plus SQL-backed persistence in `datum_row_semantics`.
- `SG-3` is now closed through `docs/plans/mos_sg3_edit_remap_policy_2026-04-21.md` plus bounded preview/apply helpers on the SQL datum-store adapter.
- `SG-4` is now closed through `docs/plans/mos_sg4_standard_closure_policy_2026-04-21.md`.
- Track C has advanced to a schema/update-policy design posture in `docs/plans/mos_directive_context_design_track_2026-04-21.md` and remains non-blocking.

## Exit Criteria Status

- Track A v1 SQL authority path implemented: **Met for the approved first-cut surfaces**
- Shadow/parity evidence published: **Met**
- SQL-primary runtime path available: **Met**
- Native MOS closure: **Not met by design**
