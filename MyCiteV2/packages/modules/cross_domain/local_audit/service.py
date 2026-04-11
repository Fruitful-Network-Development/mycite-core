from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from MyCiteV2.packages.core.datum_refs import normalize_datum_ref
from MyCiteV2.packages.ports.audit_log import (
    AUDIT_LOG_RECENT_WINDOW_LIMIT,
    AuditLogAppendReceipt,
    AuditLogAppendRequest,
    AuditLogPort,
    AuditLogRecentWindowRequest,
    AuditLogRecentWindowResult,
    AuditLogReadRequest,
    AuditLogRecord,
)

FORBIDDEN_LOCAL_AUDIT_KEYS = frozenset(
    {
        "private_key",
        "private_key_pem",
        "secret",
        "token",
        "password",
        "symmetric_key",
        "hmac_key",
        "hmac_key_b64",
        "api_key",
    }
)

_ALLOWED_LOCAL_AUDIT_FIELDS = frozenset({"event_type", "focus_subject", "shell_verb", "details"})
_LOCAL_AUDIT_HEALTH_STATES = frozenset(
    {
        "not_configured",
        "unavailable",
        "no_recent_persistence_evidence",
        "recent_persistence_observed",
    }
)
_LOCAL_AUDIT_STORAGE_STATES = frozenset(
    {
        "not_configured",
        "missing_or_empty",
        "present",
        "unreadable",
    }
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_json_value(value: Any, *, field_name: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_json_value(item, field_name=f"{field_name}[]") for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            token = _as_text(key)
            if not token:
                raise ValueError(f"{field_name} keys must be non-empty strings")
            lowered = token.lower()
            if lowered in FORBIDDEN_LOCAL_AUDIT_KEYS:
                raise ValueError(f"{field_name}.{token} is forbidden in local audit")
            out[token] = _normalize_json_value(item, field_name=f"{field_name}.{token}")
        return out
    raise ValueError(f"{field_name} must be JSON-serializable data")


@dataclass(frozen=True)
class LocalAuditRecord:
    event_type: str
    focus_subject: str
    shell_verb: str
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        event_type = _as_text(self.event_type).lower()
        if not event_type:
            raise ValueError("local_audit.event_type is required")

        shell_verb = _as_text(self.shell_verb).lower()
        if not shell_verb:
            raise ValueError("local_audit.shell_verb is required")

        focus_subject = normalize_datum_ref(
            self.focus_subject,
            require_qualified=True,
            write_format="dot",
            field_name="local_audit.focus_subject",
        )

        details = self.details if self.details is not None else {}
        if not isinstance(details, dict):
            raise ValueError("local_audit.details must be a dict")
        normalized_details = _normalize_json_value(details, field_name="local_audit.details")
        if not isinstance(normalized_details, dict):
            raise ValueError("local_audit.details must be a dict")

        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "shell_verb", shell_verb)
        object.__setattr__(self, "focus_subject", focus_subject)
        object.__setattr__(self, "details", normalized_details)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "focus_subject": self.focus_subject,
            "shell_verb": self.shell_verb,
            "details": dict(self.details or {}),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LocalAuditRecord":
        if not isinstance(payload, dict):
            raise ValueError("local_audit must be a dict")
        extra_fields = sorted(set(payload.keys()) - _ALLOWED_LOCAL_AUDIT_FIELDS)
        if extra_fields:
            raise ValueError(f"local_audit has unsupported fields: {extra_fields}")
        return cls(
            event_type=payload.get("event_type"),
            focus_subject=payload.get("focus_subject"),
            shell_verb=payload.get("shell_verb"),
            details=payload.get("details") or {},
        )


@dataclass(frozen=True)
class StoredLocalAuditRecord:
    record_id: str
    recorded_at_unix_ms: int
    record: LocalAuditRecord

    def __post_init__(self) -> None:
        if not _as_text(self.record_id):
            raise ValueError("stored_local_audit.record_id is required")
        if isinstance(self.record, LocalAuditRecord):
            normalized_record = self.record
        elif isinstance(self.record, dict):
            normalized_record = LocalAuditRecord.from_dict(self.record)
        else:
            raise ValueError("stored_local_audit.record must be a LocalAuditRecord or dict")
        object.__setattr__(self, "record_id", _as_text(self.record_id))
        object.__setattr__(self, "recorded_at_unix_ms", int(self.recorded_at_unix_ms))
        object.__setattr__(self, "record", normalized_record)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "recorded_at_unix_ms": self.recorded_at_unix_ms,
            "record": self.record.to_dict(),
        }


