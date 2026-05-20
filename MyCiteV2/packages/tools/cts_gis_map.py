"""CTS-GIS map tool — the first Plan-v2 visualization tool.

Wraps :class:`CtsGisReadOnlyService` so the workbench's visualization
panel can render a leaflet projection of a SAMRAS-family document
without owning a dedicated portal surface or activity-bar slot.

Mediation (write) is deferred — this read-only tool exists to prove
the new visualization-panel contract end-to-end against the existing
projection service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.modules.cross_domain.cts_gis.service import (
    CtsGisReadOnlyService,
)

from ._registry import register

_TENANT_DEFAULT = "fnd"


class CtsGisMapTool:
    """Spatial projection of a SAMRAS-family document as a leaflet feature
    collection. Returned panel_payload feeds
    ``window.__MYCITE_V2_TOOL_RENDERERS["cts_gis"]`` in the JS layer.
    """

    tool_id = "cts_gis"
    label = "CTS-GIS Map"
    summary = "Spatial projection of a SAMRAS-family document on an interactive map."
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
        if authority_db_file is None:
            return _error_payload("authority database not configured")
        try:
            store = SqliteSystemDatumStoreAdapter(authority_db_file)
        except Exception as exc:  # pragma: no cover — adapter init is defensive
            return _error_payload(f"datum store unavailable: {exc}")

        service = CtsGisReadOnlyService(store)
        try:
            bundle = service.read_projection_bundle(
                tenant_id=_TENANT_DEFAULT,
                selected_document_id=document_id,
                selected_row_address=datum_address,
                attention_document_id=document_id,
                overlay_mode="auto",
                project_all_documents=not document_id,
            )
        except Exception as exc:  # pragma: no cover — service is defensive
            return _error_payload(f"projection failed: {exc}")

        documents = list(bundle.get("documents") or [])
        # Prefer the selected document; fall back to whatever the
        # service surfaced first (its default-projection logic).
        target_bundle: dict[str, Any] = {}
        if document_id:
            target_bundle = next(
                (
                    doc for doc in documents
                    if str((doc or {}).get("document_id") or "") == document_id
                ),
                {},
            )
        if not target_bundle and documents:
            target_bundle = documents[0]

        map_projection = dict(target_bundle.get("map_projection") or {})
        feature_collection = dict(map_projection.get("feature_collection") or {})
        focus_node_id = str(map_projection.get("focus_node_id") or "")
        focus_bounds = list(map_projection.get("focus_bounds") or [])
        projection_state = str(map_projection.get("projection_state") or "pending")
        feature_count = int(map_projection.get("feature_count") or 0)

        return {
            "schema": "mycite.v2.portal.workbench.tool.cts_gis_map.v1",
            "sandbox_id": sandbox_id,
            "document_id": (
                str(target_bundle.get("document_id") or document_id or "")
            ),
            "selected_row_address": datum_address,
            "focus_node_id": focus_node_id,
            "focus_bounds": focus_bounds,
            "projection_state": projection_state,
            "feature_count": feature_count,
            "feature_collection": feature_collection,
        }


def _error_payload(message: str) -> dict[str, Any]:
    return {
        "schema": "mycite.v2.portal.workbench.tool.cts_gis_map.v1",
        "error": message,
        "feature_collection": {"type": "FeatureCollection", "features": []},
        "feature_count": 0,
    }


# Self-register on import.
register(CtsGisMapTool())
