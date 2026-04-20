from __future__ import annotations

import json
from contextlib import contextmanager
import time
import uuid
from pathlib import Path
from typing import Callable

from MyCiteV2.packages.ports.audit_log import (
    AuditLogAppendReceipt,
    AuditLogAppendRequest,
    AuditLogPort,
    AuditLogRecentWindowRequest,
    AuditLogRecentWindowResult,
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
        self._lock_file = self._storage_file.with_suffix(self._storage_file.suffix + ".lock")
        self._clock = clock or (lambda: int(time.time() * 1000))
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)

    @contextmanager
    def _append_lock(self):
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_file.open("a+", encoding="utf-8") as lock_handle:
            try:
                import fcntl  # type: ignore
            except Exception:
                yield
                return
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                try:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass

    def _iter_tail_lines(self, *, chunk_size: int = 4096):
        with self._storage_file.open("rb") as handle:
            handle.seek(0, 2)
            position = handle.tell()
            buffer = b""
            while position > 0:
                read_size = min(chunk_size, position)
                position -= read_size
                handle.seek(position)
                chunk = handle.read(read_size)
                pieces = (chunk + buffer).split(b"\n")
                buffer = pieces[0]
                for line in reversed(pieces[1:]):
                    yield line
            yield buffer

    def append_audit_record(self, request: AuditLogAppendRequest) -> AuditLogAppendReceipt:
        normalized_request = request if isinstance(request, AuditLogAppendRequest) else AuditLogAppendRequest.from_dict(request)
        record = AuditLogRecord(
            record_id=self._id_factory(),
            recorded_at_unix_ms=self._clock(),
            record=normalized_request.record,
        )
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        with self._append_lock():
            with self._storage_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.to_dict(), separators=(",", ":")) + "\n")
                handle.flush()
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

    def read_recent_audit_records(
        self,
        request: AuditLogRecentWindowRequest,
    ) -> AuditLogRecentWindowResult:
        normalized_request = (
            request
            if isinstance(request, AuditLogRecentWindowRequest)
            else AuditLogRecentWindowRequest.from_dict(request)
        )
        if not self._storage_file.exists() or not self._storage_file.is_file():
            return AuditLogRecentWindowResult(records=())

        records: list[AuditLogRecord] = []
        for raw_line in self._iter_tail_lines():
            token = raw_line.strip()
            if not token:
                continue
            try:
                payload = json.loads(token.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                record = AuditLogRecord.from_dict(payload)
            except ValueError:
                continue
            records.append(record)
            if len(records) >= normalized_request.limit:
                break

        return AuditLogRecentWindowResult(records=tuple(records))
