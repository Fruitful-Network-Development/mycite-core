from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldContract:
    field_id: str
    target_path: str
    constraint_family: str
    write_modes: list[str]
    multi_value: bool
    auto_create_prerequisites: bool
    update_scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "target_path": self.target_path,
            "constraint_family": self.constraint_family,
            "write_modes": list(self.write_modes),
            "multi_value": self.multi_value,
            "auto_create_prerequisites": self.auto_create_prerequisites,
            "update_scope": self.update_scope,
        }


def default_profile_field_contracts() -> dict[str, FieldContract]:
    return {
        "portal_title": FieldContract(
            field_id="portal_title",
            target_path="display.title",
            constraint_family="ascii_string",
            write_modes=["select_existing_ref", "create_new_local_datum"],
            multi_value=False,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
        ),
        "property_title": FieldContract(
            field_id="property_title",
            target_path="property.title",
            constraint_family="ascii_string",
            write_modes=["select_existing_ref", "create_new_local_datum"],
            multi_value=False,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
        ),
        "property_bbox": FieldContract(
            field_id="property_bbox",
            target_path="property.bbox",
            constraint_family="geometry.bbox",
            write_modes=["select_existing_ref", "create_new_local_datum", "resolve_then_materialize"],
            multi_value=True,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
        ),
        "property_boundary": FieldContract(
            field_id="property_boundary",
            target_path="property.geometry.coordinates",
            constraint_family="geometry.polygon",
            write_modes=["select_existing_ref", "create_new_local_datum", "resolve_then_materialize"],
            multi_value=True,
            auto_create_prerequisites=True,
            update_scope="anthology+config_ref",
        ),
    }
