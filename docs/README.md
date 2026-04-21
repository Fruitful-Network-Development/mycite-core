# MyCite V2 Portal Docs

This repository now describes one portal shell only.

- Canonical public entry: `/portal` -> `/portal/system`
- Root surfaces: `SYSTEM`, `NETWORK`, `UTILITIES`
- Canonical shell endpoint: `/portal/api/v2/shell`
- Canonical tool work pages: `/portal/system/tools/<tool_slug>`
- Canonical two-pane SQL-backed spreadsheet tool: `/portal/system/tools/workbench-ui`
- `SYSTEM` remains the anthology-centered datum-file workbench at `/portal/system`
- `workbench_ui` remains a separate SQL authority inspector for authoritative documents only; it does not manage all deployed files
- Canonical AWS service tool: `/portal/system/tools/aws-csm`
- Canonical CTS-GIS tool: `/portal/system/tools/cts-gis`
- Canonical FND-DCM tool: `/portal/system/tools/fnd-dcm`
- Migrated `SYSTEM` authority surfaces are SQL-backed and fail closed without the per-instance MOS authority database
- Canonical CTS-GIS storage contract: `private/utilities/tools/cts-gis/spec.json` + `data/sandbox/cts-gis/tool.<msn>.cts-gis.json`
- Canonical FND-DCM docs: `docs/contracts/fnd_dcm_tool_contract.md`, `docs/contracts/fnd_dcm_manifest_conventions.md`
- Canonical CTS-GIS SAMRAS addressing contract: `docs/contracts/cts_gis_samras_addressing.md`
- Canonical mediation-tool archetype note: `docs/contracts/tool_mediation_surface_archetype.md`
- Canonical SAMRAS structural docs: `docs/contracts/samras_structural_model.md`, `docs/contracts/samras_validity_and_mutation.md`, `docs/contracts/samras_engine_ui_boundary.md`
- CTS-GIS phase-B (v2.5.4) is canonical-only: legacy CTS-GIS aliases are no longer accepted
- Operator migration note: remove or ignore stale pre-v2.5.4 CTS-GIS legacy roots before or during rollout
- `NETWORK` is the read-only portal-instance system-log workbench over `data/system/system_log.json`
- `NETWORK` remains a derived-materialization surface outside SQL datum authority in the completed MOS cut-over
- retained host-bound/private assets also remain outside the `workbench_ui` SQL corpus unless separately ported
- `UTILITIES` owns configuration, exposure, integrations, and control surfaces
- The top menubar is the only shell header; `ide-body` is the peer-region window for the `Activity Bar`, `Control Panel`, `Workbench`, and `Interface Panel`
- Shell static assets are versioned through one embedded shell asset manifest
- CTS-GIS keeps the shared shell contract unchanged while projecting a CTS-GIS-local Interface Panel body with magnitude-derived `Diktataograph` navigation and a selection-aligned `Garland`
- Canonical term mapping and compatibility aliases are documented in `docs/contracts/portal_vocabulary_glossary.md`
- Documentation IA and guided-task YAML standards are maintained under `docs/standards/`
