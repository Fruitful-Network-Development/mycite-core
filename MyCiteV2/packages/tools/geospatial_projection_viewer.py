"""Geospatial Projection — the field/plots map base, derived from farm_profile.

The map half of the old farm_profile viewer, extracted so it can be reused: `farm_profile`
is now the CONSOLIDATED tool (profile_card identity + this geospatial projection), and
`plot_manager` builds on this. Resolves the agro_erp ``farm_profile`` HOPS filament (families
4→5→6→7) into a GeoJSON FeatureCollection (parcels / field / plots). Each PLOT feature carries
its lcl node (``properties.lcl_node``) so an interactive client (Plot Manager) can record which
plots a selection covers.
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

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.geospatial_projection.v1"
_LCL_MARKER = "rf.3-1-5"
_TITLE_MARKER = "rf.3-1-2"
PREVIEW_PLOT_EDGE_M = 60.0


def _feature(coords: list[tuple[float, float]], *, kind: str, label: str, fid: str,
             lcl_node: str = "") -> dict[str, Any] | None:
    if len(coords) < 3:
        return None
    ring = [[lon, lat] for lon, lat in coords]
    if ring[0] != ring[-1]:
        ring.append(ring[0])  # GeoJSON polygons are closed
    props: dict[str, Any] = {"kind": kind, "label": label}
    if lcl_node:
        props["lcl_node"] = lcl_node
    return {
        "type": "Feature",
        "id": fid,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": props,
    }


def build_geospatial_payload(doc: Any) -> dict[str, Any]:
    """Project a farm_profile filament doc → {feature_collection, feature_count, plots_source,
    parcel_count, field_count, plot_count}. Pure (no db); reused by farm_profile + plot_manager."""
    rows = {_as_text(r.datum_address): r for r in (getattr(doc, "rows", ()) or ())}

    # family-7 features: geometry address -> (kind, label, lcl_node). rf.3-1-5 => plot.
    feature_meta: dict[str, tuple[str, str, str]] = {}
    for addr, row in rows.items():
        if not addr.startswith("7-"):
            continue
        head = _row_head(row)
        lcl_node = ""
        label = _row_tail_label(row)
        for i in range(1, len(head) - 1):
            if _as_text(head[i]) == _LCL_MARKER:
                lcl_node = _as_text(head[i + 1])
            elif _as_text(head[i]) == _TITLE_MARKER and not label:
                label = decode_label(_as_text(head[i + 1]))
        geom_addr = next(
            (_as_text(t) for t in head[2:] if _as_text(t).startswith(("5-", "6-"))),
            "",
        )
        if geom_addr:
            feature_meta[geom_addr] = ("plot" if lcl_node else "property", label or addr, lcl_node)

    features: list[dict[str, Any]] = []
    field_polys: list[list[tuple[float, float]]] = []
    parcel_count = field_count = plot_count = 0
    for addr, row in sorted(rows.items()):
        if not addr.startswith("5-"):
            continue
        head = _row_head(row)
        ring_addr = next((_as_text(t) for t in head[1:] if _as_text(t).startswith("4-")), "")
        ring_row = rows.get(ring_addr)
        if ring_row is None:
            continue
        coords = resolve_coordinate(_row_head(ring_row))
        poly_label = _row_tail_label(row)
        meta = feature_meta.get(addr, ("", "", ""))
        lcl_node = meta[2]
        if poly_label.startswith("parcel"):
            kind, label = "parcel", poly_label
            parcel_count += 1
        elif poly_label == "field":
            kind, label = "field", "field"
            field_count += 1
            field_polys.append(coords)
        elif poly_label.startswith("plot"):
            kind, label = "plot", meta[1] or poly_label
            plot_count += 1
        else:
            kind, label = (meta[0] or "field"), (meta[1] or poly_label or addr)
            if kind == "plot":
                plot_count += 1
            else:
                kind = "field"
                field_polys.append(coords)
        feat = _feature(coords, kind=kind, label=label, fid=f"{doc.canonical_name}:{addr}",
                        lcl_node=lcl_node if kind == "plot" else "")
        if feat:
            features.append(feat)

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
                    feat = _feature(
                        [(x, y) for x, y in list(square.exterior.coords)],
                        kind="plot", label=f"plot_{idx}",
                        fid=f"{doc.canonical_name}:preview:{idx}",
                    )
                    if feat:
                        features.append(feat)
            plot_count = idx
        except Exception:
            plots_source = "unavailable"

    return {
        "feature_collection": {"type": "FeatureCollection", "features": features},
        "feature_count": len(features),
        "plots_source": plots_source,
        "parcel_count": parcel_count,
        "field_count": field_count,
        "plot_count": plot_count,
    }


def _error(message: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA, "error": message,
        "feature_collection": {"type": "FeatureCollection", "features": []}, "feature_count": 0,
    }


def resolve_farm_profile(authority_db_file: Path | None, sandbox_id: str, document_id: str, *, tool: Any):
    """Shared farm_profile doc resolution (by archetype, not the auto-selected anchor)."""
    docs, err = read_sandbox_catalog(authority_db_file, tenant_id=_TENANT_DEFAULT)
    if err:
        return None, _error(err)
    doc = resolve_tool_document(
        docs, tool=tool, sandbox=sandbox_id or "agro_erp",
        document_id=document_id, canonical_name="farm_profile",
    )
    if doc is None:
        return None, _error("farm_profile document not found")
    return doc, None


class GeospatialProjectionViewer:
    """The field/plots map (GeoJSON), the geospatial half of farm_profile."""

    tool_id = "geospatial_projection"
    label = "Geospatial Projection"
    summary = "Field and plot polygons projected from the farm_profile HOPS filament."
    route = WORKBENCH_UI_TOOL_ROUTE
    applies_to_archetype: tuple[str, ...] = ("hops_geospatial_filament",)
    applies_to_source_kind: tuple[str, ...] = ()

    def build_panel_payload(
        self, *, authority_db_file: Path | None, sandbox_id: str, document_id: str, datum_address: str,
    ) -> dict[str, Any]:
        doc, err = resolve_farm_profile(authority_db_file, sandbox_id, document_id, tool=self)
        if err:
            return err
        geo = build_geospatial_payload(doc)
        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox_id or "agro_erp",
            "document_id": _as_text(doc.document_id),
            "selected_row_address": _as_text(datum_address),
            **geo,
        }


register(GeospatialProjectionViewer())
