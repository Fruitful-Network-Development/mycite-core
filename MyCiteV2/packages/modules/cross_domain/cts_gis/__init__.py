"""CTS-GIS compiled-artifact + profile reads (read-only; thin-tool data core).

The bespoke read/mutation service (CtsGisReadOnlyService / CtsGisMutationService)
was retired in Stage C — CTS-GIS is now thin read-only WorkbenchTools that read the
compiled artifact / MOS-direct profiles. Only the compiled_artifact read core
survives here.
"""

from .compiled_artifact import (
    CTS_GIS_ADMIN_ROOT_DATUM_RELATIVE_PATH,
    CTS_GIS_PRECINCTS_RELATIVE_PATH,
    build_admin_profile_static,
    build_compiled_artifact,
    build_cts_gis_source_layout_summary,
    build_district_geospatial_projection,
    build_district_profile_static,
    compiled_artifact_path,
    cts_gis_admin_root_source_path,
    cts_gis_precinct_file_for_id,
    cts_gis_precincts_source_path,
    cts_gis_source_root,
    evict_compiled_artifact_read_cache,
    read_admin_profile_static_from_mos,
    read_admin_profile_static_from_source_datum,
    read_compiled_artifact,
    read_compiled_artifact_cached,
    read_district_profile_static_from_mos,
    read_district_profile_static_from_source_datum,
    read_district_profile_static_with_geometry_from_source_datum,
    validate_compiled_artifact,
    validate_cts_gis_source_layout,
    write_compiled_artifact,
)

__all__ = [
    "CTS_GIS_ADMIN_ROOT_DATUM_RELATIVE_PATH",
    "CTS_GIS_PRECINCTS_RELATIVE_PATH",
    "build_admin_profile_static",
    "build_compiled_artifact",
    "build_cts_gis_source_layout_summary",
    "build_district_geospatial_projection",
    "build_district_profile_static",
    "compiled_artifact_path",
    "cts_gis_admin_root_source_path",
    "cts_gis_precinct_file_for_id",
    "cts_gis_precincts_source_path",
    "cts_gis_source_root",
    "evict_compiled_artifact_read_cache",
    "read_admin_profile_static_from_mos",
    "read_admin_profile_static_from_source_datum",
    "read_compiled_artifact",
    "read_compiled_artifact_cached",
    "read_district_profile_static_from_mos",
    "read_district_profile_static_from_source_datum",
    "read_district_profile_static_with_geometry_from_source_datum",
    "validate_cts_gis_source_layout",
    "validate_compiled_artifact",
    "write_compiled_artifact",
]
