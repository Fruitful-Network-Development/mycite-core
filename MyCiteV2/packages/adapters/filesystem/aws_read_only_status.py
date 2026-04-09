from __future__ import annotations

import json
from pathlib import Path

from MyCiteV2.packages.ports.aws_read_only_status import (
    AwsReadOnlyStatusPort,
    AwsReadOnlyStatusRequest,
    AwsReadOnlyStatusResult,
    AwsReadOnlyStatusSource,
)


class FilesystemAwsReadOnlyStatusAdapter(AwsReadOnlyStatusPort):
    def __init__(self, storage_file: str | Path) -> None:
        self._storage_file = Path(storage_file)

    def read_aws_read_only_status(self, request: AwsReadOnlyStatusRequest) -> AwsReadOnlyStatusResult:
        normalized_request = (
            request if isinstance(request, AwsReadOnlyStatusRequest) else AwsReadOnlyStatusRequest.from_dict(request)
        )
        if not self._storage_file.exists() or not self._storage_file.is_file():
            return AwsReadOnlyStatusResult(source=None)

        payload = json.loads(self._storage_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("filesystem aws read-only status payload must be a dict")

        source = AwsReadOnlyStatusSource(payload=payload)
        payload_scope_id = str(source.payload.get("tenant_scope_id") or "").strip()
        if payload_scope_id and payload_scope_id != normalized_request.tenant_scope_id:
            return AwsReadOnlyStatusResult(source=None)

        return AwsReadOnlyStatusResult(source=source)
