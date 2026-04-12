from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

SYSTEM_DATUM_RESOURCE_WORKBENCH_SCHEMA = "mycite.v2.data.system_resource_workbench.surface.v1"
PUBLICATION_TENANT_SUMMARY_SOURCE_SCHEMA = "mycite.v2.data.publication_tenant_summary.source.v1"

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


@dataclass(frozen=True)
class PublicationTenantSummaryRequest:
    tenant_id: str
    tenant_domain: str

    def __post_init__(self) -> None:
        tenant_id = _as_text(self.tenant_id).lower()
        tenant_domain = _as_text(self.tenant_domain).lower()
        if not tenant_id:
            raise ValueError("publication_tenant_summary_request.tenant_id is required")
        if not tenant_domain or "." not in tenant_domain:
            raise ValueError("publication_tenant_summary_request.tenant_domain must be a domain-like value")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "tenant_domain", tenant_domain)

    def to_dict(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "tenant_domain": self.tenant_domain,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicationTenantSummaryRequest":
        if not isinstance(payload, dict):
            raise ValueError("publication_tenant_summary_request must be a dict")
        return cls(
            tenant_id=payload.get("tenant_id"),
            tenant_domain=payload.get("tenant_domain"),
        )


def _normalize_optional_object_payload(value: Any, *, field_name: str) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict or null")
    normalized = _normalize_json_value(value, field_name=field_name)
    if not isinstance(normalized, dict):
        raise ValueError(f"{field_name} must be a dict or null")
    return normalized


@dataclass(frozen=True)
class PublicationTenantSummarySource:
    tenant_id: str
    tenant_domain: str
    profile_id: str
    public_profile: dict[str, JsonValue] | None
    tenant_profile: dict[str, JsonValue] | None
    schema: str = PUBLICATION_TENANT_SUMMARY_SOURCE_SCHEMA

    def __post_init__(self) -> None:
        tenant_id = _as_text(self.tenant_id).lower()
        tenant_domain = _as_text(self.tenant_domain).lower()
        profile_id = _as_text(self.profile_id)
        if not tenant_id:
            raise ValueError("publication_tenant_summary_source.tenant_id is required")
        if not tenant_domain or "." not in tenant_domain:
            raise ValueError("publication_tenant_summary_source.tenant_domain must be a domain-like value")
        if not profile_id:
            raise ValueError("publication_tenant_summary_source.profile_id is required")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "tenant_domain", tenant_domain)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(
            self,
            "public_profile",
            _normalize_optional_object_payload(
                self.public_profile,
                field_name="publication_tenant_summary_source.public_profile",
            ),
        )
        object.__setattr__(
            self,
            "tenant_profile",
            _normalize_optional_object_payload(
                self.tenant_profile,
                field_name="publication_tenant_summary_source.tenant_profile",
            ),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schema": self.schema,
            "tenant_id": self.tenant_id,
            "tenant_domain": self.tenant_domain,
            "profile_id": self.profile_id,
            "public_profile": self.public_profile,
            "tenant_profile": self.tenant_profile,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicationTenantSummarySource":
        if not isinstance(payload, dict):
            raise ValueError("publication_tenant_summary_source must be a dict")
        return cls(
            tenant_id=payload.get("tenant_id"),
            tenant_domain=payload.get("tenant_domain"),
            profile_id=payload.get("profile_id"),
            public_profile=payload.get("public_profile"),
            tenant_profile=payload.get("tenant_profile"),
        )


@dataclass(frozen=True)
class PublicationTenantSummaryResult:
    source: PublicationTenantSummarySource | dict[str, Any] | None
    resolution_status: dict[str, JsonValue]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source is None:
            normalized_source = None
        elif isinstance(self.source, PublicationTenantSummarySource):
            normalized_source = self.source
        elif isinstance(self.source, dict):
            normalized_source = PublicationTenantSummarySource.from_dict(self.source)
        else:
            raise ValueError(
                "publication_tenant_summary_result.source must be PublicationTenantSummarySource, dict, or None"
            )
        object.__setattr__(self, "source", normalized_source)
        object.__setattr__(
            self,
            "resolution_status",
            _normalize_json_value(
                self.resolution_status,
                field_name="publication_tenant_summary_result.resolution_status",
            ),
        )
        object.__setattr__(self, "warnings", tuple(_as_text(item) for item in self.warnings if _as_text(item)))

    @property
    def found(self) -> bool:
        return self.source is not None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "found": self.found,
            "source": None if self.source is None else self.source.to_dict(),
            "resolution_status": self.resolution_status,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicationTenantSummaryResult":
        if not isinstance(payload, dict):
            raise ValueError("publication_tenant_summary_result must be a dict")
        warnings = payload.get("warnings") or ()
        if not isinstance(warnings, (list, tuple)):
            raise ValueError("publication_tenant_summary_result.warnings must be a list")
        return cls(
            source=payload.get("source"),
            resolution_status=payload.get("resolution_status") or {},
            warnings=tuple(str(item) for item in warnings),
        )


@dataclass(frozen=True)
class PublicationProfileBasicsWriteRequest:
    tenant_id: str
    tenant_domain: str
    profile_title: str
    profile_summary: str = ""
    contact_email: str = ""
    public_website_url: str = ""

    def __post_init__(self) -> None:
        tenant_id = _as_text(self.tenant_id).lower()
        tenant_domain = _as_text(self.tenant_domain).lower()
        profile_title = _as_text(self.profile_title)
        if not tenant_id:
            raise ValueError("publication_profile_basics_write_request.tenant_id is required")
        if not tenant_domain or "." not in tenant_domain:
            raise ValueError(
                "publication_profile_basics_write_request.tenant_domain must be a domain-like value"
            )
        if not profile_title:
            raise ValueError("publication_profile_basics_write_request.profile_title is required")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "tenant_domain", tenant_domain)
        object.__setattr__(self, "profile_title", profile_title)
        object.__setattr__(self, "profile_summary", _as_text(self.profile_summary))
        object.__setattr__(self, "contact_email", _as_text(self.contact_email).lower())
        object.__setattr__(self, "public_website_url", _as_text(self.public_website_url))

    def to_dict(self) -> dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "tenant_domain": self.tenant_domain,
            "profile_title": self.profile_title,
            "profile_summary": self.profile_summary,
            "contact_email": self.contact_email,
            "public_website_url": self.public_website_url,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicationProfileBasicsWriteRequest":
        if not isinstance(payload, dict):
            raise ValueError("publication_profile_basics_write_request must be a dict")
        return cls(
            tenant_id=payload.get("tenant_id"),
            tenant_domain=payload.get("tenant_domain"),
            profile_title=payload.get("profile_title"),
            profile_summary=payload.get("profile_summary") or "",
            contact_email=payload.get("contact_email") or "",
            public_website_url=payload.get("public_website_url") or "",
        )


