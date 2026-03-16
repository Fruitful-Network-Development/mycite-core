from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldContract:
    field_id: str
    target_path: str
    datum_family: str
    constraint_family: str
    write_modes: list[str]
    multi_value: bool
    auto_create_prerequisites: bool
    update_scope: str
    lens_hint: str
    allowed_template_ids: list[str]
    required_field_keys: list[str]
    config_ref_surface: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "target_path": self.target_path,
            "datum_family": self.datum_family,
            "constraint_family": self.constraint_family,
            "write_modes": list(self.write_modes),
            "multi_value": self.multi_value,
            "auto_create_prerequisites": self.auto_create_prerequisites,
            "update_scope": self.update_scope,
            "lens_hint": self.lens_hint,
            "allowed_template_ids": list(self.allowed_template_ids),
            "required_field_keys": list(self.required_field_keys),
            "config_ref_surface": self.config_ref_surface,
        }

    def validate_fields(self, fields: dict[str, Any]) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        payload = fields if isinstance(fields, dict) else {}
        for key in self.required_field_keys:
            token = str(payload.get(key) or "").strip()
            if not token:
                errors.append(f"missing required field: {key}")
        if self.constraint_family == "duration.days":
            raw = str(payload.get("duration_days") or "").strip()
            if raw:
                try:
                    value = int(raw)
                    if value <= 0:
                        errors.append("duration_days must be > 0")
                except Exception:
                    errors.append("duration_days must be an integer")
        if self.multi_value and self.update_scope.endswith("config_ref"):
            existing = payload.get("existing_refs")
            if existing and not isinstance(existing, list):
                warnings.append("existing_refs should be a list for multi-value ref updates")
        return errors, warnings


def default_profile_field_contracts() -> dict[str, FieldContract]:
    return {
        "portal_title": FieldContract(
            field_id="portal_title",
            target_path="display.title",
            datum_family="text.title",
            constraint_family="ascii_string",
            write_modes=["select_existing_ref", "create_new_local_datum"],
            multi_value=False,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
            lens_hint="text.inline",
            allowed_template_ids=["geometry.parcel", "geometry.field", "geometry.plot"],
            required_field_keys=["local_id", "title"],
            config_ref_surface=True,
        ),
        "property_title": FieldContract(
            field_id="property_title",
            target_path="property.title",
            datum_family="text.title",
            constraint_family="ascii_string",
            write_modes=["select_existing_ref", "create_new_local_datum"],
            multi_value=False,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
            lens_hint="text.inline",
            allowed_template_ids=["geometry.parcel", "geometry.field", "geometry.plot"],
            required_field_keys=["local_id", "title"],
            config_ref_surface=True,
        ),
        "property_bbox": FieldContract(
            field_id="property_bbox",
            target_path="property.bbox",
            datum_family="geometry.bbox",
            constraint_family="geometry.bbox",
            write_modes=["select_existing_ref", "create_new_local_datum", "resolve_then_materialize"],
            multi_value=True,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
            lens_hint="geometry.bbox",
            allowed_template_ids=["geometry.coordinate_point", "geometry.polygon_boundary"],
            required_field_keys=["local_id"],
            config_ref_surface=True,
        ),
        "property_boundary": FieldContract(
            field_id="property_boundary",
            target_path="property.geometry.coordinates",
            datum_family="geometry.polygon",
            constraint_family="geometry.polygon",
            write_modes=["select_existing_ref", "create_new_local_datum", "resolve_then_materialize"],
            multi_value=True,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
            lens_hint="geometry.polygon",
            allowed_template_ids=["geometry.coordinate_point", "geometry.polygon_boundary"],
            required_field_keys=["local_id"],
            config_ref_surface=True,
        ),
        "livestock_gestation": FieldContract(
            field_id="livestock_gestation",
            target_path="agro.livestock.gestation_period_ref",
            datum_family="livestock.gestation_period",
            constraint_family="duration.days",
            write_modes=["select_existing_ref", "create_new_local_datum"],
            multi_value=False,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
            lens_hint="duration.days",
            allowed_template_ids=["livestock.gestation_period"],
            required_field_keys=["local_id", "duration_days", "title"],
            config_ref_surface=True,
        ),
    }
