from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a non-negative integer") from None
    if number < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return number


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


def _normalize_record(value: object, *, field_name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict")
    normalized = _normalize_json_value(value, field_name=field_name)
    if not isinstance(normalized, dict) or not normalized:
        raise ValueError(f"{field_name} must be a non-empty dict")
    return normalized


@dataclass(frozen=True)
class AuditLogAppendRequest:
    record: dict[str, JsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "record",
            _normalize_record(self.record, field_name="audit_log_append.record"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "record": dict(self.record),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditLogAppendRequest":
        if not isinstance(payload, dict):
            raise ValueError("audit_log_append must be a dict")
        return cls(record=payload.get("record"))


@dataclass(frozen=True)
class AuditLogAppendReceipt:
    record_id: str
    recorded_at_unix_ms: int

    def __post_init__(self) -> None:
        token = _as_text(self.record_id)
        if not token:
            raise ValueError("audit_log_append_receipt.record_id is required")
        object.__setattr__(self, "record_id", token)
        object.__setattr__(
            self,
            "recorded_at_unix_ms",
            _normalize_non_negative_int(
                self.recorded_at_unix_ms,
                field_name="audit_log_append_receipt.recorded_at_unix_ms",
            ),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "record_id": self.record_id,
            "recorded_at_unix_ms": self.recorded_at_unix_ms,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditLogAppendReceipt":
        if not isinstance(payload, dict):
            raise ValueError("audit_log_append_receipt must be a dict")
        return cls(
            record_id=payload.get("record_id"),
            recorded_at_unix_ms=payload.get("recorded_at_unix_ms"),
        )


@dataclass(frozen=True)
class AuditLogReadRequest:
    record_id: str

    def __post_init__(self) -> None:
        token = _as_text(self.record_id)
        if not token:
            raise ValueError("audit_log_read.record_id is required")
        object.__setattr__(self, "record_id", token)

    def to_dict(self) -> dict[str, str]:
        return {
            "record_id": self.record_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditLogReadRequest":
        if not isinstance(payload, dict):
            raise ValueError("audit_log_read must be a dict")
        return cls(record_id=payload.get("record_id"))


@dataclass(frozen=True)
class AuditLogRecord:
    record_id: str
    recorded_at_unix_ms: int
    record: dict[str, JsonValue]

    def __post_init__(self) -> None:
        token = _as_text(self.record_id)
        if not token:
            raise ValueError("audit_log_record.record_id is required")
        object.__setattr__(self, "record_id", token)
        object.__setattr__(
            self,
            "recorded_at_unix_ms",
            _normalize_non_negative_int(
                self.recorded_at_unix_ms,
                field_name="audit_log_record.recorded_at_unix_ms",
            ),
        )
        object.__setattr__(
            self,
            "record",
            _normalize_record(self.record, field_name="audit_log_record.record"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "record_id": self.record_id,
            "recorded_at_unix_ms": self.recorded_at_unix_ms,
            "record": dict(self.record),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditLogRecord":
        if not isinstance(payload, dict):
            raise ValueError("audit_log_record must be a dict")
        return cls(
            record_id=payload.get("record_id"),
            recorded_at_unix_ms=payload.get("recorded_at_unix_ms"),
            record=payload.get("record"),
        )


@dataclass(frozen=True)
class AuditLogReadResult:
    record: AuditLogRecord | None

    def __post_init__(self) -> None:
        if self.record is None:
            return
        if isinstance(self.record, AuditLogRecord):
            return
        if isinstance(self.record, dict):
            object.__setattr__(self, "record", AuditLogRecord.from_dict(self.record))
            return
        raise ValueError("audit_log_read_result.record must be an AuditLogRecord, dict, or None")

    @property
    def found(self) -> bool:
        return self.record is not None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "found": self.found,
            "record": None if self.record is None else self.record.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditLogReadResult":
        if not isinstance(payload, dict):
            raise ValueError("audit_log_read_result must be a dict")
        return cls(record=payload.get("record"))


@runtime_checkable
class AuditLogPort(Protocol):
    def append_audit_record(self, request: AuditLogAppendRequest) -> AuditLogAppendReceipt:
        """Persist one already-normalized audit record."""

    def read_audit_record(self, request: AuditLogReadRequest) -> AuditLogReadResult:
        """Read one previously persisted audit record by opaque identifier."""
