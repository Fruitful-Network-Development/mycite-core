from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_ALLOWED_VIEWS = frozenset({"overview", "pages", "collections", "issues"})


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


def _normalize_identifier(value: object, *, field_name: str) -> str:
    token = _as_text(value)
    if not token:
        return ""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in token):
        raise ValueError(f"{field_name} must use letters, numbers, dots, dashes, or underscores")
    return token


def _normalize_view(value: object, *, field_name: str) -> str:
    token = _as_text(value).lower()
    if not token:
        return "overview"
    if token not in _ALLOWED_VIEWS:
        raise ValueError(f"{field_name} must be one of {sorted(_ALLOWED_VIEWS)}")
    return token


@dataclass(frozen=True)
class FndDcmReadOnlyRequest:
    portal_tenant_id: str
    site: str = ""
    view: str = "overview"
    page: str = ""
    collection: str = ""

    def __post_init__(self) -> None:
        portal_tenant_id = _as_text(self.portal_tenant_id).lower()
        if not portal_tenant_id:
            raise ValueError("fnd_dcm_read_only_request.portal_tenant_id is required")
        object.__setattr__(self, "portal_tenant_id", portal_tenant_id)
        object.__setattr__(
            self,
            "site",
            _normalize_optional_domain(self.site, field_name="fnd_dcm_read_only_request.site"),
        )
        object.__setattr__(
            self,
            "view",
            _normalize_view(self.view, field_name="fnd_dcm_read_only_request.view"),
        )
        object.__setattr__(
            self,
            "page",
            _normalize_identifier(self.page, field_name="fnd_dcm_read_only_request.page"),
        )
        object.__setattr__(
            self,
            "collection",
            _normalize_identifier(self.collection, field_name="fnd_dcm_read_only_request.collection"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "portal_tenant_id": self.portal_tenant_id,
            "site": self.site,
            "view": self.view,
            "page": self.page,
            "collection": self.collection,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FndDcmReadOnlyRequest":
        if not isinstance(payload, dict):
            raise ValueError("fnd_dcm_read_only_request must be a dict")
        return cls(
            portal_tenant_id=payload.get("portal_tenant_id"),
            site=payload.get("site") or "",
            view=payload.get("view") or "overview",
            page=payload.get("page") or "",
            collection=payload.get("collection") or "",
        )


@dataclass(frozen=True)
class FndDcmReadOnlySource:
    payload: dict[str, JsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            _normalize_payload(self.payload, field_name="fnd_dcm_read_only_source.payload"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {"payload": dict(self.payload)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FndDcmReadOnlySource":
        if not isinstance(payload, dict):
            raise ValueError("fnd_dcm_read_only_source must be a dict")
        return cls(payload=payload.get("payload"))


@dataclass(frozen=True)
class FndDcmReadOnlyResult:
    source: FndDcmReadOnlySource | None

    def __post_init__(self) -> None:
        if self.source is None:
            return
        if isinstance(self.source, FndDcmReadOnlySource):
            return
        if isinstance(self.source, dict):
            object.__setattr__(self, "source", FndDcmReadOnlySource.from_dict(self.source))
            return
        raise ValueError("fnd_dcm_read_only_result.source must be FndDcmReadOnlySource, dict, or None")

    @property
    def found(self) -> bool:
        return self.source is not None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "found": self.found,
            "source": None if self.source is None else self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FndDcmReadOnlyResult":
        if not isinstance(payload, dict):
            raise ValueError("fnd_dcm_read_only_result must be a dict")
        return cls(source=payload.get("source"))


@runtime_checkable
class FndDcmReadOnlyPort(Protocol):
    def read_fnd_dcm_read_only(self, request: FndDcmReadOnlyRequest) -> FndDcmReadOnlyResult:
        """Read hosted manifest profiles and normalized projections without writes."""
