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

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.hops.square_pack import pack_squares
from MyCiteV2.packages.core.structures.hops import decode_hops_coordinate_token
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.packages.state_machine.lens.base import BinaryTextLens
from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._registry import register

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.farm_profile.v1"
_HOPS_MARKER = "rf.3-1-3"
_LCL_MARKER = "rf.3-1-5"
_TITLE_MARKER = "rf.3-1-2"
# Edge length (metres) for the LIVE preview packing when plots are not yet migrated.
# The migration (TASK-006) persists plots at the operator-chosen --plot-edge-m; this
# preview uses a coarser default so the unmigrated view is legible.
PREVIEW_PLOT_EDGE_M = 60.0
_BINARY_TEXT = BinaryTextLens()


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _error(message: str) -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "error": message,
        "feature_collection": {"type": "FeatureCollection", "features": []},
        "feature_count": 0,
        "fields": [],
    }


def _row_head(row: Any) -> list[Any]:
    raw = getattr(row, "raw", None)
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        return raw[0]
    return raw if isinstance(raw, list) else []


def _row_tail_label(row: Any) -> str:
    raw = getattr(row, "raw", None)
    if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], list) and raw[1]:
        return _as_text(raw[1][0])
    return ""


def _decode_title_bits(bits: str) -> str:
    try:
        text = "".join(chr(int(bits[i : i + 8], 2)) for i in range(0, len(bits), 8))
        return text.rstrip("\x00")
    except Exception:
        return ""


def _ring_coords(head: list[Any]) -> list[tuple[float, float]]:
    """Decode a family-4 ring row head (rf.3-1-3 HOPS tokens) → lon/lat coords."""
    coords: list[tuple[float, float]] = []
    for i in range(len(head) - 1):
        if _as_text(head[i]) == _HOPS_MARKER:
            decoded = decode_hops_coordinate_token(_as_text(head[i + 1]))
            if decoded:
                coords.append((decoded["longitude"]["value"], decoded["latitude"]["value"]))
    return coords


def _find_named(docs: list[AuthoritativeDatumDocument], sandbox: str, name: str) -> AuthoritativeDatumDocument | None:
    for doc in docs:
        if _as_text(getattr(doc, "canonical_name", "")) == name:
            parts = _as_text(getattr(doc, "document_id", "")).split(".")
            if not sandbox or (len(parts) > 4 and parts[2] == sandbox):
                return doc
    return None


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
        if authority_db_file is None:
            return _error("authority database not configured")
        try:
            store = SqliteSystemDatumStoreAdapter(authority_db_file)
            catalog = store.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id=_TENANT_DEFAULT)
            )
        except Exception as exc:
            return _error(f"datum store unavailable: {exc}")

        docs = list(getattr(catalog, "documents", ()) or ())
        doc = next((d for d in docs if _as_text(getattr(d, "document_id", "")) == _as_text(document_id)), None)
        if doc is None:
            doc = _find_named(docs, sandbox_id or "agro_erp", "farm_profile")
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
                        label = _decode_title_bits(_as_text(head[i + 1]))
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
            coords = _ring_coords(_row_head(ring_row))
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

        metadata = getattr(doc, "document_metadata", None) or {}
        fields = [
            {"label": "title", "value": _as_text(metadata.get("title")) or doc.canonical_name},
            {"label": "samras_node", "value": _as_text(metadata.get("msn_node"))},
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
            "fields": fields,
            "feature_count": len(features),
            "plots_source": plots_source,
            "feature_collection": {"type": "FeatureCollection", "features": features},
        }


# Self-register on import.
register(FarmProfileViewer())
