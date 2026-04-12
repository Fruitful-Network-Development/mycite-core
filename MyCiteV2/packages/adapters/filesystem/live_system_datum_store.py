from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.ports.datum_store import (
    PublicationProfileBasicsWriteRequest,
    PublicationProfileBasicsWriteResult,
    PublicationTenantSummaryRequest,
    PublicationTenantSummaryResult,
    PublicationTenantSummarySource,
    SystemDatumResourceRow,
    SystemDatumStorePort,
    SystemDatumStoreRequest,
    SystemDatumWorkbenchResult,
)

LEGACY_ROOT_DATUM_FILENAMES = (
    "anthology.json",
    "samras-msn.json",
    "samras-txa.json",
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_text_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(_as_text(item) for item in value if _as_text(item))
    token = _as_text(value)
    return (token,) if token else ()


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _extract_row(resource_id: str, raw: Any) -> SystemDatumResourceRow:
    subject_ref = resource_id
    relation = ""
    object_ref = ""
    labels: tuple[str, ...] = ()

    if isinstance(raw, list) and raw:
        triple = raw[0]
        if isinstance(triple, list):
            subject_ref = _as_text(triple[0] if len(triple) > 0 else resource_id) or resource_id
            relation = _as_text(triple[1] if len(triple) > 1 else "")
            object_ref = _as_text(triple[2] if len(triple) > 2 else "")
        if len(raw) > 1:
            labels = _as_text_tuple(raw[1])
    elif isinstance(raw, dict):
        subject_ref = _as_text(raw.get("subject_ref") or raw.get("subject") or resource_id) or resource_id
        relation = _as_text(raw.get("relation") or raw.get("predicate"))
        object_ref = _as_text(raw.get("object_ref") or raw.get("object"))
        labels = _as_text_tuple(raw.get("labels") or raw.get("label") or raw.get("name"))

    return SystemDatumResourceRow(
        resource_id=resource_id,
        subject_ref=subject_ref,
        relation=relation,
        object_ref=object_ref,
        labels=labels,
        raw=raw,
    )


class FilesystemSystemDatumStoreAdapter(SystemDatumStorePort):
    def __init__(self, data_dir: str | Path, *, public_dir: str | Path | None = None) -> None:
        self._data_dir = Path(data_dir)
        self._public_dir = None if public_dir is None else Path(public_dir)

    def read_system_resource_workbench(self, request: SystemDatumStoreRequest) -> SystemDatumWorkbenchResult:
        normalized_request = (
            request if isinstance(request, SystemDatumStoreRequest) else SystemDatumStoreRequest.from_dict(request)
        )
        anthology_file = self._data_dir / "system" / "anthology.json"
        system_source_files = sorted((self._data_dir / "system" / "sources").glob("*.json"))
        payload_cache_files = sorted((self._data_dir / "payloads" / "cache").glob("*.json"))
        legacy_root_files = [self._data_dir / filename for filename in LEGACY_ROOT_DATUM_FILENAMES]
        present_legacy_root_files = [path for path in legacy_root_files if path.exists()]

        rows: list[SystemDatumResourceRow] = []
        warnings: list[str] = []
        canonical_source = "missing"

        if not anthology_file.exists() or not anthology_file.is_file():
            warnings.append("Canonical system anthology is missing at data/system/anthology.json.")
        else:
            try:
                payload = json.loads(anthology_file.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    canonical_source = "invalid"
                    warnings.append("Canonical system anthology must be a JSON object.")
                else:
                    rows = [_extract_row(key, payload[key]) for key in sorted(payload.keys())]
                    canonical_source = "loaded"
            except json.JSONDecodeError:
                canonical_source = "invalid"
                warnings.append("Canonical system anthology is not valid JSON.")

        if not system_source_files:
            warnings.append("No canonical system source JSON files were found under data/system/sources.")
        if not payload_cache_files:
            warnings.append("No derived payload cache JSON files were found under data/payloads/cache.")
        if present_legacy_root_files:
            warnings.append("Legacy root datum files exist but were ignored by the V2 native datum adapter.")

        return SystemDatumWorkbenchResult(
            tenant_id=normalized_request.tenant_id,
            rows=tuple(rows),
            source_files={
                "anthology": str(anthology_file),
                "system_sources": [str(path) for path in system_source_files],
                "payload_cache": [str(path) for path in payload_cache_files],
                "legacy_root_candidates": [str(path) for path in legacy_root_files],
                "ignored_legacy_root_files": [str(path) for path in present_legacy_root_files],
            },
            materialization_status={
                "canonical_source": canonical_source,
                "legacy_root_fallback": "blocked",
                "system_source_count": len(system_source_files),
                "payload_cache_count": len(payload_cache_files),
                "legacy_root_conflict_count": len(present_legacy_root_files),
            },
            warnings=tuple(warnings),
        )

    def read_publication_tenant_summary(
        self,
        request: PublicationTenantSummaryRequest,
    ) -> PublicationTenantSummaryResult:
        normalized_request = (
            request
            if isinstance(request, PublicationTenantSummaryRequest)
            else PublicationTenantSummaryRequest.from_dict(request)
        )
        (
            profile_id,
            public_profile,
            public_status,
            tenant_profile,
            tenant_status,
            resolution_status,
            warnings,
        ) = self._resolve_publication_profiles(
            tenant_domain=normalized_request.tenant_domain,
        )
        if not profile_id:
            return PublicationTenantSummaryResult(
                source=None,
                resolution_status=resolution_status,
                warnings=tuple(warnings),
            )
        return PublicationTenantSummaryResult(
            source=PublicationTenantSummarySource(
                tenant_id=normalized_request.tenant_id,
                tenant_domain=normalized_request.tenant_domain,
                profile_id=profile_id,
                public_profile=public_profile,
                tenant_profile=tenant_profile,
            ),
            resolution_status=resolution_status,
            warnings=tuple(warnings),
        )

    def write_publication_profile_basics(
        self,
        request: PublicationProfileBasicsWriteRequest,
    ) -> PublicationProfileBasicsWriteResult:
        normalized_request = (
            request
            if isinstance(request, PublicationProfileBasicsWriteRequest)
            else PublicationProfileBasicsWriteRequest.from_dict(request)
        )
        (
            profile_id,
            _public_profile,
            _public_status,
            tenant_profile,
            tenant_status,
            _resolution_status,
            warnings,
        ) = self._resolve_publication_profiles(
            tenant_domain=normalized_request.tenant_domain,
        )
        if not profile_id:
            raise ValueError(
                "No canonical publication profile mapping was found for the requested tenant domain."
            )
        if self._public_dir is None:
            raise ValueError("Publication profile basics write requires public_dir.")
        if tenant_status == "invalid":
            raise ValueError("The resolved tenant publication profile document is invalid JSON.")

        next_payload = dict(tenant_profile or {})
        next_payload["title"] = normalized_request.profile_title
        next_payload["summary"] = normalized_request.profile_summary
        next_payload["contact_email"] = normalized_request.contact_email
        next_payload["public_website_url"] = normalized_request.public_website_url

        target_path = _tenant_profile_path(public_dir=self._public_dir, profile_id=profile_id)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(next_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        confirmed = self.read_publication_tenant_summary(
            PublicationTenantSummaryRequest(
                tenant_id=normalized_request.tenant_id,
                tenant_domain=normalized_request.tenant_domain,
            )
        )
        if confirmed.source is None:
            raise ValueError("Publication profile basics read-after-write confirmation failed.")
        return PublicationProfileBasicsWriteResult(
            source=confirmed.source,
            resolution_status=confirmed.resolution_status,
            warnings=confirmed.warnings,
        )

    def _resolve_publication_profiles(
        self,
        *,
        tenant_domain: str,
    ) -> tuple[
        str,
        dict[str, Any] | None,
        str,
        dict[str, Any] | None,
        str,
        dict[str, Any],
        list[str],
    ]:
        anthology_file = self._data_dir / "system" / "anthology.json"
        warnings: list[str] = []
        resolution_status: dict[str, Any] = {
            "anthology": "missing",
            "domain_match": "missing",
            "public_profile": "missing",
            "tenant_profile": "missing",
        }

        if not anthology_file.exists() or not anthology_file.is_file():
            warnings.append("Canonical system anthology is missing at data/system/anthology.json.")
            return "", None, "missing", None, "missing", resolution_status, warnings

        try:
            anthology_payload = _read_json_object(anthology_file)
        except (json.JSONDecodeError, ValueError):
            warnings.append("Canonical system anthology is not a valid JSON object.")
            resolution_status["anthology"] = "invalid"
            return "", None, "missing", None, "missing", resolution_status, warnings

        resolution_status["anthology"] = "loaded"
        profile_id = _resolve_profile_id_from_domain(
            anthology_payload=anthology_payload,
            tenant_domain=tenant_domain,
        )
        if not profile_id:
            warnings.append(
                "No canonical publication profile mapping was found for the requested tenant domain."
            )
            return "", None, "missing", None, "missing", resolution_status, warnings

        resolution_status["domain_match"] = "matched"
        public_profile, public_status = _load_publication_profile(
            public_dir=self._public_dir,
            profile_id=profile_id,
            include_fnd=False,
        )
        tenant_profile, tenant_status = _load_publication_profile(
            public_dir=self._public_dir,
            profile_id=profile_id,
            include_fnd=True,
        )
        resolution_status["public_profile"] = public_status
        resolution_status["tenant_profile"] = tenant_status

        if public_status == "missing":
            warnings.append("No public publication profile document was found for the resolved tenant profile.")
        elif public_status == "invalid":
            warnings.append("The resolved public publication profile document is invalid JSON.")
        if tenant_status == "missing":
            warnings.append("No tenant publication profile document was found for the resolved tenant profile.")
        elif tenant_status == "invalid":
            warnings.append("The resolved tenant publication profile document is invalid JSON.")
        return (
            profile_id,
            public_profile,
            public_status,
            tenant_profile,
            tenant_status,
            resolution_status,
            warnings,
        )


def _resolve_profile_id_from_domain(
    *,
    anthology_payload: dict[str, Any],
    tenant_domain: str,
) -> str:
    normalized_domain = _as_text(tenant_domain).lower()
    if not normalized_domain:
        return ""
    for resource_id in sorted(anthology_payload.keys()):
        raw = anthology_payload[resource_id]
        labels = tuple(label.lower() for label in _extract_labels(raw))
        if normalized_domain not in labels:
            continue
        profile_id = _extract_profile_id(raw)
        if profile_id:
            return profile_id
    return ""


def _extract_labels(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, list) and len(raw) > 1:
        return _as_text_tuple(raw[1])
    if isinstance(raw, dict):
        return _as_text_tuple(raw.get("labels") or raw.get("label") or raw.get("name"))
    return ()


def _extract_profile_id(raw: Any) -> str:
    if isinstance(raw, list) and raw:
        triple = raw[0]
        if isinstance(triple, list) and len(triple) > 4:
            return _as_text(triple[4])
    if isinstance(raw, dict):
        return _as_text(raw.get("profile_id") or raw.get("msn_id"))
    return ""


def _candidate_profile_paths(*, public_dir: Path, profile_id: str, include_fnd: bool) -> tuple[Path, ...]:
    candidates = [
        public_dir / f"{profile_id}.json",
        public_dir / f"msn-{profile_id}.json",
        public_dir / f"mss-{profile_id}.json",
    ]
    if include_fnd:
        candidates = [_tenant_profile_path(public_dir=public_dir, profile_id=profile_id)]
    return tuple(candidates)


def _tenant_profile_path(*, public_dir: Path, profile_id: str) -> Path:
    return public_dir / f"fnd-{profile_id}.json"


def _load_publication_profile(
    *,
    public_dir: Path | None,
    profile_id: str,
    include_fnd: bool,
) -> tuple[dict[str, Any] | None, str]:
    if public_dir is None:
        return None, "missing"
    saw_invalid = False
    for path in _candidate_profile_paths(public_dir=public_dir, profile_id=profile_id, include_fnd=include_fnd):
        if not path.exists() or not path.is_file():
            continue
        try:
            return _read_json_object(path), "loaded"
        except (json.JSONDecodeError, ValueError):
            saw_invalid = True
    return None, "invalid" if saw_invalid else "missing"
