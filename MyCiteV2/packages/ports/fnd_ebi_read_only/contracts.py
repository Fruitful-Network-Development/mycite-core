from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol, runtime_checkable

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_YEAR_MONTH_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}$")


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


def _normalize_payload(value: object, *, field_name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    normalized = _normalize_json_value(value, field_name=field_name)
    if not isinstance(normalized, dict) or not normalized:
        raise ValueError(f"{field_name} must be a non-empty dict")
    return normalized


def _normalize_optional_domain(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if not token:
        return ""
    if "." not in token or "/" in token or "\\" in token or ".." in token:
        raise ValueError(f"{field_name} must be a plain domain-like value")
    return token


def _normalize_optional_year_month(value: object, *, field_name: str) -> str:
    token = _as_text(value)
    if not token:
        return ""
    if not _YEAR_MONTH_PATTERN.match(token):
        raise ValueError(f"{field_name} must use YYYY-MM")
    return token


@dataclass(frozen=True)
class FndEbiReadOnlyRequest:
    portal_tenant_id: str
    selected_domain: str = ""
    year_month: str = ""

    def __post_init__(self) -> None:
        portal_tenant_id = _as_text(self.portal_tenant_id).lower()
        if not portal_tenant_id:
            raise ValueError("fnd_ebi_read_only_request.portal_tenant_id is required")
        object.__setattr__(self, "portal_tenant_id", portal_tenant_id)
        object.__setattr__(
            self,
            "selected_domain",
            _normalize_optional_domain(
                self.selected_domain,
                field_name="fnd_ebi_read_only_request.selected_domain",
            ),
        )
        object.__setattr__(
            self,
            "year_month",
            _normalize_optional_year_month(
                self.year_month,
                field_name="fnd_ebi_read_only_request.year_month",
            ),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "portal_tenant_id": self.portal_tenant_id,
            "selected_domain": self.selected_domain,
            "year_month": self.year_month,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FndEbiReadOnlyRequest":
        if not isinstance(payload, dict):
            raise ValueError("fnd_ebi_read_only_request must be a dict")
        return cls(
            portal_tenant_id=payload.get("portal_tenant_id"),
            selected_domain=payload.get("selected_domain") or "",
            year_month=payload.get("year_month") or "",
        )


@dataclass(frozen=True)
class FndEbiReadOnlySource:
    payload: dict[str, JsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            _normalize_payload(self.payload, field_name="fnd_ebi_read_only_source.payload"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {"payload": dict(self.payload)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FndEbiReadOnlySource":
        if not isinstance(payload, dict):
            raise ValueError("fnd_ebi_read_only_source must be a dict")
        return cls(payload=payload.get("payload"))


@dataclass(frozen=True)
class FndEbiReadOnlyResult:
    source: FndEbiReadOnlySource | None

    def __post_init__(self) -> None:
        if self.source is None:
            return
        if isinstance(self.source, FndEbiReadOnlySource):
            return
        if isinstance(self.source, dict):
            object.__setattr__(self, "source", FndEbiReadOnlySource.from_dict(self.source))
            return
        raise ValueError("fnd_ebi_read_only_result.source must be FndEbiReadOnlySource, dict, or None")

    @property
    def found(self) -> bool:
        return self.source is not None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "found": self.found,
            "source": None if self.source is None else self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FndEbiReadOnlyResult":
        if not isinstance(payload, dict):
            raise ValueError("fnd_ebi_read_only_result must be a dict")
        return cls(source=payload.get("source"))


@runtime_checkable
class FndEbiReadOnlyPort(Protocol):
    def read_fnd_ebi_read_only(self, request: FndEbiReadOnlyRequest) -> FndEbiReadOnlyResult:
        """Read profile-led hosted site visibility without writes."""
