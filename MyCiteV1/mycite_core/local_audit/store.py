from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from mycite_core.runtime_paths import local_audit_path

FORBIDDEN_SECRET_KEYS = {
    "private_key",
    "private_key_pem",
    "secret",
    "token",
    "password",
    "symmetric_key",
    "hmac_key",
    "hmac_key_b64",
    "api_key",
}


def append_local_audit_event(private_dir: Path, event: Dict[str, Any]) -> Path:
    payload = dict(event or {})
    bad = set(payload.keys()).intersection(FORBIDDEN_SECRET_KEYS)
    if bad:
        raise ValueError(f"Do not store secrets in local audit. Forbidden keys: {sorted(bad)}")
    payload.setdefault("ts_unix_ms", int(time.time() * 1000))
    payload.setdefault("type", "local.audit")
    path = local_audit_path(private_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
    return path


def read_local_audit_events(private_dir: Path, *, limit: int = 200) -> List[Dict[str, Any]]:
    path = local_audit_path(private_dir)
    if not path.exists() or not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    if limit > 0 and len(rows) > limit:
        return rows[-limit:]
    return rows
