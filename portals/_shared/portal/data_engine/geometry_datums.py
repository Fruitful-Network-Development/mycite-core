from __future__ import annotations

from typing import Any


GEOMETRY_TEMPLATES: dict[str, dict[str, Any]] = {
    "geometry.coordinate_point": {"layer": 30, "value_group": 1, "reference": "0-0-10"},
    "geometry.polygon_boundary": {"layer": 30, "value_group": 1, "reference": "0-0-11"},
    "geometry.parcel": {"layer": 31, "value_group": 1, "reference": "0-0-20"},
    "geometry.field": {"layer": 31, "value_group": 1, "reference": "0-0-21"},
    "geometry.plot": {"layer": 31, "value_group": 1, "reference": "0-0-22"},
    "livestock.product_type": {"layer": 20, "value_group": 1, "reference": "0-0-1"},
    "livestock.gestation_period": {"layer": 20, "value_group": 1, "reference": "0-0-2"},
}


def geometry_template_spec(template_id: str) -> dict[str, Any]:
    token = str(template_id or "").strip()
    return dict(GEOMETRY_TEMPLATES.get(token) or {})
