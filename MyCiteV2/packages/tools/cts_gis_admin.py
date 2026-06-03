"""CTS-GIS admin-profile thin tool (read-only, MOS-direct).

Renders the spatial-administrative root identity (Ohio node 3-2-3-17: node_id,
label, capital_msn_id, fields) and any present geometry, built directly from MOS
(``read_admin_profile_static_from_mos``) — no heavy runtime, no slow projection.
Feeds ``__MYCITE_V2_TOOL_RENDERERS["cts_gis_admin"]``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from . import _cts_gis_artifact as artifact

_SCHEMA = "mycite.v2.portal.workbench.tool.cts_gis_admin.v1"


class CtsGisAdminTool:
    """Spatial-administrative root identity + fields + (when present) geometry."""

    tool_id = "cts_gis_admin"
    label = "CTS-GIS Admin Profile"
    summary = "Administrative root identity and fields, resolved from MOS."
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
        if authority_db_file is None:
            return _error("authority database not configured")
        try:
            profile = artifact.read_admin_profile(authority_db_file)
        except Exception as exc:  # pragma: no cover — defensive
            return _error(f"admin profile unavailable: {exc}")
        projection = dict(profile.get("geospatial_projection") or {})
        features = list(projection.get("features") or [])
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox_id,
            "document_id": document_id,
            "selected_row_address": datum_address,
            "node_id": str(profile.get("node_id") or ""),
            "node_label": str(profile.get("label") or ""),
            "capital_msn_id": str(profile.get("capital_msn_id") or ""),
            "fields": list(profile.get("fields") or []),
            "has_real_projection": bool(projection.get("has_real_projection")),
            "feature_count": len(features),
            "diagnostics": {"resolved": bool(profile), "source": "mos"},
        }


def _error(message: str) -> dict[str, Any]:
    return {"schema": _SCHEMA, "error": message, "fields": [], "feature_count": 0}


# RETIRED from the viz palette (no longer self-registers). See packages/tools/__init__.py.
