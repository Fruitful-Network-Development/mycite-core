# CTS-GIS Ohio State Profile Pass (2026-04-20)

## Scope

- Target profile: `sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17.json`
- Node: `3-2-3-17`
- Reference source: `docs/personal_notes/CTS-GIS-prototype-mockup/3-2-3-17.geojson`
- Data root: `deployed/fnd/data` (repo-only authority)

## Workflow Executed

1. Dry-run deterministic repair:
   - `python3 MyCiteV2/scripts/repair_cts_gis_from_reference_geojson.py --data-root /srv/repo/mycite-core/deployed/fnd/data --node-id 3-2-3-17`
2. Apply deterministic repair:
   - `python3 MyCiteV2/scripts/repair_cts_gis_from_reference_geojson.py --data-root /srv/repo/mycite-core/deployed/fnd/data --node-id 3-2-3-17 --apply`

## Findings

- Owner row `7-4-1` is preserved as owner binding (state-profile variant).
- Primary collection `6-0-1` rebuilt from reference GeoJSON with complete polygon
  membership (`5-0-1` through `5-0-25`).
- Supplemental collection chain remained intact:
  - `6-0-2` preserved
  - `5-0-26` preserved
- Owner-row links now include both primary and supplemental collection references.
- Manifest/report updated with node `3-2-3-17` checksum and applied status.

## Evidence Snapshot

- Repair report:
  - `docs/audits/cts_gis_reference_repair_report.json`
  - `docs/audits/cts_gis_reference_repair_report.md`
- Manifest:
  - `docs/audits/cts_gis_reference_manifest.json`

## Outcome

Ohio state profile now follows deterministic reference-derived HOPS structure for
its primary boundary collection while preserving additive supplemental collection
rows required for state/precinct contextual workflows.
