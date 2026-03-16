from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DatumTemplate:
    template_id: str
    datum_family: str
    layer: int
    value_group: int
    reference: str
    required_inputs: list[str]
    prerequisite_ref_fields: list[str]
    parent_ref_field: str
    title_field: str
    id_field: str
    update_scope: str
    duplicate_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "datum_family": self.datum_family,
            "layer": self.layer,
            "value_group": self.value_group,
            "reference": self.reference,
            "required_inputs": list(self.required_inputs),
            "prerequisite_ref_fields": list(self.prerequisite_ref_fields),
            "parent_ref_field": self.parent_ref_field,
            "title_field": self.title_field,
            "id_field": self.id_field,
            "update_scope": self.update_scope,
            "duplicate_policy": self.duplicate_policy,
        }

    def validate_fields(self, fields: dict[str, Any]) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        payload = fields if isinstance(fields, dict) else {}
        for key in self.required_inputs:
            if not str(payload.get(key) or "").strip():
                errors.append(f"missing required input: {key}")
        for key in self.prerequisite_ref_fields:
            token = str(payload.get(key) or "").strip()
            if token and "." not in token and "-" not in token:
                warnings.append(f"prerequisite ref {key} does not look canonical: {token}")
        return errors, warnings


TEMPLATES: dict[str, DatumTemplate] = {
    "geometry.coordinate_point": DatumTemplate(
        template_id="geometry.coordinate_point",
        datum_family="geometry.coordinate_point",
        layer=30,
        value_group=1,
        reference="0-0-10",
        required_inputs=["local_id", "title"],
        prerequisite_ref_fields=[],
        parent_ref_field="",
        title_field="title",
        id_field="local_id",
        update_scope="anthology_only",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
    "geometry.polygon_boundary": DatumTemplate(
        template_id="geometry.polygon_boundary",
        datum_family="geometry.polygon_boundary",
        layer=30,
        value_group=1,
        reference="0-0-11",
        required_inputs=["local_id", "title"],
        prerequisite_ref_fields=["point_ref"],
        parent_ref_field="",
        title_field="title",
        id_field="local_id",
        update_scope="anthology_only",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
    "geometry.parcel": DatumTemplate(
        template_id="geometry.parcel",
        datum_family="geometry.parcel",
        layer=31,
        value_group=1,
        reference="0-0-20",
        required_inputs=["local_id", "title"],
        prerequisite_ref_fields=["boundary_ref"],
        parent_ref_field="property_ref",
        title_field="title",
        id_field="local_id",
        update_scope="anthology+config_ref",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
    "geometry.field": DatumTemplate(
        template_id="geometry.field",
        datum_family="geometry.field",
        layer=31,
        value_group=1,
        reference="0-0-21",
        required_inputs=["local_id", "title"],
        prerequisite_ref_fields=["parcel_ref", "boundary_ref"],
        parent_ref_field="parcel_ref",
        title_field="title",
        id_field="local_id",
        update_scope="anthology+config_ref",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
    "geometry.plot": DatumTemplate(
        template_id="geometry.plot",
        datum_family="geometry.plot",
        layer=31,
        value_group=1,
        reference="0-0-22",
        required_inputs=["local_id", "title"],
        prerequisite_ref_fields=["field_ref", "boundary_ref"],
        parent_ref_field="field_ref",
        title_field="title",
        id_field="local_id",
        update_scope="anthology+config_ref",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
    "livestock.product_type": DatumTemplate(
        template_id="livestock.product_type",
        datum_family="livestock.product_type",
        layer=20,
        value_group=1,
        reference="0-0-1",
        required_inputs=["local_id", "title", "taxonomy_ref"],
        prerequisite_ref_fields=["taxonomy_ref"],
        parent_ref_field="",
        title_field="title",
        id_field="local_id",
        update_scope="anthology_only",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
    "livestock.gestation_period": DatumTemplate(
        template_id="livestock.gestation_period",
        datum_family="livestock.gestation_period",
        layer=20,
        value_group=1,
        reference="0-0-2",
        required_inputs=["local_id", "title", "taxonomy_ref", "duration_days"],
        prerequisite_ref_fields=["taxonomy_ref"],
        parent_ref_field="",
        title_field="title",
        id_field="local_id",
        update_scope="anthology_only",
        duplicate_policy="reuse_if_local_ref_exists",
    ),
}

# Backward-compatible read-only dict of template specs.
GEOMETRY_TEMPLATES: dict[str, dict[str, Any]] = {key: value.to_dict() for key, value in TEMPLATES.items()}


def geometry_template_spec(template_id: str) -> dict[str, Any]:
    token = str(template_id or "").strip()
    template = TEMPLATES.get(token)
    return template.to_dict() if template is not None else {}


def validate_template_fields(template_id: str, fields: dict[str, Any]) -> tuple[list[str], list[str]]:
    token = str(template_id or "").strip()
    template = TEMPLATES.get(token)
    if template is None:
        return ([f"unknown template_id: {token}"] if token else ["template_id is required"]), []
    return template.validate_fields(fields if isinstance(fields, dict) else {})
