"""Filesystem-backed AWS-CSM tool profile store and registry."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem.live_aws_profile import LIVE_AWS_PROFILE_SCHEMA
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingProfileStorePort
from MyCiteV2.packages.ports.aws_csm_profile_registry import AwsCsmProfileRegistryPort


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


class FilesystemAwsCsmToolProfileStore(
    AwsCsmProfileRegistryPort,
    AwsCsmOnboardingProfileStorePort,
):
    def __init__(self, tool_root: str | Path) -> None:
        self._tool_root = Path(tool_root)

    def list_profiles(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self._tool_root.glob("aws-csm.*.json")):
            payload = self._read_profile_file(path, allow_missing=False)
            if payload is None:
                continue
            rows.append(payload)
        return [deepcopy(row) for row in rows]

    def resolve_domain_seed(self, *, domain: str) -> dict[str, Any] | None:
        token = _as_text(domain).lower()
        if not token:
            return None
        for profile in self.list_profiles():
            identity = _as_dict(profile.get("identity"))
            if _as_text(identity.get("domain")).lower() != token:
                continue
            tenant_id = _as_text(identity.get("tenant_id")).lower()
            if not tenant_id:
                continue
            provider = _as_dict(profile.get("provider"))
            return {
                "tenant_id": tenant_id,
                "region": _as_text(identity.get("region")) or "us-east-1",
                "provider": {
                    "aws_ses_identity_status": _as_text(provider.get("aws_ses_identity_status")),
                    "last_checked_at": _as_text(provider.get("last_checked_at")),
                },
                "profile_id": _as_text(identity.get("profile_id")),
            }
        return None

    def create_profile(self, *, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile_token = _as_text(profile_id)
        if not profile_token:
            raise ValueError("profile_id is required")
        if _as_text(payload.get("schema")) != LIVE_AWS_PROFILE_SCHEMA:
            raise ValueError("profile schema must remain mycite.service_tool.aws_csm.profile.v1")
        profile_path = self._tool_root / f"{profile_token}.json"
        if profile_path.exists():
            raise ValueError(f"AWS-CSM profile already exists: {profile_token}")
        collection_path = self._collection_path()
        collection_payload = self._read_collection_payload(collection_path)
        member_files = [
            _as_text(item)
            for item in list(collection_payload.get("member_files") or [])
            if _as_text(item)
        ]
        filename = profile_path.name
        if filename in member_files:
            raise ValueError(f"AWS-CSM collection already references {filename}")
        updated_collection = dict(collection_payload)
        updated_collection["member_files"] = list(member_files) + [filename]

        original_collection = collection_path.read_text(encoding="utf-8")
        self._tool_root.mkdir(parents=True, exist_ok=True)
        try:
            self._write_json_atomic(profile_path, payload)
            self._write_json_atomic(collection_path, updated_collection)
        except Exception:
            if profile_path.exists():
                profile_path.unlink()
            collection_path.write_text(original_collection, encoding="utf-8")
            raise
        reloaded = self._read_profile_file(profile_path, allow_missing=False)
        if reloaded is None:
            raise ValueError("read-after-write failed for AWS-CSM tool profile creation")
        return reloaded

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict[str, Any] | None:
        path = self._tool_root / f"{_as_text(profile_id)}.json"
        payload = self._read_profile_file(path, allow_missing=True)
        if payload is None:
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
        path = self._tool_root / f"{_as_text(profile_id)}.json"
        self._tool_root.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(path, payload)
        reloaded = self.load_profile(tenant_scope_id=tenant_scope_id, profile_id=profile_id)
        if reloaded is None:
            raise ValueError("read-after-write failed for AWS-CSM tool profile store")
        return reloaded

    def _collection_path(self) -> Path:
        for candidate in sorted(self._tool_root.glob("tool.*.aws-csm.json")):
            return candidate
        raise ValueError("AWS-CSM collection file is missing from the tool root")

    def _read_collection_payload(self, path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("AWS-CSM collection payload must be a dict")
        return payload

    def _read_profile_file(self, path: Path, *, allow_missing: bool) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            if allow_missing:
                return None
            raise ValueError(f"AWS-CSM profile file is missing: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("AWS-CSM profile payload must be a dict")
        if _as_text(payload.get("schema")) != LIVE_AWS_PROFILE_SCHEMA:
            return None
        return payload

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)


__all__ = ["FilesystemAwsCsmToolProfileStore"]
