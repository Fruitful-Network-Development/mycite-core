"""Farm-profile viewer — the first agro_erp geospatial Plan-v2 visualizer.

Reads the agro_erp ``farm_profile`` document (a CTS-GIS HOPS filament, families
4→5→6→7) live and emits a GeoJSON FeatureCollection the workbench viz panel paints
as an inline-SVG map: the property field polygons plus the equal-square plots. When
the plots have been migrated INTO farm_profile (TASK-2026-06-02-006) the persisted
plot squares are rendered; otherwise the squares are computed live from the field
geometry via the square-packing function (TASK-2026-06-02-004) as a preview.

See plans/TASK-003-farm-plot-model.md. Eligibility is by shape — the doc resolves as
``hops_geospatial_filament`` via the palette's archetype derivation (TASK-008).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import decode_label, resolve_coordinate
from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._archetype import read_sandbox_catalog, resolve_tool_document
from ._registry import register
from ._shared.utilities import as_text as _as_text
from ._shared.utilities import row_head as _row_head
from ._shared.utilities import row_tail_label as _row_tail_label
from .profile_projection import build_profile_projection

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.farm_profile.v1"
_LCL_MARKER = "rf.3-1-5"
_TITLE_MARKER = "rf.3-1-2"
# Edge length (metres) for the LIVE preview packing when plots are not yet migrated.
# The migration (TASK-006) persists plots at the operator-chosen --plot-edge-m; this
# preview uses a coarser default so the unmigrated view is legible.
PREVIEW_PLOT_EDGE_M = 60.0


def _error(message: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "error": message,
        "feature_collection": {"type": "FeatureCollection", "features": []},
        "feature_count": 0,
        "fields": [],
    }


def _feature(coords: list[tuple[float, float]], *, kind: str, label: str, fid: str) -> dict[str, Any] | None:
    if len(coords) < 3:
        return None
    ring = [[lon, lat] for lon, lat in coords]
    if ring[0] != ring[-1]:
        ring.append(ring[0])  # GeoJSON polygons are closed
    return {
        "type": "Feature",
        "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"kind": kind, "label": label},
    }


class FarmProfileViewer:
    """Render the agro_erp farm_profile: property/field polygons + plot squares."""

    tool_id = "farm_profile"
    label = "Farm Profile"
    summary = "Property fields and equal-square plots projected from the farm_profile HOPS filament."
    route = WORKBENCH_UI_TOOL_ROUTE
    applies_to_archetype: tuple[str, ...] = ("hops_geospatial_filament",)
    applies_to_source_kind: tuple[str, ...] = ()

    def build_panel_payload(
        self,
        *,
        authority_db_file: Path | None,
        sandbox_id: str,
        document_id: str,
        datum_address: str,
    ) -> dict[str, Any]:
        docs, err = read_sandbox_catalog(authority_db_file, tenant_id=_TENANT_DEFAULT)
        if err:
            return _error(err)
        # Resolve the farm_profile by archetype — NOT by trusting the selected
        # document_id. The workbench auto-selects the first sandbox doc (the
        # geometry-less anchor); resolving by document_id alone rendered that wrong
        # doc as an empty map. resolve_tool_document honors the selection only when
        # it actually matches this tool, else finds the real farm_profile.
        doc = resolve_tool_document(
            docs,
            tool=self,
            sandbox=sandbox_id or "agro_erp",
            document_id=document_id,
            canonical_name="farm_profile",
        )
        if doc is None:
            return _error("farm_profile document not found")

        rows = {_as_text(r.datum_address): r for r in (getattr(doc, "rows", ()) or ())}

        # family-7 features: map geometry address -> (kind, label). rf.3-1-5 => plot
        # (lcl-bound); rf.3-1-4 => the property/profile feature.
        feature_meta: dict[str, tuple[str, str]] = {}
        for addr, row in rows.items():
            if not addr.startswith("7-"):
                continue
            head = _row_head(row)
            is_plot = any(_as_text(t) == _LCL_MARKER for t in head)
            label = _row_tail_label(row)
            if not label:
                for i in range(len(head) - 1):
                    if _as_text(head[i]) == _TITLE_MARKER:
                        label = decode_label(_as_text(head[i + 1]))
                        break
            geom_addr = next(
                (_as_text(t) for t in head[2:] if _as_text(t).startswith(("5-", "6-"))),
                "",
            )
            if geom_addr:
                feature_meta[geom_addr] = ("plot" if is_plot else "property", label or addr)

        # Resolve each family-5 polygon → ring coords → GeoJSON feature.
        features: list[dict[str, Any]] = []
        field_polys: list[list[tuple[float, float]]] = []
        plot_count = 0
        for addr, row in sorted(rows.items()):
            if not addr.startswith("5-"):
                continue
            head = _row_head(row)
            ring_addr = next((_as_text(t) for t in head[1:] if _as_text(t).startswith("4-")), "")
            ring_row = rows.get(ring_addr)
            if ring_row is None:
                continue
            coords = resolve_coordinate(_row_head(ring_row))
            kind, label = feature_meta.get(addr, ("field", _row_tail_label(row) or addr))
            if kind == "plot":
                plot_count += 1
            else:
                kind = "field"
                field_polys.append(coords)
            feat = _feature(coords, kind=kind, label=label, fid=f"{doc.canonical_name}:{addr}")
            if feat:
                features.append(feat)

        # No migrated plots yet → compute a live preview by packing each field.
        plots_source = "migrated" if plot_count else "live_preview"
        if not plot_count:
            try:
                from shapely.geometry import Polygon

                from MyCiteV2.packages.core.hops.square_pack import pack_squares

                idx = 0
                for coords in field_polys:
                    if len(coords) < 3:
                        continue
                    for square in pack_squares(Polygon(coords), edge_m=PREVIEW_PLOT_EDGE_M):
                        idx += 1
                        sq_coords = list(square.exterior.coords)
                        feat = _feature(
                            [(x, y) for x, y in sq_coords],
                            kind="plot",
                            label=f"plot_{idx}",
                            fid=f"{doc.canonical_name}:preview:{idx}",
                        )
                        if feat:
                            features.append(feat)
                plot_count = idx
            except Exception:
                plots_source = "unavailable"

        # Compose the base profile-card projection for the identity (title + SAMRAS id + visual),
        # then EXTEND it with the filament's own fields — farm_profile is BUILT ON profile_card.
        profile = build_profile_projection(doc)
        fields = [
            {"label": "title", "value": profile["title"] or doc.canonical_name},
            {"label": "samras_node", "value": profile["samras_node"]},
            {"label": "fields", "value": str(len(field_polys))},
            {"label": "plots", "value": str(plot_count)},
            {"label": "plots_source", "value": plots_source},
        ]
        if plots_source == "live_preview":
            fields.append({"label": "preview_plot_edge_m", "value": str(PREVIEW_PLOT_EDGE_M)})

        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox_id or "agro_erp",
            "document_id": _as_text(doc.document_id),
            "selected_row_address": _as_text(datum_address),
            "profile": profile,
            "fields": fields,
            "feature_count": len(features),
            "plots_source": plots_source,
            "feature_collection": {"type": "FeatureCollection", "features": features},
        }


# Self-register on import.
register(FarmProfileViewer())
