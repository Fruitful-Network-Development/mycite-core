from __future__ import annotations

import json
from pathlib import Path

from MyCiteV2.packages.ports.aws_narrow_write import (
    AwsNarrowWritePort,
    AwsNarrowWriteRequest,
    AwsNarrowWriteResult,
    AwsNarrowWriteSource,
)


class FilesystemAwsNarrowWriteAdapter(AwsNarrowWritePort):
    def __init__(self, storage_file: str | Path) -> None:
        self._storage_file = Path(storage_file)

    def apply_aws_narrow_write(self, request: AwsNarrowWriteRequest) -> AwsNarrowWriteResult:
        normalized_request = (
            request if isinstance(request, AwsNarrowWriteRequest) else AwsNarrowWriteRequest.from_dict(request)
        )
        if not self._storage_file.exists() or not self._storage_file.is_file():
            raise ValueError("filesystem aws narrow write requires an existing status snapshot file")

        payload = json.loads(self._storage_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("filesystem aws narrow write payload must be a dict")

        payload_scope_id = str(payload.get("tenant_scope_id") or "").strip()
        if payload_scope_id and payload_scope_id != normalized_request.tenant_scope_id:
            raise ValueError("filesystem aws narrow write tenant_scope_id does not match the stored snapshot")

        profile = payload.get("canonical_newsletter_profile")
        if not isinstance(profile, dict):
            raise ValueError("filesystem aws narrow write payload is missing canonical_newsletter_profile")
        current_profile_id = str(profile.get("profile_id") or "").strip()
        if current_profile_id != normalized_request.profile_id:
            raise ValueError("filesystem aws narrow write profile_id does not match the stored snapshot")

        payload["selected_verified_sender"] = normalized_request.selected_verified_sender
        profile["selected_verified_sender"] = normalized_request.selected_verified_sender
        payload["canonical_newsletter_profile"] = profile

        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._storage_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        confirmed_payload = json.loads(self._storage_file.read_text(encoding="utf-8"))
        return AwsNarrowWriteResult(source=AwsNarrowWriteSource(payload=confirmed_payload))
