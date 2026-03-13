from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from portal.services.progeny_workspace import find_member_instance


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _safe_lookup_id(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        return ""
    return normalized


def _match_tenant(payload: Dict[str, Any], tenant_id: str) -> bool:
    candidates = [
        str(payload.get("member_id") or "").strip(),
        str(payload.get("member_msn_id") or "").strip(),
        str(payload.get("child_msn_id") or "").strip(),
        str(payload.get("tenant_id") or "").strip(),
        str(payload.get("tenant_msn_id") or "").strip(),
        str(payload.get("msn_id") or "").strip(),
    ]
    return tenant_id in {c for c in candidates if c}


def load_tenant_progeny(private_dir: Path, alias_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    _ = _safe_lookup_id(alias_id)
    safe_tenant_id = _safe_lookup_id(tenant_id)
    if not safe_tenant_id:
        return None

    record = find_member_instance(private_dir, safe_tenant_id)
    if record is not None:
        payload = record.get("payload")
        if isinstance(payload, dict) and _match_tenant(payload, safe_tenant_id):
            return payload
    return None
