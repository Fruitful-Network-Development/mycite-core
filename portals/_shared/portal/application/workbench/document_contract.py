from __future__ import annotations

import hashlib
import json
from typing import Any


DOCUMENT_SCHEMA = "mycite.workbench.document.v1"


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_workbench_document(
    *,
    document_id: str,
    instance_id: str,
    logical_key: str,
    display_name: str,
    family_kind: str,
    family_type: str,
    family_subtype: str = "",
    scope_kind: str,
    workspace: str = "system",
    visibility: str = "private",
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    persistence: dict[str, Any] | None = None,
    mutability: dict[str, Any] | None = None,
    revision: dict[str, Any] | None = None,
    inheritance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload_dict = _dict(payload)
    metadata_dict = _dict(metadata)
    metadata_dict.setdefault("payload_loaded", bool(payload_dict))
    revision_dict = _dict(revision)
    revision_dict.setdefault("version", 1)
    revision_dict.setdefault("etag", _json_hash(payload_dict))
    revision_dict.setdefault("updated_at_unix_ms", 0)
    return {
        "schema": DOCUMENT_SCHEMA,
        "identity": {
            "document_id": _text(document_id),
            "instance_id": _text(instance_id),
            "logical_key": _text(logical_key),
            "display_name": _text(display_name),
        },
        "family": {
            "kind": _text(family_kind),
            "type": _text(family_type),
            "subtype": _text(family_subtype),
        },
        "scope": {
            "kind": _text(scope_kind),
            "workspace": _text(workspace),
            "visibility": _text(visibility),
        },
        "payload": payload_dict,
        "metadata": metadata_dict,
        "capabilities": _dict(capabilities),
        "provenance": _dict(provenance),
        "persistence": _dict(persistence),
        "mutability": _dict(mutability),
        "revision": revision_dict,
        "inheritance": _dict(inheritance),
    }
