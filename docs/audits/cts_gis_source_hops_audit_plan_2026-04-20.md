# CTS-GIS Source HOPS Audit Plan (Summit Lineage)

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-22`

## Purpose

Create a repeatable, file-by-file audit and correction process for Summit-lineage
CTS-GIS source profiles so HOPS geometry and source-correlation behavior remain aligned
to current one-shell runtime conventions and package modularization boundaries.

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/contracts/cts_gis_samras_addressing.md`
- `docs/contracts/samras_structural_model.md`
- `docs/contracts/samras_validity_and_mutation.md`

## Goal

Create a repeatable, file-by-file audit and correction process for every Summit-lineage
CTS-GIS source profile so HOPS geometry is verified against vetted reference GeoJSON,
runtime projection quality is documented, and source-file conventions remain canonical.

This plan initially prioritized **Hudson City (`3-2-3-17-77-1-6`) first** because it was
visually incorrect. That repair/verification pass is now complete. The remaining open
Summit-lineage blocker is node `3-2-3-17-77-1-14`, which still lacks a deployed source
profile and vetted reference mapping.

## Scope

- Dataset root: `deployed/fnd/data/sandbox/cts-gis/sources/`
- File pattern: `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77*.json`
- Existing deployed source profiles under this pattern: `32`
- Additional blocked logical node with no deployed source profile: `3-2-3-17-77-1-14`
- Reference corpus root: `docs/personal_notes/CTS-GIS-prototype-mockup/`

## Required Inputs Per File

- Source profile file (target `.json`)
- Candidate reference GeoJSON path
- Reference checksum (SHA256)
- Node id and expected administrative title
- Previous audit status (if any)

## Audit Workflow (Per File)

1. **Load + classify**
   - Parse source profile and detect row-chain families `4 -> 5 -> 6 -> 7`.
   - Confirm `7-3-1` primary node binding equals file suffix node id.
2. **Reference binding**
   - Resolve vetted GeoJSON reference from manifest or explicit source path.
   - Record provenance and SHA256 before any correction.
3. **Deterministic rebuild**
   - Normalize ring geometry.
   - Regenerate HOPS rows deterministically from reference geometry.
   - Rebuild `4-*`, `5-*`, `6-*`, and `7-3-1` linkage.
4. **Structural verification**
   - Confirm no missing row references.
   - Confirm `4-<n>-*` declared counts match actual HOPS token counts.
   - Confirm ring/polygon counts match reference geometry.
5. **Projection verification**
   - Confirm projection remains `projectable` or intentionally `projectable_degraded`.
   - Capture reason codes when degraded/fallback state appears.
   - Verify descendants/children overlays remain intact.
6. **Audit output**
   - Record before/after findings, actions, and final status.
   - Update manifest entry and batch report.

## Rule Investigation Track (Required Before New Repairs)

For each audited source file, explicitly capture how the current rules are interpreted:

1. **Geometry authority rule**
   - Confirm whether decoded HOPS geometry is accepted, rejected, or fallback-substituted.
   - Record rule path and reason code when semantic guardrails reject decode-valid geometry.
2. **Source precedence rule**
   - Confirm precedence between node-specific source documents and corpus-level source documents.
   - Record when explicit document pinning is preserved across node/intention transitions.
3. **Projection coherence rule**
   - Confirm Garland/profile counts and geospatial projection counts remain aligned for the same scope.
   - Record any count divergence with evidence and classification (`contract drift`, `data defect`, `tool bug`).
4. **Compatibility rule**
   - Confirm legacy compatibility behavior remains additive and does not create a second authority path.
   - Record warnings for compatibility paths that are still exercised.

## Paradigm and Modularization Alignment Checks

Every audit/repair decision must pass these alignment checks:

- **One-shell convention alignment**
  - No source-file correction may redefine shell route/surface semantics.
  - No HOPS correction may bypass runtime-owned mediation envelopes.
- **Contract-first alignment**
  - Any normative change discovered in practice must be proposed as a contract update task, not silently embedded in repair scripts.
