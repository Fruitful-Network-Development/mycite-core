# Contract Docs

The canonical portal contract set is:

- [portal_shell_contract.md](portal_shell_contract.md)
- [route_model.md](route_model.md)
- [surface_catalog.md](surface_catalog.md)
- [fnd_dcm_tool_contract.md](fnd_dcm_tool_contract.md)
- [fnd_dcm_manifest_conventions.md](fnd_dcm_manifest_conventions.md)
- [tool_mediation_surface_archetype.md](tool_mediation_surface_archetype.md)
- [tool_operating_contract.md](tool_operating_contract.md)
- [cts_gis_samras_addressing.md](cts_gis_samras_addressing.md)
- [cts_gis_hops_profile_sources.md](cts_gis_hops_profile_sources.md)
- [cts_gis_compiled_artifact_contract.md](cts_gis_compiled_artifact_contract.md)
- [cts_gis_operating_contract.md](cts_gis_operating_contract.md)
- [cts_gis_admin_entity_yaml_guidelines.md](cts_gis_admin_entity_yaml_guidelines.md)
- [cts_gis_legacy_alias_retirement_timeline.md](cts_gis_legacy_alias_retirement_timeline.md)
- [samras_structural_model.md](samras_structural_model.md)
- [samras_validity_and_mutation.md](samras_validity_and_mutation.md)
- [samras_engine_ui_boundary.md](samras_engine_ui_boundary.md)
- [portal_vocabulary_glossary.md](portal_vocabulary_glossary.md)

These documents describe the one-shell V2 portal model only.

CTS-GIS canonical storage contract in v2.5.3.x is:

- `private/utilities/tools/cts-gis/spec.json`
- `data/sandbox/cts-gis/tool.<msn>.cts-gis.json`
- `data/payloads/cache/<corpus>.msn-administrative.json` for first-pass `msn-SAMRAS` authority candidates
- `data/sandbox/cts-gis/sources/<corpus>.msn-administrative.json` for node-title overlays
- `data/sandbox/cts-gis/sources/precincts/*.json` for precinct-profile source modularization
- `data/payloads/compiled/cts_gis.<scope_id>.compiled.json` for the strict compiled artifact

v2.5.4 phase-B is canonical-only. Legacy CTS-GIS aliases are not part of active contracts.

CTS-GIS staged inserts are now contract-backed:

- canonical action route: `POST /portal/api/v2/system/tools/cts-gis/actions`
- canonical request schema: `mycite.v2.portal.system.tools.cts_gis.action.request.v1`
- canonical staged payload schema: `mycite.v2.cts_gis.stage_insert.v1`
- canonical staged state schema: `mycite.v2.cts_gis.staged_insert.state.v1`

CTS-GIS validation / deploy entrypoints:

- `MyCiteV2/scripts/compile_cts_gis_artifact.py`
- `MyCiteV2/scripts/validate_cts_gis_sources.py`
- `MyCiteV2/scripts/deploy_portal_update.sh` compile-before-restart posture for FND
