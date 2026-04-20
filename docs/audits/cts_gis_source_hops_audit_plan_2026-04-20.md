# CTS-GIS Source HOPS Audit Plan (Summit Lineage)

## Goal

Create a repeatable, file-by-file audit and correction process for every Summit-lineage
CTS-GIS source profile so HOPS geometry is verified against vetted reference GeoJSON and
runtime projection quality is documented.

This plan prioritizes **Hudson City (`3-2-3-17-77-1-6`) first** because it remains
visually incorrect.

## Scope

- Dataset root: `deployed/fnd/data/sandbox/cts-gis/sources/`
- File pattern: `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77*.json`
- Total in-scope source profiles: `32`
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

1. `3-2-3-17-77-1-6` (Hudson City) - highest priority
2. `3-2-3-17-77` (Summit County) - verify post-repair consistency
3. `3-2-3-17-77-1-1` (Akron City) - verify post-repair consistency
4. Remaining files in deterministic node-id order

## File-By-File Checklist

Use statuses: `unchecked`, `in_review`, `repaired`, `verified`, `blocked`.

Latest execution updates:

- `2026-04-20`: Hudson City (`3-2-3-17-77-1-6`) dry-run passed, repair applied from
  `Summit-County-Communities/city-of-hudson.geojson`, manifest/report refreshed, and
  focused CTS-GIS regression suites passed.
- `2026-04-20`: Remaining city/township/village batches (`1-2..1-13`, `2-1..2-9`, `3-1..3-9`) completed via dry-run then apply; all targeted nodes marked repaired in manifest and verified here.
- `2026-04-20`: Node `3-2-3-17-77-1-14` marked blocked due to missing deployed source profile and missing vetted reference mapping.

- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-6.json` - status: `verified` - note: Hudson City priority
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77.json` - status: `unchecked`
- `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-1.json` - status: `unchecked`
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

- Every in-scope file is in `verified` or `blocked` state with explicit rationale.
- Hudson City (`3-2-3-17-77-1-6`) corrected or explicitly blocked with root cause.
- Manifest and repair reports are current and reproducible from script commands.
