from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA = "mycite.v2.data.system_resource_workbench.surface.v1"

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_json_value(value: Any, *, field_name: str) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_json_value(item, field_name=f"{field_name}[]") for item in value]
    if isinstance(value, dict):
        out: dict[str, JsonValue] = {}
        for key, item in value.items():
            token = _as_text(key)
            if not token:
                raise ValueError(f"{field_name} keys must be non-empty strings")
            out[token] = _normalize_json_value(item, field_name=f"{field_name}.{token}")
        return out
    raise ValueError(f"{field_name} must be JSON-serializable data")


@dataclass(frozen=True)
class SystemDatumStoreRequest:
    tenant_id: str

    def __post_init__(self) -> None:
        tenant_id = _as_text(self.tenant_id).lower()
        if not tenant_id:
            raise ValueError("system_datum_store_request.tenant_id is required")
        object.__setattr__(self, "tenant_id", tenant_id)

    def to_dict(self) -> dict[str, str]:
        return {"tenant_id": self.tenant_id}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SystemDatumStoreRequest":
        if not isinstance(payload, dict):
            raise ValueError("system_datum_store_request must be a dict")
        return cls(tenant_id=payload.get("tenant_id"))


@dataclass(frozen=True)
class SystemDatumResourceRow:
    resource_id: str
    subject_ref: str
    relation: str
    object_ref: str
    labels: tuple[str, ...]
    raw: JsonValue

    def __post_init__(self) -> None:
        resource_id = _as_text(self.resource_id)
        if not resource_id:
            raise ValueError("system_datum_resource_row.resource_id is required")
        labels = tuple(_as_text(label) for label in self.labels if _as_text(label))
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "subject_ref", _as_text(self.subject_ref))
        object.__setattr__(self, "relation", _as_text(self.relation))
        object.__setattr__(self, "object_ref", _as_text(self.object_ref))
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "raw", _normalize_json_value(self.raw, field_name="system_datum_resource_row.raw"))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "resource_id": self.resource_id,
            "subject_ref": self.subject_ref,
            "relation": self.relation,
            "object_ref": self.object_ref,
            "labels": list(self.labels),
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SystemDatumResourceRow":
        if not isinstance(payload, dict):
            raise ValueError("system_datum_resource_row must be a dict")
        labels = payload.get("labels") or ()
        if not isinstance(labels, (list, tuple)):
            raise ValueError("system_datum_resource_row.labels must be a list")
        return cls(
            resource_id=payload.get("resource_id"),
            subject_ref=payload.get("subject_ref"),
            relation=payload.get("relation"),
            object_ref=payload.get("object_ref"),
            labels=tuple(str(label) for label in labels),
            raw=payload.get("raw"),
        )


@dataclass(frozen=True)
class SystemDatumWorkbenchResult:
    tenant_id: str
    rows: tuple[SystemDatumResourceRow, ...]
    source_files: dict[str, JsonValue]
    materialization_status: dict[str, JsonValue]
    warnings: tuple[str, ...] = ()
    schema: str = SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA

    def __post_init__(self) -> None:
        tenant_id = _as_text(self.tenant_id).lower()
        if not tenant_id:
            raise ValueError("system_datum_workbench_result.tenant_id is required")
        normalized_rows: list[SystemDatumResourceRow] = []
        for row in self.rows:
            normalized_rows.append(row if isinstance(row, SystemDatumResourceRow) else SystemDatumResourceRow.from_dict(row))
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "rows", tuple(normalized_rows))
        object.__setattr__(
            self,
            "source_files",
            _normalize_json_value(self.source_files, field_name="system_datum_workbench_result.source_files"),
        )
        object.__setattr__(
            self,
            "materialization_status",
            _normalize_json_value(
                self.materialization_status,
                field_name="system_datum_workbench_result.materialization_status",
            ),
        )
        object.__setattr__(self, "warnings", tuple(_as_text(warning) for warning in self.warnings if _as_text(warning)))

    @property
    def ok(self) -> bool:
        return self.row_count > 0 and self.materialization_status.get("canonical_source") == "loaded"

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schema": self.schema,
            "ok": self.ok,
            "tenant_id": self.tenant_id,
            "row_count": self.row_count,
            "rows": [row.to_dict() for row in self.rows],
            "source_files": self.source_files,
            "materialization_status": self.materialization_status,
            "warnings": list(self.warnings),
        }


@runtime_checkable
class SystemDatumStorePort(Protocol):
    def read_system_resource_workbench(self, request: SystemDatumStoreRequest) -> SystemDatumWorkbenchResult:
        """Read the canonical system datum workbench surface without legacy fallbacks."""
