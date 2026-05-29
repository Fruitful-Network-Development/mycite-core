"""Neutral datum-store accessor (no CTS-GIS / heavy-runtime dependency).

The per-authority-db ``SqliteSystemDatumStoreAdapter`` cache used to live inside
``portal_cts_gis_runtime`` (the heavy CTS-GIS runtime). The surviving palette/
visualizer routes (``/portal/api/tools/eligible``, ``/portal/api/visualizers/
for-sandbox``) and the app preload only need this thin accessor, so it lives here
— importing nothing from the CTS-GIS runtime — letting that runtime be retired
without breaking tool discovery (Stage C precondition #1).
"""

from __future__ import annotations

from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter

_DATUM_STORE_BY_AUTHORITY_DB: dict[str, SqliteSystemDatumStoreAdapter] = {}


def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _datum_store_for_authority_db(
    authority_db_file: str | Path | None,
) -> SqliteSystemDatumStoreAdapter | None:
    """Return a cached read/write adapter for ``authority_db_file`` (canonical-only writes).

    Canonical-only write posture (2026-05-28): the legacy_alias back-compat was
    retired ahead of schedule (commit 0c355db); live data is fully canonical and
    the adapter refuses to re-persist any non-canonical catalog id. Reads do not
    validate canonicality.
    """
    root = _path_or_none(authority_db_file)
    if root is None:
        return None
    cache_key = str(root.resolve())
    cached = _DATUM_STORE_BY_AUTHORITY_DB.get(cache_key)
    if cached is not None:
        return cached
    store = SqliteSystemDatumStoreAdapter(root, allow_legacy_writes=False)
    _DATUM_STORE_BY_AUTHORITY_DB[cache_key] = store
    return store
