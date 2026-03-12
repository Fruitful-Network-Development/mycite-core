from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from portal.services.runtime_paths import request_log_path, request_log_read_paths

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


@dataclass(frozen=True)
class ReadResult:
    events: List[Dict[str, Any]]
    parse_errors: int
    total_lines: int


def _log_dir(private_dir: Path) -> Path:
    return request_log_path(private_dir).parent


def _log_path(private_dir: Path, msn_id: str) -> Path:
    _ = msn_id
    return request_log_path(private_dir)


def append_event(private_dir: Path, msn_id: str, event: Dict[str, Any]) -> Path:
    d = _log_dir(private_dir)
    d.mkdir(parents=True, exist_ok=True)

    e = dict(event)
    bad = set(e.keys()).intersection(FORBIDDEN_SECRET_KEYS)
    if bad:
        raise ValueError(f"Do not store secrets in request_log. Forbidden keys: {sorted(bad)}")
    e.setdefault("ts_unix_ms", int(time.time() * 1000))
    e.setdefault("msn_id", msn_id)

    p = _log_path(private_dir, msn_id)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, separators=(",", ":")) + "\n")
    return p


def read_events(
    private_dir: Path,
    msn_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    reverse: bool = True,
) -> ReadResult:
    paths = [path for path in request_log_read_paths(private_dir, msn_id) if path.exists() and path.is_file()]
    if not paths:
        return ReadResult(events=[], parse_errors=0, total_lines=0)

    parse_errors = 0
    total = 0
    collected: List[tuple[int, Dict[str, Any]]] = []
    seen_events: set[str] = set()
    order_index = 0

    for path in paths:
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            total += 1
            try:
                obj = json.loads(ln)
            except Exception:
                parse_errors += 1
                continue
            if not isinstance(obj, dict):
                parse_errors += 1
                continue
            event_msn_id = str(obj.get("msn_id") or "").strip()
            if event_msn_id and event_msn_id != msn_id:
                continue
            dedupe_key = json.dumps(obj, sort_keys=True, separators=(",", ":"))
            if dedupe_key in seen_events:
                continue
            seen_events.add(dedupe_key)
            order_index += 1
            collected.append((order_index, obj))

    ranked = sorted(
        collected,
        key=lambda item: (int(item[1].get("ts_unix_ms") or 0), item[0]),
        reverse=reverse,
    )
    events = [item for _, item in ranked[offset : offset + limit]]
    return ReadResult(events=events, parse_errors=parse_errors, total_lines=total)
