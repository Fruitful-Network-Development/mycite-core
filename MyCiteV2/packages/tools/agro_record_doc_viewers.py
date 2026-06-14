"""Viewers for the Phase-5 seed datum docs: livestock / equipment / soil / growing_season.

Each is a one-class :class:`DatumDocTool` over a shared ``_RecordDocViewer`` base — proof
that a new agro_erp record doc becomes a tool by DECLARATION (canonical_name + schema +
a field map), with no new backend preamble and no new JS (they emit the shared
``record_table`` container). The field map names each ``4-3-N`` pair's column + kind
(node-ref resolved via NameIndex, title/nominal decoded).
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    Markers,
    cached_index,
    decode_label,
    iter_marker_pairs,
)

from ._archetype import find_named_document
from ._contract import DatumDocTool
from ._registry import register
from ._shared.utilities import as_text as _as_text
from ._shared.utilities import row_head as _row_head


class _RecordDocViewer(DatumDocTool):
    """Render a sandbox PAIRS record doc (``4-3-N`` rows) as a record_table."""

    container = "record_table"
    title = ""
    # Column names, in head-pair order. The VALUE kind is derived from each pair's
    # marker (node-ref → resolved via NameIndex; else decoded), so a marker/kind
    # mismatch is impossible. Column order must match the doc's 4-3-N head order.
    fields: tuple[str, ...] = ()

    def empty_body(self) -> dict[str, Any]:
        return {"container": self.container, "columns": [], "rows": [], "row_count": 0}

    def shape_payload(self, *, doc: Any, docs: list[Any], sandbox: str, datum_address: str) -> dict[str, Any]:
        lcl = cached_index(find_named_document(docs, sandbox=sandbox, name="lcl"))
        rows: list[dict[str, Any]] = []
        for row in getattr(doc, "rows", ()) or ():
            if not _as_text(row.datum_address).startswith("4-3-"):
                continue
            pairs = list(iter_marker_pairs(_row_head(row)))
            rec: dict[str, Any] = {}
            for col, (marker, value) in zip(self.fields, pairs, strict=False):
                if Markers.is_node_ref(marker):
                    v = _as_text(value)
                    rec[col] = lcl.resolve(v) or v
                else:
                    rec[col] = decode_label(value)
            rows.append(rec)
        return {
            "container": self.container,
            "title": self.title,
            "count_label": f"{len(rows)} record{'' if len(rows) == 1 else 's'}",
            "columns": list(self.fields),
            "rows": rows,
            "row_count": len(rows),
            "empty_text": f"No {self.title.lower()} records.",
        }


class LivestockViewer(_RecordDocViewer):
    tool_id = "livestock"
    label = "Livestock"
    summary = "Animals on the farm (lcl animal node, tag, head count)."
    schema = "mycite.v2.portal.workbench.tool.livestock.v1"
    canonical_name = "livestock"
    title = "Livestock"
    fields = ("animal", "tag", "count")
    applies_to_archetype = ("mycite.v2.datum.agro_erp.livestock.v1",)


class EquipmentViewer(_RecordDocViewer):
    tool_id = "equipment"
    label = "Equipment"
    summary = "Farm equipment / tractors (lcl equipment node, model, acquisition cost)."
    schema = "mycite.v2.portal.workbench.tool.equipment.v1"
    canonical_name = "equipment"
    title = "Equipment"
    fields = ("equipment", "model", "cost")
    applies_to_archetype = ("mycite.v2.datum.agro_erp.equipment.v1",)


class SoilViewer(_RecordDocViewer):
    tool_id = "soil"
    label = "Soil"
    summary = "Per-plot soil type and acreage (ecologicals)."
    schema = "mycite.v2.portal.workbench.tool.soil.v1"
    canonical_name = "soil"
    title = "Soil"
    fields = ("plot", "soil_type", "acres")
    applies_to_archetype = ("mycite.v2.datum.agro_erp.soil.v1",)


class GrowingSeasonViewer(_RecordDocViewer):
    tool_id = "growing_season"
    label = "Growing Season"
    summary = "Growing-season windows by Raunkiær life-form (ecologicals)."
    schema = "mycite.v2.portal.workbench.tool.growing_season.v1"
    canonical_name = "growing_season"
    title = "Growing Season"
    fields = ("raunkiaerality", "season", "growing_degree_days")
    applies_to_archetype = ("mycite.v2.datum.agro_erp.growing_season.v1",)


for _tool in (LivestockViewer(), EquipmentViewer(), SoilViewer(), GrowingSeasonViewer()):
    register(_tool)
