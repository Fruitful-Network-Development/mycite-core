"""CTS-GIS map thin tool (read-only, compiled-artifact fast-read).

Renders the precinct/district map as a leaflet feature collection read from the
**compiled artifact's** pre-rendered ``projection_model`` — NOT from the slow
``CtsGisReadOnlyService.read_projection_bundle`` (~35s / ~700MB → gunicorn SIGKILL
→ nginx 504). The compiled-artifact root is configured once at app startup
(:func:`_cts_gis_artifact.configure_data_dir`). Feeds
``window.__MYCITE_V2_TOOL_RENDERERS["cts_gis"]``.

(The artifact is rebuilt by ``scripts/compile_cts_gis_artifact.py``; the map renders
empty until a recompile populates ``projection_model.feature_collection``.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from . import _cts_gis_artifact as artifact
from ._registry import register

_SCHEMA = "mycite.v2.portal.workbench.tool.cts_gis_map.v1"


class CtsGisMapTool:
    """Spatial projection of the SAMRAS-family precinct map (compiled fast-read)."""

    tool_id = "cts_gis"
    label = "CTS-GIS Map"
    summary = "Pre-rendered precinct/district map projection."
    route = WORKBENCH_UI_TOOL_ROUTE
    applies_to_archetype: tuple[str, ...] = ("samras_family",)
    applies_to_source_kind: tuple[str, ...] = ("sandbox_source",)

    def build_panel_payload(
        self,
        *,
        authority_db_file: Path | None,
        sandbox_id: str,
        document_id: str,
        datum_address: str,
    ) -> dict[str, Any]:
        try:
            projection = artifact.read_map_projection()
        except Exception as exc:  # pragma: no cover — defensive
            return _error_payload(f"projection unavailable: {exc}")

        feature_collection = dict(projection.get("feature_collection") or {})
        features = list(feature_collection.get("features") or [])
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox_id,
            "document_id": document_id,
            "selected_row_address": datum_address,
            "focus_node_id": str(projection.get("focus_node_id") or ""),
            "focus_bounds": list(projection.get("focus_bounds") or projection.get("bounds") or []),
            "projection_state": str(projection.get("projection_state") or ("ready" if features else "empty")),
            "feature_count": int(projection.get("feature_count") or len(features)),
            "feature_collection": feature_collection,
            "diagnostics": {"resolved": bool(projection), "source": "compiled_artifact"},
        }


def _error_payload(message: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "error": message,
        "feature_collection": {"type": "FeatureCollection", "features": []},
        "feature_count": 0,
    }


# Self-register on import.
register(CtsGisMapTool())
