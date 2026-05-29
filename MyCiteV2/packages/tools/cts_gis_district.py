"""CTS-GIS district-profile thin tool (read-only, MOS-direct).

One of the single-use tools the monolithic CTS-GIS surface decomposes into: it
renders the SD-31 district collection and its member-precinct list, built directly
from MOS (``read_district_profile_static_from_mos``) — no heavy runtime, no slow
projection. Returned payload feeds ``__MYCITE_V2_TOOL_RENDERERS["cts_gis_district"]``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from . import _cts_gis_artifact as artifact
from ._registry import register

_SCHEMA = "mycite.v2.portal.workbench.tool.cts_gis_district.v1"


class CtsGisDistrictTool:
    """SD-31 district collection + member-precinct list (read-only)."""

    tool_id = "cts_gis_district"
    label = "CTS-GIS District Profile"
    summary = "District collection and its member precincts, resolved from MOS."
    route = WORKBENCH_UI_TOOL_ROUTE
    # Match the CTS-GIS map's eligibility exactly (archetype + sandbox_source) so the
    # decomposed thin tools surface wherever the map did. (Archetype-only refinement
    # is a deferred follow-up — would risk the tools vanishing if production cts_gis
    # docs aren't archetype-tagged at recognition time.)
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
            profile = artifact.read_district_profile(authority_db_file)
        except Exception as exc:  # pragma: no cover — defensive
            return _error(f"district profile unavailable: {exc}")
        members = list(profile.get("member_precinct_ids") or [])
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox_id,
            "document_id": document_id,
            "selected_row_address": datum_address,
            "collection_id": str(profile.get("collection_id") or ""),
            "collection_label": str(profile.get("label") or ""),
            "timeframe": str(profile.get("timeframe") or ""),
            "member_count": int(profile.get("member_count") or len(members)),
            "member_precinct_ids": members,
            "diagnostics": _diagnostics(profile),
        }


def _diagnostics(profile: dict[str, Any]) -> dict[str, Any]:
    return {"resolved": bool(profile), "source": "mos"}


def _error(message: str) -> dict[str, Any]:
    return {"schema": _SCHEMA, "error": message, "member_precinct_ids": [], "member_count": 0}


# Self-register on import.
register(CtsGisDistrictTool())