@dataclass(frozen=True)
class LocalAuditOperationalStatusSummary:
    health_state: str
    storage_state: str
    recent_window_limit: int = AUDIT_LOG_RECENT_WINDOW_LIMIT
    recent_record_count: int = 0
    latest_recorded_at_unix_ms: int | None = None

    def __post_init__(self) -> None:
        health_state = _as_text(self.health_state).lower()
        storage_state = _as_text(self.storage_state).lower()
        if health_state not in _LOCAL_AUDIT_HEALTH_STATES:
            raise ValueError("local_audit_operational_status.health_state is invalid")
        if storage_state not in _LOCAL_AUDIT_STORAGE_STATES:
            raise ValueError("local_audit_operational_status.storage_state is invalid")
        if int(self.recent_window_limit) != AUDIT_LOG_RECENT_WINDOW_LIMIT:
            raise ValueError(
                "local_audit_operational_status.recent_window_limit must be "
                f"{AUDIT_LOG_RECENT_WINDOW_LIMIT}"
            )
        recent_record_count = int(self.recent_record_count)
        if recent_record_count < 0:
            raise ValueError("local_audit_operational_status.recent_record_count must be non-negative")
        latest_recorded_at_unix_ms = (
            None
            if self.latest_recorded_at_unix_ms is None
            else int(self.latest_recorded_at_unix_ms)
        )
        if latest_recorded_at_unix_ms is not None and latest_recorded_at_unix_ms < 0:
            raise ValueError(
                "local_audit_operational_status.latest_recorded_at_unix_ms must be non-negative"
            )
        if recent_record_count == 0 and latest_recorded_at_unix_ms is not None:
            raise ValueError(
                "local_audit_operational_status.latest_recorded_at_unix_ms requires recent records"
            )
        object.__setattr__(self, "health_state", health_state)
        object.__setattr__(self, "storage_state", storage_state)
        object.__setattr__(self, "recent_window_limit", AUDIT_LOG_RECENT_WINDOW_LIMIT)
        object.__setattr__(self, "recent_record_count", recent_record_count)
        object.__setattr__(self, "latest_recorded_at_unix_ms", latest_recorded_at_unix_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_state": self.health_state,
            "storage_state": self.storage_state,
            "recent_window_limit": self.recent_window_limit,
            "recent_record_count": self.recent_record_count,
            "latest_recorded_at_unix_ms": self.latest_recorded_at_unix_ms,
        }


def normalize_local_audit_record(payload: LocalAuditRecord | dict[str, Any]) -> LocalAuditRecord:
    if isinstance(payload, LocalAuditRecord):
        return payload
    return LocalAuditRecord.from_dict(payload)


class LocalAuditService:
    def __init__(self, audit_log_port: AuditLogPort | None) -> None:
        self._audit_log_port = audit_log_port

    def _require_port(self) -> AuditLogPort:
        if self._audit_log_port is None:
            raise ValueError("local_audit.audit_log_port is not configured")
        return self._audit_log_port

    def read_operational_status_summary(self) -> LocalAuditOperationalStatusSummary:
        if self._audit_log_port is None:
            return LocalAuditOperationalStatusSummary(
                health_state="not_configured",
                storage_state="not_configured",
            )

        try:
            recent = self._audit_log_port.read_recent_audit_records(AuditLogRecentWindowRequest())
        except (OSError, UnicodeDecodeError):
            return LocalAuditOperationalStatusSummary(
                health_state="unavailable",
                storage_state="unreadable",
            )
        normalized_recent = (
            recent
            if isinstance(recent, AuditLogRecentWindowResult)
            else AuditLogRecentWindowResult.from_dict(recent)
        )
        if normalized_recent.record_count == 0:
            return LocalAuditOperationalStatusSummary(
                health_state="no_recent_persistence_evidence",
                storage_state="missing_or_empty",
            )
        latest_recorded_at_unix_ms = max(
            record.recorded_at_unix_ms
            for record in normalized_recent.records
        )
        return LocalAuditOperationalStatusSummary(
            health_state="recent_persistence_observed",
            storage_state="present",
            recent_record_count=normalized_recent.record_count,
            latest_recorded_at_unix_ms=latest_recorded_at_unix_ms,
        )

    def append_record(self, payload: LocalAuditRecord | dict[str, Any]) -> AuditLogAppendReceipt:
        normalized = normalize_local_audit_record(payload)
        request = AuditLogAppendRequest(record=normalized.to_dict())
        return self._require_port().append_audit_record(request)

    def read_record(self, record_id: object) -> StoredLocalAuditRecord | None:
        request = AuditLogReadRequest(record_id=_as_text(record_id))
        result = self._require_port().read_audit_record(request)
        if result.record is None:
            return None
        stored = result.record if isinstance(result.record, AuditLogRecord) else AuditLogRecord.from_dict(result.record)
        return StoredLocalAuditRecord(
            record_id=stored.record_id,
            recorded_at_unix_ms=stored.recorded_at_unix_ms,
            record=normalize_local_audit_record(stored.record),
        )