- **Modularization alignment**
  - Keep source-repair logic in scripts/adapters; avoid introducing data-repair semantics into cross-domain runtime orchestration modules.
  - Keep shared decode/normalization helpers in shared or core structural modules, not duplicated per feature path.
- **Evidence alignment**
  - Every correction must have rule evidence, data evidence, and verification evidence recorded in manifest/report outputs.

## Batch Execution Controls

- Run dry-run first across selected node batch.
- Apply changes only after dry-run findings reviewed.
- Keep per-file rollback snapshots before apply mode.
- Never mass-apply unknown references.

## Standard Commands

- Dry-run for one node:
  - `python3 MyCiteV2/scripts/repair_cts_gis_from_reference_geojson.py --data-root deployed/fnd/data --manifest-path docs/audits/cts_gis_reference_manifest.json --report-json docs/audits/cts_gis_reference_repair_report.json --report-markdown docs/audits/cts_gis_reference_repair_report.md --node-id <node-id>`
- Apply for one approved node:
  - `python3 MyCiteV2/scripts/repair_cts_gis_from_reference_geojson.py --data-root deployed/fnd/data --manifest-path docs/audits/cts_gis_reference_manifest.json --report-json docs/audits/cts_gis_reference_repair_report.json --report-markdown docs/audits/cts_gis_reference_repair_report.md --node-id <node-id> --apply`

## Priority Order

1. `3-2-3-17-77-1-14` - only remaining Summit-lineage blocker; requires a deployed source profile plus vetted reference mapping, or an explicit readiness waiver
2. Reopen already verified Summit-lineage files only if new provenance or projection evidence contradicts the current `0 flagged / 32 clean` follow-up state

## File-By-File Checklist

Use statuses: `unchecked`, `in_review`, `repaired`, `verified`, `blocked`.

Latest execution updates:

- `2026-04-20`: Hudson City (`3-2-3-17-77-1-6`) dry-run passed, repair applied from
  `Summit-County-Communities/city-of-hudson.geojson`, manifest/report refreshed, and
  focused CTS-GIS regression suites passed.
- `2026-04-20`: Remaining city/township/village batches (`1-2..1-13`, `2-1..2-9`, `3-1..3-9`) completed via dry-run then apply; all targeted nodes marked repaired in manifest and verified here.
- `2026-04-20`: Node `3-2-3-17-77-1-14` marked blocked due to missing deployed source profile and missing vetted reference mapping.
- `2026-04-22`: Post-repair follow-up against `/srv/repo/mycite-core/deployed/fnd/data`
  and `/srv/mycite-state/instances/fnd/data` reported `0 flagged / 32 clean`; the
  checklist below now reflects the post-follow-up verification state for deployed
  Summit-lineage source profiles.

- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-6.json` - status: `verified` - note: Hudson City priority
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-1.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-2.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-3.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-4.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-5.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-7.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-8.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-9.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-10.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-11.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-12.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-13.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-14.json` - status: `blocked` - note: missing deployed source profile and no vetted reference mapping
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-1.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-2.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-3.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-4.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-5.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-6.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-7.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-8.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-2-9.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-1.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-2.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-3.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-4.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-5.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-6.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-7.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-8.json` - status: `verified`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-3-9.json` - status: `verified`

## Evidence To Capture Per File

- Before:
  - projection source/state
  - decode summary counts
  - fallback/semantic reason codes
  - bounds snapshot
- After:
  - same metrics with diff
  - manifest entry id + checksum
  - runtime verification note for descendants/children overlay behavior

## Exit Criteria

- Every deployed Summit-lineage source profile is in `verified` state, and the undeployed
  node `3-2-3-17-77-1-14` remains explicitly `blocked` with rationale.
- Hudson City (`3-2-3-17-77-1-6`) corrected or explicitly blocked with root cause.
- Manifest and repair reports are current and reproducible from script commands.
- Rule investigation and modularization alignment evidence are recorded for each corrected or blocked file.

## Remaining Open Item

- Resolve or explicitly waive blocked node `3-2-3-17-77-1-14` by supplying a deployed
  source profile plus vetted reference mapping, or by recording a formal readiness waiver
  in the upstream CTS-GIS parity/readiness gate.
