from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.ports.datum_store import (
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
    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)

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