@dataclass(frozen=True)
class PublicationProfileBasicsWriteResult:
    source: PublicationTenantSummarySource | dict[str, Any]
    resolution_status: dict[str, JsonValue]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized_source = (
            self.source
            if isinstance(self.source, PublicationTenantSummarySource)
            else PublicationTenantSummarySource.from_dict(self.source)
        )
        object.__setattr__(self, "source", normalized_source)
        object.__setattr__(
            self,
            "resolution_status",
            _normalize_json_value(
                self.resolution_status,
                field_name="publication_profile_basics_write_result.resolution_status",
            ),
        )
        object.__setattr__(self, "warnings", tuple(_as_text(item) for item in self.warnings if _as_text(item)))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "source": self.source.to_dict(),
            "resolution_status": self.resolution_status,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicationProfileBasicsWriteResult":
        if not isinstance(payload, dict):
            raise ValueError("publication_profile_basics_write_result must be a dict")
        warnings = payload.get("warnings") or ()
        if not isinstance(warnings, (list, tuple)):
            raise ValueError("publication_profile_basics_write_result.warnings must be a list")
        return cls(
            source=payload.get("source"),
            resolution_status=payload.get("resolution_status") or {},
            warnings=tuple(str(item) for item in warnings),
        )


@runtime_checkable
class SystemDatumStorePort(Protocol):
    def read_system_resource_workbench(self, request: SystemDatumStoreRequest) -> SystemDatumWorkbenchResult:
        """Read the canonical system datum workbench surface without legacy fallbacks."""


@runtime_checkable
class PublicationTenantSummaryPort(Protocol):
    def read_publication_tenant_summary(
        self,
        request: PublicationTenantSummaryRequest,
    ) -> PublicationTenantSummaryResult:
        """Read one publication-backed tenant profile projection without writes."""


@runtime_checkable
class PublicationProfileBasicsWritePort(Protocol):
    def write_publication_profile_basics(
        self,
        request: PublicationProfileBasicsWriteRequest,
    ) -> PublicationProfileBasicsWriteResult:
        """Apply one bounded publication-backed profile basics write with read-after-write confirmation."""
