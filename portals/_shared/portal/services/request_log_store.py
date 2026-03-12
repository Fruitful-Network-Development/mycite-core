from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from portal.services.datum_refs import normalize_datum_ref, parse_datum_ref
from portal.services.runtime_paths import request_log_path, request_log_read_paths, request_log_types_dir

FORBIDDEN_SECRET_KEYS = {
    "private_key", "private_key_pem", "secret", "token", "password",
    "symmetric_key", "hmac_key", "hmac_key_b64", "api_key",
}

@dataclass(frozen=True)
class ReadResult:
    events: List[Dict[str, Any]]
    parse_errors: int
    total_lines: int


class RequestLogValidationError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("; ".join(self.errors))


def _log_dir(private_dir: Path) -> Path:
    return request_log_path(private_dir).parent


def _log_path(private_dir: Path, msn_id: str) -> Path:
    _ = msn_id
    # Canonical request_log storage is a shared append-only NDJSON stream.
    return request_log_path(private_dir)


def _typed_log_dir(private_dir: Path) -> Path:
    return request_log_types_dir(private_dir)


def _typed_log_path(private_dir: Path, event_type: str) -> Path:
    safe_type = re.sub(r"[^A-Za-z0-9_.-]", "_", str(event_type or "").strip().lower()) or "unknown"
    return _typed_log_dir(private_dir) / f"{safe_type}.ndjson"


def _normalize_event_datum_ref(token: str, msn_id: str) -> str:
    return normalize_datum_ref(
        token,
        local_msn_id=msn_id,
        require_qualified=True,
        write_format="dot",
        field_name="event_datum",
    )


def _normalize_status_ref(token: str, msn_id: str) -> str:
    status_ref = normalize_datum_ref(
        token,
        local_msn_id=msn_id,
        require_qualified=True,
        write_format="dot",
        field_name="status",
    )
    parsed = parse_datum_ref(status_ref, field_name="status")
    if parsed.datum_address not in {"3-1-5", "3-1-6"}:
        raise ValueError("status must reference <msn_id>.3-1-5 or <msn_id>.3-1-6")
    return status_ref


def _normalize_v1_event(msn_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(event)
    errors: List[str] = []
    event_type = str(out.get("type") or "").strip()
    transmitter = str(out.get("transmitter") or "").strip()
    receiver = str(out.get("receiver") or "").strip()
    if not event_type:
        errors.append("type: required")
    if not transmitter or not (transmitter.startswith("msn-") or transmitter.startswith("alias-")):
        errors.append("transmitter: must start with 'msn-' or 'alias-'")
    if not receiver:
        errors.append("receiver: required")

    out["type"] = event_type
    out["transmitter"] = transmitter
    out["receiver"] = receiver
    try:
        out["event_datum"] = _normalize_event_datum_ref(out.get("event_datum"), msn_id)
    except ValueError as exc:
        errors.append(f"event_datum: {exc}")

    try:
        out["status"] = _normalize_status_ref(out.get("status"), msn_id)
    except ValueError as exc:
        errors.append(f"status: {exc}")

    if errors:
        raise RequestLogValidationError(errors)

    return out


def _write_typed_supplement(private_dir: Path, event: Dict[str, Any]) -> None:
    event_type = str(event.get("type") or "").strip()
    if not event_type:
        return
    payload = {
        "type": event_type,
        "event_datum": str(event.get("event_datum") or ""),
        "status": str(event.get("status") or ""),
        "transmitter": str(event.get("transmitter") or ""),
        "receiver": str(event.get("receiver") or ""),
        "ts_unix_ms": int(event.get("ts_unix_ms") or int(time.time() * 1000)),
        "msn_id": str(event.get("msn_id") or ""),
        "details": event.get("details") if isinstance(event.get("details"), dict) else {},
    }
    path = _typed_log_path(private_dir, event_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")


def append_event(private_dir: Path, msn_id: str, event: Dict[str, Any]) -> Path:
    """Append a single event to the request log (NDJSON).

    - Does NOT store secrets.
    - Adds a timestamp if none exists.
    """
    d = _log_dir(private_dir)
    d.mkdir(parents=True, exist_ok=True)

    e = dict(event)
    bad = set(e.keys()).intersection(FORBIDDEN_SECRET_KEYS)
    if bad:
        raise ValueError(f"Do not store secrets in request_log. Forbidden keys: {sorted(bad)}")

    is_v1 = any(key in e for key in ("transmitter", "receiver", "event_datum", "status"))
    if is_v1:
        e = _normalize_v1_event(msn_id, e)
    e.setdefault("ts_unix_ms", int(time.time() * 1000))
    e.setdefault("msn_id", msn_id)

    p = _log_path(private_dir, msn_id)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, separators=(",", ":")) + "\n")

    if is_v1:
        _write_typed_supplement(private_dir, e)
    return p


def read_events(
    private_dir: Path,
    msn_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    reverse: bool = True,
) -> ReadResult:
    """Read events from the request log.

    Behavior:
    - If log doesn't exist: returns empty list.
    - reverse=True returns newest-first (requires loading lines; acceptable for prototype).
    """
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
