"""Thin-tool read substrate for the CTS-GIS visualizers.

The CTS-GIS thin tools (map / district / admin) read pre-computed models WITHOUT
the heavy ``portal_cts_gis_runtime`` or the slow ``CtsGisReadOnlyService.
read_projection_bundle`` (~35s / ~700MB → 504). Two fast sources:

* **MOS-direct** (district + admin): ``read_{district,admin}_profile_static_from_mos``
  build the precinct collection + admin identity from a few MOS document reads.
* **Compiled artifact** (map projection): the pre-rendered GeoJSON feature
  collection lives in ``{data_dir}/payloads/compiled/cts_gis.{tenant}.compiled.json``.
  ``data_dir`` is fixed deployment config (its own ``DATA_DIR`` env, independent of
  the authority db), so it is configured once at app startup via
  :func:`configure_data_dir` rather than threaded per-request through the shell.

Imports only the surviving ``compiled_artifact`` read core + the neutral datum-store
accessor — nothing from the heavy runtime / service / mutation modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.datum_store_accessor import _datum_store_for_authority_db
from MyCiteV2.packages.modules.cross_domain.cts_gis.compiled_artifact import (
    compiled_artifact_path,
    read_admin_profile_static_from_mos,
    read_compiled_artifact_cached,
    read_district_profile_static_from_mos,
)

_TENANT_DEFAULT = "fnd"

# Process-level compiled-artifact root (deployment config, set once at startup).
_DATA_DIR: Path | None = None


def configure_data_dir(data_dir: str | Path | None) -> None:
    """Register the compiled-artifact root (called once from app startup)."""
    global _DATA_DIR
    _DATA_DIR = Path(data_dir) if data_dir else None


def datum_store_for(authority_db_file: Path | None) -> Any | None:
    """Cached read adapter for the authority db (via the neutral accessor)."""
    return _datum_store_for_authority_db(authority_db_file)


def read_map_projection(tenant: str = _TENANT_DEFAULT, *, data_dir: str | Path | None = None) -> dict[str, Any]:
    """Return the pre-rendered map projection model from the compiled artifact.

    ``data_dir`` falls back to the startup-configured root. Returns ``{}`` when the
    artifact is absent/unreadable (the map renders empty until a recompile).
    """
    root = data_dir if data_dir is not None else _DATA_DIR
    path = compiled_artifact_path(root, portal_scope_id=tenant)
    artifact = read_compiled_artifact_cached(path)
    if not isinstance(artifact, dict):
        return {}
    projection = artifact.get("projection_model")
    return dict(projection) if isinstance(projection, dict) else {}


def read_admin_profile(authority_db_file: Path | None, tenant: str = _TENANT_DEFAULT) -> dict[str, Any]:
    """Admin identity + (when present) geometry, built MOS-direct (no data_dir)."""
    store = datum_store_for(authority_db_file)
    if store is None:
        return {}
    return read_admin_profile_static_from_mos(store, tenant_id=tenant) or {}


def read_district_profile(authority_db_file: Path | None, tenant: str = _TENANT_DEFAULT) -> dict[str, Any]:
    """District collection + member-precinct list, built MOS-direct (no data_dir)."""
    store = datum_store_for(authority_db_file)
    if store is None:
        return {}
    return read_district_profile_static_from_mos(store, tenant_id=tenant) or {}
