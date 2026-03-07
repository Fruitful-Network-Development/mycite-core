from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

FORBIDDEN_SECRET_KEYS = {
    "private_key", "private_key_pem", "secret", "token", "password",
    "symmetric_key", "hmac_key", "hmac_key_b64", "api_key",
}

_DATUM_ADDRESS_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_NUMERIC_TOKEN_RE = re.compile(r"^[0-9]+(?:-[0-9]+)+$")


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
    return private_dir / "request_log"


def _log_path(private_dir: Path, msn_id: str) -> Path:
    # Append-only NDJSON is the simplest durable log for this stage.
    return _log_dir(private_dir) / f"{msn_id}.ndjson"


def _typed_log_dir(private_dir: Path) -> Path:
    return _log_dir(private_dir) / "types"


def _typed_log_path(private_dir: Path, event_type: str) -> Path:
    safe_type = re.sub(r"[^A-Za-z0-9_.-]", "_", str(event_type or "").strip().lower()) or "unknown"
    return _typed_log_dir(private_dir) / f"{safe_type}.ndjson"


def _qualified_tail_identifier(token: str) -> str:
    parts = str(token or "").split("-")
    if len(parts) < 4 or not all(part.isdigit() for part in parts):
        return ""
    return "-".join(parts[-3:])


def _normalize_event_datum_ref(token: str, msn_id: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        raise ValueError("event_datum is required for request_log v1 entries")
    if _DATUM_ADDRESS_RE.fullmatch(raw):
        if not str(msn_id or "").strip():
            raise ValueError("Cannot normalize event_datum without msn_id")
        return f"{msn_id}-{raw}"
    if _NUMERIC_TOKEN_RE.fullmatch(raw) and _DATUM_ADDRESS_RE.fullmatch(_qualified_tail_identifier(raw)):
        return raw
    raise ValueError("event_datum must be <datum_address> or <msn_id>-<datum_address>")


def _normalize_status_ref(token: str, msn_id: str) -> str:
    status_ref = _normalize_event_datum_ref(token, msn_id)
    if not status_ref.endswith("-3-1-5") and not status_ref.endswith("-3-1-6"):
        raise ValueError("status must reference <msn_id>-3-1-5 or <msn_id>-3-1-6")
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
    p = _log_path(private_dir, msn_id)
    if not p.exists():
        return ReadResult(events=[], parse_errors=0, total_lines=0)

    lines = p.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    parse_errors = 0
    events: List[Dict[str, Any]] = []

    iterable = reversed(lines) if reverse else lines
    # Apply offset/limit after ordering
    sliced = list(iterable)[offset : offset + limit]

    for ln in sliced:
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                events.append(obj)
            else:
                parse_errors += 1
        except Exception:
            parse_errors += 1

    return ReadResult(events=events, parse_errors=parse_errors, total_lines=total)
