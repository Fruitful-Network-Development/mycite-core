"""Filesystem-backed profile store for AWS-CSM onboarding writes."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem.live_aws_profile import LIVE_AWS_PROFILE_SCHEMA
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingProfileStorePort


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _matches_tenant_scope(payload: dict[str, Any], tenant_scope_id: str) -> bool:
    identity = _as_dict(payload.get("identity"))
    requested = _as_text(tenant_scope_id).lower()
    allowed = {
        _as_text(identity.get("tenant_id")).lower(),
        _as_text(identity.get("domain")).lower(),
        _as_text(identity.get("profile_id")).lower(),
    }
    return bool(requested and requested in allowed)


class FilesystemAwsCsmOnboardingProfileStore(AwsCsmOnboardingProfileStorePort):
    """Trusted-tenant canonical live profile path (same artifact as Band 1/2)."""

    def __init__(self, storage_file: str | Path) -> None:
        self._storage_file = Path(storage_file)

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict[str, Any] | None:
        if not self._storage_file.exists() or not self._storage_file.is_file():
            return None
        payload = json.loads(self._storage_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("live aws profile payload must be a dict")
        if _as_text(payload.get("schema")) != LIVE_AWS_PROFILE_SCHEMA:
            return None
        if not _matches_tenant_scope(payload, tenant_scope_id):
            return None
        identity = _as_dict(payload.get("identity"))
        if _as_text(identity.get("profile_id")) != _as_text(profile_id):
            return None
        return deepcopy(payload)

    def save_profile(self, *, tenant_scope_id: str, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("profile payload must be a dict")
        if _as_text(payload.get("schema")) != LIVE_AWS_PROFILE_SCHEMA:
            raise ValueError("profile schema must remain mycite.service_tool.aws_csm.profile.v1")
        if not _matches_tenant_scope(payload, tenant_scope_id):
            raise ValueError("profile tenant_scope_id does not match stored identity")
        identity = _as_dict(payload.get("identity"))
        if _as_text(identity.get("profile_id")) != _as_text(profile_id):
            raise ValueError("profile_id does not match stored identity")
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._storage_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        reloaded = self.load_profile(tenant_scope_id=tenant_scope_id, profile_id=profile_id)
        if reloaded is None:
            raise ValueError("read-after-write failed for onboarding profile store")
        return reloaded


__all__ = ["FilesystemAwsCsmOnboardingProfileStore"]
