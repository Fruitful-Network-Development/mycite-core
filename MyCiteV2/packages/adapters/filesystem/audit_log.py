from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Callable

from MyCiteV2.packages.ports.audit_log import (
    AuditLogAppendReceipt,
    AuditLogAppendRequest,
    AuditLogPort,
    AuditLogReadRequest,
    AuditLogReadResult,
    AuditLogRecord,
)


class FilesystemAuditLogAdapter(AuditLogPort):
    def __init__(
        self,
        storage_file: str | Path,
        *,
        clock: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._storage_file = Path(storage_file)
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)

    def append_audit_record(self, request: AuditLogAppendRequest) -> AuditLogAppendReceipt:
        normalized_request = request if isinstance(request, AuditLogAppendRequest) else AuditLogAppendRequest.from_dict(request)
        record = AuditLogRecord(
            record_id=self._id_factory(),
            recorded_at_unix_ms=self._clock(),
            record=normalized_request.record,
        )
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        with self._storage_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), separators=(",", ":")) + "\n")
        return AuditLogAppendReceipt(
            record_id=record.record_id,
            recorded_at_unix_ms=record.recorded_at_unix_ms,
        )

    def read_audit_record(self, request: AuditLogReadRequest) -> AuditLogReadResult:
        normalized_request = request if isinstance(request, AuditLogReadRequest) else AuditLogReadRequest.from_dict(request)
        if not self._storage_file.exists() or not self._storage_file.is_file():
            return AuditLogReadResult(record=None)

        with self._storage_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                token = line.strip()
                if not token:
                    continue
                try:
                    payload = json.loads(token)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                if payload.get("record_id") != normalized_request.record_id:
                    continue
                return AuditLogReadResult(record=AuditLogRecord.from_dict(payload))

        return AuditLogReadResult(record=None)
