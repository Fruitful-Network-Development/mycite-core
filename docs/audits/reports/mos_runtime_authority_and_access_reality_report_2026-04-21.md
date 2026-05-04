# MOS Runtime Authority and Access Reality Report

Date: 2026-04-21

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-26`

## Purpose

Execute a focused post-cutover audit of current MOS operational reality:
database truth, package-peripheral access posture, tool access mediation, FND
authorization scope, and current visualization behavior on `/portal/system`.

## Source Intent

Intent references used for this audit:

- `docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md`
- `docs/personal_notes/MOS/data_base_use_findings.md`
- `docs/personal_notes/MOS/legacy_cleanup_assesment_and_final_consolidation.md`

These notes emphasize:

- SQL-backed authority as the primary operating core
- file/workbench-shaped runtime behavior preserved through adapter swap
- explicit peripheral grants for privileged operations
- state-reflective UI behavior over script-backed operations

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`

## Scope

Host/runtime and adapters:

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/packages/adapters/sql/portal_authority.py`
- `MyCiteV2/packages/adapters/sql/datum_store.py`
- `MyCiteV2/packages/ports/portal_authority/contracts.py`

Renderer path:

- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_system_workspace.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`

Live data:

- `/srv/mycite-state/instances/fnd/private/mos_authority.sqlite3`
- `/srv/mycite-state/instances/fnd/data`

## Findings

### 1) SQL authority reality is present and populated

Observed in live authority DB:

- `datum_document_semantics = 409`
- `datum_row_semantics = 3133`
- `authoritative_catalog_snapshots = 1`
- `system_workbench_snapshots = 1`
- `publication_summary_snapshots = 1`
- `portal_authority_snapshots = 1`
- `directive_context_snapshots = 0`
- `directive_context_events = 0`

CTS-GIS subset present:

- `cts_gis_documents = 406`
- `cts_gis_rows = 2233`

Status: `preserved`

### 1a) The live catalog snapshot now reflects `DATA_DIR` reality instead of repo-local path leakage

Observed in the live `authoritative_catalog_snapshots` payload for `tenant_id=fnd`:

- `source_files.anthology = system/anthology.json`
- sandbox/system/payload entries are stored as `DATA_DIR`-relative paths
- repo-local `deployed/fnd/...` source-path leakage is no longer present in the live catalog snapshot

Status: `corrected`

### 1b) Compatibility document keys remain active while MOS semantic identity lives in hashes

Observed in live `datum_document_semantics`:

- `408` document ids still use `sandbox:<tool>:<filename>`
- `1` document id remains `system:anthology`
- `0` document ids currently use the proposed native `lv.*`, `stl.*`, or `cptr.*` forms

Interpretation:

- current runtime canon is SQL-backed semantic identity through `version_hash` and `hyphae_hash`
- full native MOS document-key unification remains future work and should not be implied by active docs or tasks

Status: `explicitly bounded`

### 2) Package-peripheral access is SQL authority mediated, not hard-coded at runtime entry

`portal_shell_runtime.py` resolves portal scope and tool exposure from SQL portal
authority snapshots when available (`_portal_authority_source`,
`_portal_scope_from_request`, `_resolved_tool_exposure_policy`).

`portal_authority.py` stores and reads authoritative scope grants from
`portal_authority_snapshots` through `PortalAuthorityPort` contracts.

Status: `preserved`

### 3) FND authorization scope is explicit and broad for privileged tooling

In live `portal_authority_snapshots` payload for `scope_id=fnd`:

- capabilities:
  - `datum_recognition`
  - `spatial_projection`
  - `fnd_peripheral_routing`
  - `hosted_site_manifest_visibility`
  - `hosted_site_visibility`
- tool exposure policy enables and configures:
  - `aws_csm`
  - `cts_gis`
  - `fnd_dcm`
  - `fnd_ebi`
  - `workbench_ui`

Status: `preserved`

### 4) Tool access posture is offered through shell composition rows and readiness gates

`portal_shell_runtime.py` computes tool posture by combining:

- portal capabilities
- exposure policy state
- integration availability (`data_dir`, `webapps_root`)

`portal_system_workspace_runtime.py` and `portal_shell_runtime.py` fail closed on
missing SQL requirements for migrated `SYSTEM` surfaces using:

- `sql_authority_required`
- `sql_portal_authority_missing`
- `sql_authority_uninitialized`
- `sql_publication_summary_missing`

Status: `preserved`

### 5) Visualization drift signal exists on `/portal/system` despite valid runtime contract paths

Observed landing-page symptom: `The system workspace renderer is unavailable.`

`v2_portal_workbench_renderers.js` emits that exact fallback message when:

- payload kind is `system_workspace`, and
- `window.PortalSystemWorkspaceRenderer` is missing or non-callable at runtime.

`v2_portal_system_workspace.js` does define `window.PortalSystemWorkspaceRenderer`,
and the shell asset manifest in `app.py` includes that module.

Implication:

- likely runtime-side bundle/load/cache/order fault, or earlier JS failure before
  renderer registration, not an intentional server-side posture.

Status: `closed on 2026-04-22`

Closure evidence:

- `docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md`
- `docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md`
- `docs/audits/reports/mos_premorice_and_modularization_posture_report_2026-04-22.md`

## Intent Drift Assessment

- SQL-backed core: `preserved`
- file/workbench shape: `preserved`
- explicit portal-grant mediation: `preserved`
- state-reflective visualization on system landing: `narrowed`
- expanded directive-context persistence as first-class behavior: `deferred` (still `0` snapshots/events)

## Risks Not Immediately Obvious

1. Renderer fallback can hide healthy backend state and appear as authority
   failure to operators.
2. `build_allow_all_tool_exposure_policy` remains a permissive fallback when no
   SQL authority source is present; this is currently bounded by SQL fail-closed
   gates for `SYSTEM`, but still a drift vector for non-`SYSTEM` contexts.
3. Directive-context tables are empty; if continuity expectations increase, this
   can be misread as data loss rather than current scoped design.
4. `hippo` mirrors reference JSON and records, but it is not in the live runtime
   authority chain; treating it as canonical would create silent drift.

## Recommendation Set

1. Completed on `2026-04-22`: deploy-time/runtime shell-module health is now
   asserted through the manifest-backed registration contract.
2. Completed on `2026-04-22`: module-registration and script-load ordering
   diagnostics now flow through shell loader/watchdog/workbench paths.
3. Completed on `2026-04-22`: contract tests now pin tool adapter payload
   lookup locations (`resolveToolId` / `resolveReadiness`).
4. Keep SQL authority and tool-grant verification in CI with explicit `fnd`
   scope checks.

## Verification

Executed evidence collection:

- static/runtime contract review in listed code paths
- live SQL authority queries against `/srv/mycite-state/instances/fnd/private/mos_authority.sqlite3`
- renderer fallback path review in shell static modules

## Result

Current MOS reality is aligned to intended cutover operation: SQL authority is
populated, package-peripheral/tool access is contract-mediated, FND privileged
access is explicitly represented in authority snapshots, and the previously
named system-page visualization drift is now closed by the 2026-04-22
reflectivity closure package rather than remaining an active authority concern.
