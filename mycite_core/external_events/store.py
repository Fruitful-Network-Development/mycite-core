from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from mycite_core.datum_refs import normalize_datum_ref, parse_datum_ref
from mycite_core.runtime_paths import (
    external_event_log_path,
    external_event_read_paths,
    external_event_types_dir,
)

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

_EXTERNAL_EVENT_PREFIXES = (
    "alias.",
    "compact_array.",
    "contract.",
    "contract_",
    "contract_proposal",
    "line.",
    "network.",
    "profile.",
    "progeny.",
    "public.",
)
_QUALIFIER_VALUES = {"anonymous", "asymmetric", "symmetric"}


@dataclass(frozen=True)
class ReadResult:
    events: List[Dict[str, Any]]
    parse_errors: int
    total_lines: int


class ExternalEventValidationError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = [str(item) for item in errors if str(item).strip()]
        super().__init__("; ".join(self.errors))


RequestLogValidationError = ExternalEventValidationError


def _log_dir(private_dir: Path) -> Path:
    return external_event_log_path(private_dir).parent


def _log_path(private_dir: Path, msn_id: str) -> Path:
    _ = msn_id
    return external_event_log_path(private_dir)


def _typed_log_dir(private_dir: Path) -> Path:
    return external_event_types_dir(private_dir)


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
        raise ExternalEventValidationError(errors)
    return out


def _event_type(event: Dict[str, Any]) -> str:
    return str(event.get("type") or "").strip()


def _is_v1_event_candidate(event: Dict[str, Any]) -> bool:
    return any(key in event for key in ("transmitter", "receiver", "event_datum", "status"))


def is_externally_meaningful_event(event: Dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        return False
    event_type = _event_type(event)
    if _is_v1_event_candidate(event):
        return True
    if any(event_type.startswith(prefix) for prefix in _EXTERNAL_EVENT_PREFIXES):
        return True
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    qualifier = str(details.get("qualifier") or event.get("qualifier") or "").strip().lower()
    return qualifier in _QUALIFIER_VALUES


def _normalize_external_event(msn_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(event)
    event_type = _event_type(out)
    if not event_type:
        raise ExternalEventValidationError(["type: required"])
    if _is_v1_event_candidate(out):
        return _normalize_v1_event(msn_id, out)
    if not is_externally_meaningful_event(out):
        raise ExternalEventValidationError(
            [
                "event is not externally meaningful; local-only operational chatter must go to local audit storage",
            ]
        )
    out["type"] = event_type
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
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


def append_external_event(private_dir: Path, msn_id: str, event: Dict[str, Any]) -> Path:
    d = _log_dir(private_dir)
    d.mkdir(parents=True, exist_ok=True)

    normalized = dict(event)
    bad = set(normalized.keys()).intersection(FORBIDDEN_SECRET_KEYS)
    if bad:
        raise ValueError(f"Do not store secrets in external event log. Forbidden keys: {sorted(bad)}")

    normalized = _normalize_external_event(msn_id, normalized)
    normalized.setdefault("ts_unix_ms", int(time.time() * 1000))
    normalized.setdefault("msn_id", msn_id)

    path = _log_path(private_dir, msn_id)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, separators=(",", ":")) + "\n")

    _write_typed_supplement(private_dir, normalized)
    return path


def read_external_events(
    private_dir: Path,
    msn_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    reverse: bool = True,
) -> ReadResult:
    paths = [path for path in external_event_read_paths(private_dir, msn_id) if path.exists() and path.is_file()]
    if not paths:
        return ReadResult(events=[], parse_errors=0, total_lines=0)

    parse_errors = 0
    total = 0
    collected: List[tuple[int, Dict[str, Any]]] = []
    seen_events: set[str] = set()
    order_index = 0

    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            total += 1
            try:
                obj = json.loads(line)
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


# Compatibility exports.
append_event = append_external_event
read_events = read_external_events
