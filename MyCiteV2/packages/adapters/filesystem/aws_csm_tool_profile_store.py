"""Filesystem-backed AWS-CSM tool profile store and registry."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem.live_aws_profile import LIVE_AWS_PROFILE_SCHEMA
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingProfileStorePort
from MyCiteV2.packages.ports.aws_csm_profile_registry import AwsCsmProfileRegistryPort

AWS_CSM_DOMAIN_SCHEMA = "mycite.service_tool.aws_csm.domain.v1"


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


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


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

    def list_domains(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self._tool_root.glob("aws-csm-domain.*.json")):
            payload = self._read_domain_file(path, allow_missing=False)
            if payload is None:
                continue
            rows.append(payload)
        return [deepcopy(row) for row in rows]

    def resolve_domain_seed(self, *, domain: str) -> dict[str, Any] | None:
        token = _normalized_domain(domain)
        if not token:
            return None
        for domain_record in self.list_domains():
            identity = _as_dict(domain_record.get("identity"))
            if _normalized_domain(identity.get("domain")) != token:
                continue
            tenant_id = _as_text(identity.get("tenant_id")).lower()
            if not tenant_id:
                continue
            ses = _as_dict(domain_record.get("ses"))
            observation = _as_dict(domain_record.get("observation"))
            return {
                "tenant_id": tenant_id,
                "region": _as_text(identity.get("region")) or "us-east-1",
                "provider": {
                    "aws_ses_identity_status": _as_text(ses.get("identity_status")),
                    "last_checked_at": _as_text(observation.get("last_checked_at")),
                },
                "profile_id": _as_text(identity.get("profile_id")),
            }
        for profile in self.list_profiles():
            identity = _as_dict(profile.get("identity"))
            if _normalized_domain(identity.get("domain")) != token:
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

    def create_domain(self, *, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_token = _as_text(tenant_id).lower()
        identity = _as_dict(payload.get("identity"))
        domain = _normalized_domain(identity.get("domain"))
        payload_tenant = _as_text(identity.get("tenant_id")).lower()
        if not tenant_token:
            raise ValueError("tenant_id is required")
        if _as_text(payload.get("schema")) != AWS_CSM_DOMAIN_SCHEMA:
            raise ValueError("domain schema must remain mycite.service_tool.aws_csm.domain.v1")
        if payload_tenant != tenant_token:
            raise ValueError("domain payload tenant_id does not match create_domain tenant_id")
        if not domain:
            raise ValueError("domain payload must include identity.domain")
        if self.load_domain(domain=domain) is not None:
            raise ValueError(f"AWS-CSM domain record already exists for {domain}")
        domain_path = self._domain_path_for_tenant(tenant_token)
        if domain_path.exists():
            raise ValueError(f"AWS-CSM domain record already exists for tenant {tenant_token}")
        collection_path = self._collection_path()
        collection_payload = self._read_collection_payload(collection_path)
        member_files = [
            _as_text(item)
            for item in list(collection_payload.get("member_files") or [])
            if _as_text(item)
        ]
        filename = domain_path.name
        if filename in member_files:
            raise ValueError(f"AWS-CSM collection already references {filename}")
        updated_collection = dict(collection_payload)
        updated_collection["member_files"] = list(member_files) + [filename]

        original_collection = collection_path.read_text(encoding="utf-8")
        self._tool_root.mkdir(parents=True, exist_ok=True)
        try:
            self._write_json_atomic(domain_path, payload)
            self._write_json_atomic(collection_path, updated_collection)
        except Exception:
            if domain_path.exists():
                domain_path.unlink()
            collection_path.write_text(original_collection, encoding="utf-8")
            raise
        reloaded = self.load_domain(domain=domain)
        if reloaded is None:
            raise ValueError("read-after-write failed for AWS-CSM domain creation")
        return reloaded

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

    def load_domain(self, *, domain: str) -> dict[str, Any] | None:
        domain_token = _normalized_domain(domain)
        if not domain_token:
            return None
        for payload in self.list_domains():
            identity = _as_dict(payload.get("identity"))
            if _normalized_domain(identity.get("domain")) == domain_token:
                return deepcopy(payload)
        return None

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

    def save_domain(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("domain payload must be a dict")
        if _as_text(payload.get("schema")) != AWS_CSM_DOMAIN_SCHEMA:
            raise ValueError("domain schema must remain mycite.service_tool.aws_csm.domain.v1")
        identity = _as_dict(payload.get("identity"))
        domain_token = _normalized_domain(domain)
        payload_domain = _normalized_domain(identity.get("domain"))
        tenant_id = _as_text(identity.get("tenant_id")).lower()
        if not tenant_id:
            raise ValueError("domain payload must include identity.tenant_id")
        if payload_domain != domain_token:
            raise ValueError("domain does not match stored identity")
        path = self._domain_path_for_tenant(tenant_id)
        if not path.exists():
            raise ValueError(f"AWS-CSM domain file is missing: {path}")
        self._tool_root.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(path, payload)
        reloaded = self.load_domain(domain=domain_token)
        if reloaded is None:
            raise ValueError("read-after-write failed for AWS-CSM domain store")
        return reloaded

    def _collection_path(self) -> Path:
        for candidate in sorted(self._tool_root.glob("tool.*.aws-csm.json")):
            return candidate
        raise ValueError("AWS-CSM collection file is missing from the tool root")

    def _domain_path_for_tenant(self, tenant_id: str) -> Path:
        return self._tool_root / f"aws-csm-domain.{_as_text(tenant_id).lower()}.json"

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

    def _read_domain_file(self, path: Path, *, allow_missing: bool) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            if allow_missing:
                return None
            raise ValueError(f"AWS-CSM domain file is missing: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("AWS-CSM domain payload must be a dict")
        if _as_text(payload.get("schema")) != AWS_CSM_DOMAIN_SCHEMA:
            return None
        return payload

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_name(path.name + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(path)

__all__ = ["AWS_CSM_DOMAIN_SCHEMA", "FilesystemAwsCsmToolProfileStore"]
