# CTS-GIS Reference Promotion And Profile Repair

## Purpose

This contract defines the required promotion and repair workflow for CTS-GIS source
profiles that are derived from external GeoJSON. The process is mandatory when
adding new source profiles or correcting existing profiles with known geometry
drift.

## Authoritative Workflow

1. **Promote reference candidate**
   - Candidate geometry must come from a traceable source file (path + hash).
   - Candidate must be linked to a target CTS node id (`3-2-3-17-77-*` lineage).
2. **Normalize geometry**
   - Accept only `Polygon` or `MultiPolygon`.
   - Normalize ring coordinates to deterministic ordering rules used by the repair
     pipeline.
3. **Encode deterministic HOPS rows**
   - Encode each coordinate through canonical HOPS partitioning.
   - Rebuild row families `4-*`, `5-*`, `6-*`, and bind them from `7-3-1`.
4. **Round-trip and semantic checks**
   - Validate contract structure and row references.
   - Run semantic projection guardrails in CTS-GIS runtime pathways.
5. **Generate audit output**
   - Emit machine-readable report and markdown summary for every batch.
   - Persist manifest entry with source checksum and status.
6. **Apply controlled repair batch**
   - Apply a small approved batch only (`--apply` mode).
   - Keep rollback artifacts and pre-repair snapshots.

## Provenance And Acceptance Rules

- Every promoted reference must have:
  - `node_id`
  - `source_profile` and profile path
  - `reference_geojson_source` and/or `reference_geojson_path`
  - `reference_geojson_sha256`
  - timestamp and status
- Promotion is accepted only if:
  - geometry parses as polygonal GeoJSON
  - deterministic encoding is reproducible across repeated runs
  - contract violations are not introduced
  - projection diagnostics remain within allowed states (`projectable` or
    `projectable_degraded` with explicit reason codes)

## Runtime Authority Boundaries

- **Promotion time authority:** vetted reference GeoJSON may be used to regenerate
  HOPS rows and update source profile payloads.
- **Runtime authority:** HOPS remains primary projection input. Reference GeoJSON is
  fallback-only when semantic guardrails classify decode-valid HOPS as implausible.

## Rollback Requirements

- Before each apply batch, save:
  - profile file snapshot(s)
  - previous manifest snapshot
  - generated audit report
- Rollback is required if any of these occur:
  - contract violations increase after repair
  - semantic guardrail diagnostics regress unexpectedly
  - descendants/children overlay behavior deviates from expected scope

## Required Tooling

- Orchestration command:
  - `python MyCiteV2/scripts/repair_cts_gis_from_reference_geojson.py`
- Required outputs:
  - `docs/audits/cts_gis_reference_manifest.json`
  - `docs/audits/cts_gis_reference_repair_report.json`
  - `docs/audits/cts_gis_reference_repair_report.md`
