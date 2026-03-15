from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_closure_signature(canonical_refs: list[str]) -> str:
    return _stable_hash({"canonical_refs": sorted(str(item).strip() for item in canonical_refs if str(item).strip())})


def compute_isolate_identity(
    *,
    source_msn_id: str,
    resource_id: str,
    export_family: str,
    payload_sha256: str,
    closure_signature: str,
    wire_variant: str,
    source_card_revision: str = "",
) -> str:
    return _stable_hash(
        {
            "source_msn_id": str(source_msn_id or ""),
            "resource_id": str(resource_id or ""),
            "export_family": str(export_family or ""),
            "payload_sha256": str(payload_sha256 or ""),
            "closure_signature": str(closure_signature or ""),
            "wire_variant": str(wire_variant or ""),
            "source_card_revision": str(source_card_revision or ""),
        }
    )
