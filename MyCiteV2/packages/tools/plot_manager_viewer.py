"""Plot Manager — geospatial_projection developed into a plot-selection / cluster tool.

Built ON the ``geospatial_projection`` base (the field/plots map): renders the same
feature_collection, but the client wraps it with a DATE widget above (today by default,
inline-editable digits + a calendar icon) and, below, plot multi-select (single / ctrl /
shift click) + a CREATE button that records the dissolved-union outline of the selected
plots as a date-stamped *cluster* (POST /portal/api/v2/agro/create_cluster). Lives on the
agronomics PLAN tab (top-left).
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._registry import register
from ._shared.utilities import as_text as _as_text
from .geospatial_projection_viewer import build_geospatial_payload, resolve_farm_profile

_SCHEMA = "mycite.v2.portal.workbench.tool.plot_manager.v1"


class PlotManagerViewer:
    tool_id = "plot_manager"
    label = "Plot Manager"
    summary = "Field/plots map with a date widget and plot multi-select → create date-stamped clusters."
    route = WORKBENCH_UI_TOOL_ROUTE
    applies_to_archetype: tuple[str, ...] = ("hops_geospatial_filament",)
    applies_to_source_kind: tuple[str, ...] = ()

    def build_panel_payload(
        self, *, authority_db_file: Path | None, sandbox_id: str, document_id: str, datum_address: str,
    ) -> dict[str, Any]:
        doc, err = resolve_farm_profile(authority_db_file, sandbox_id, document_id, tool=self)
        if err:
            return {**err, "schema": _SCHEMA}
        geo = build_geospatial_payload(doc)
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox_id or "agro_erp",
            "document_id": _as_text(doc.document_id),
            "today": _date.today().isoformat(),  # default widget date (server's current day)
            "create_route": "/portal/api/v2/agro/create_cluster",
            **geo,
        }


register(PlotManagerViewer())
