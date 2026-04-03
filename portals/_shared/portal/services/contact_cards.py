from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from _shared.portal.services.profile_resolver import find_local_contact_card


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def read_json_object(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def find_local_public_card(public_dir: Path, msn_id: str) -> Optional[Path]:
    return find_local_contact_card(public_dir=public_dir, fallback_dir=None, msn_id=msn_id, include_fnd=False)


def fetch_remote_contact_card(msn_id: str) -> Dict[str, Any]:
    base = _as_str(os.environ.get("MYCITE_CONTACT_BASE_URL")).rstrip("/")
    if not base:
        raise FileNotFoundError(
            "Contact card is not local and MYCITE_CONTACT_BASE_URL is unset for remote lookup."
        )
    url = f"{base}/{msn_id}.json"
    with urllib.request.urlopen(url, timeout=4.0) as resp:
        body = resp.read()
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Remote contact card response was not a JSON object")
    return payload


def resolve_contact_card(public_dir: Path, msn_id: str) -> Dict[str, Any]:
    local_path = find_local_public_card(public_dir, msn_id)
    if local_path is not None:
        return read_json_object(local_path)
    return fetch_remote_contact_card(msn_id)


def sanitize_contact_card(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "msn_id",
        "schema",
        "title",
        "public_key",
        "entity_type",
        "public_resources",
        "accessible",
        "options_public",
        "options",
    }
    return {key: payload.get(key) for key in allowed if key in payload}


def public_key_fingerprint(public_key_pem: str) -> str:
    token = _as_str(public_key_pem)
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
