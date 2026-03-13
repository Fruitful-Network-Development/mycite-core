from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

from portal.services.runtime_paths import legacy_member_progeny_dir, legacy_tenant_progeny_dir, progeny_root

_INSTANCE_RE = re.compile(r"^msn-(?P<provider>[^.]+)\.(?P<progeny_type>admin|member|user)-(?P<alias>.+)$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _load_shared_hosted_model():
    portals_root = Path(__file__).resolve().parents[6]
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    import _shared.portal.hosted_model as module

    return module


_HOSTED = _load_shared_hosted_model()
SUPPORTED_PROGENY_TYPES = tuple(_HOSTED.SUPPORTED_PROGENY_TYPES)


def _as_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _safe_token(value: str, *, field: str) -> str:
    token = _as_text(value)
    if not token or not _SAFE_TOKEN_RE.fullmatch(token):
        raise ValueError(f"{field} must match [A-Za-z0-9._:-]{{1,128}}")
    return token


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _canonical_type(value: str) -> str:
    token = _as_text(value).lower()
    if token == "tenant":
        return "member"
    if token == "board_member":
        return "member"
    return token


def canonical_instance_filename(provider_msn_id: str, progeny_type: str, alias_associated_msn_id: str) -> str:
    provider = _safe_token(provider_msn_id, field="provider_msn_id")
    token = _canonical_type(progeny_type)
    if token not in SUPPORTED_PROGENY_TYPES:
        raise ValueError(f"Unsupported progeny_type: {progeny_type}")
    alias_id = _safe_token(alias_associated_msn_id, field="alias_associated_msn_id")
    return f"msn-{provider}.{token}-{alias_id}.json"


def parse_instance_stem(instance_stem: str) -> dict[str, str] | None:
    match = _INSTANCE_RE.fullmatch(_as_text(instance_stem))
    if not match:
        return None
    return {
        "provider_msn_id": _as_text(match.group("provider")),
        "progeny_type": _canonical_type(match.group("progeny_type")),
        "alias_associated_msn_id": _as_text(match.group("alias")),
    }


def _candidate_ids(payload: dict[str, Any], metadata: dict[str, Any]) -> list[str]:
    values = [
        payload.get("member_id"),
        payload.get("member_msn_id"),
        payload.get("tenant_id"),
        payload.get("tenant_msn_id"),
        payload.get("alias_associated_msn_id"),
        payload.get("msn_id"),
        metadata.get("alias_associated_msn_id"),
        metadata.get("instance_id"),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _as_text(value)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _record_key(payload: dict[str, Any], metadata: dict[str, Any]) -> str:
    progeny_type = _canonical_type(_as_text(payload.get("profile_type") or payload.get("progeny_type") or metadata.get("progeny_type")))
    ids = _candidate_ids(payload, metadata)
    return f"{progeny_type}:{ids[0] if ids else metadata.get('instance_id') or 'unknown'}"


def _iter_unified_paths(private_dir: Path) -> list[Path]:
    root = progeny_root(private_dir)
    if not root.exists() or not root.is_dir():
        return []
    return [path for path in sorted(root.glob("*.json")) if path.is_file()]


def _iter_legacy_paths(private_dir: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for progeny_type in SUPPORTED_PROGENY_TYPES:
        root = progeny_root(private_dir) / f"{progeny_type}_progeny"
        if root.exists() and root.is_dir():
            for path in sorted(root.glob("*.json")):
                out.append((path, progeny_type))
    for path in sorted(legacy_member_progeny_dir(private_dir).glob("*.json")):
        out.append((path, "member"))
    for path in sorted(legacy_tenant_progeny_dir(private_dir).glob("*.json")):
        out.append((path, "member"))
    return out


def list_instances(private_dir: Path, progeny_type: str = "") -> list[dict[str, Any]]:
    requested_type = _canonical_type(progeny_type)
    prioritized: dict[str, dict[str, Any]] = {}

    for priority, path in enumerate(_iter_unified_paths(private_dir)):
        if path.name.endswith("-config.json"):
            continue
        meta = parse_instance_stem(path.stem)
        if meta is None:
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        if requested_type and meta["progeny_type"] != requested_type:
            continue
        record = {
            "instance_id": path.stem,
            "path": path,
            "payload": copy.deepcopy(payload),
            "provider_msn_id": meta["provider_msn_id"],
            "progeny_type": meta["progeny_type"],
            "alias_associated_msn_id": meta["alias_associated_msn_id"],
            "source_kind": "unified",
            "priority": priority,
        }
        key = _record_key(payload, record)
        prioritized[key] = record

    offset = len(prioritized)
    for priority, item in enumerate(_iter_legacy_paths(private_dir), start=offset):
        path, fallback_type = item
        if path.name.endswith("-config.json"):
            continue
        try:
            payload = _read_json(path)
        except Exception:
            continue
        token = _canonical_type(_as_text(payload.get("profile_type") or payload.get("progeny_type") or fallback_type))
        if token not in SUPPORTED_PROGENY_TYPES:
            continue
        if requested_type and token != requested_type:
            continue
        alias_id = _as_text(
            payload.get("alias_associated_msn_id")
            or payload.get("member_msn_id")
            or payload.get("tenant_msn_id")
            or payload.get("msn_id")
            or path.stem
        )
        record = {
            "instance_id": path.stem,
            "path": path,
            "payload": copy.deepcopy(payload),
            "provider_msn_id": "",
            "progeny_type": token,
            "alias_associated_msn_id": alias_id,
            "source_kind": "legacy",
            "priority": priority,
        }
        key = _record_key(payload, record)
        if key in prioritized:
            continue
        prioritized[key] = record

    out = list(prioritized.values())

    def _sort_title(item: dict[str, Any]) -> str:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
        return _as_text(payload.get("title") or display.get("title") or item.get("alias_associated_msn_id"))

    out.sort(
        key=lambda item: (
            _as_text(item.get("progeny_type")),
            _sort_title(item),
            _as_text(item.get("instance_id")),
        )
    )
    return out


def load_instance(private_dir: Path, instance_id: str) -> dict[str, Any] | None:
    token = _as_text(instance_id)
    for record in list_instances(private_dir):
        if token == _as_text(record.get("instance_id")):
            return record
    return None


def find_member_instance(private_dir: Path, member_id: str) -> dict[str, Any] | None:
    token = _as_text(member_id)
    if not token:
        return None
    for record in list_instances(private_dir, "member"):
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        if token in _candidate_ids(payload, record):
            return record
    return None


def find_profile_by_associated_msn(private_dir: Path, associated_msn_id: str, progeny_type: str = "") -> dict[str, Any] | None:
    token = _as_text(associated_msn_id)
    requested_type = _canonical_type(progeny_type)
    if not token:
        return None
    for record in list_instances(private_dir, requested_type):
        payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        if token in _candidate_ids(payload, record):
            return record
    return None


def save_instance(private_dir: Path, payload: dict[str, Any], provider_msn_id: str, *, instance_id: str = "") -> Path:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    token = _canonical_type(_as_text(payload.get("profile_type") or payload.get("progeny_type")))
    if token not in SUPPORTED_PROGENY_TYPES:
        raise ValueError("payload.profile_type or payload.progeny_type must be admin/member/user")

    existing = load_instance(private_dir, instance_id) if _as_text(instance_id) else None
    alias_associated_msn_id = _as_text(
        payload.get("alias_associated_msn_id")
        or payload.get("member_msn_id")
        or payload.get("tenant_msn_id")
        or payload.get("msn_id")
        or payload.get("member_id")
        or payload.get("tenant_id")
        or (existing or {}).get("alias_associated_msn_id")
    )
    if not alias_associated_msn_id:
        raise ValueError("Unable to infer alias_associated_msn_id from payload")

    filename = canonical_instance_filename(provider_msn_id, token, alias_associated_msn_id)
    target = progeny_root(private_dir) / filename
    target.parent.mkdir(parents=True, exist_ok=True)

    clean = copy.deepcopy(payload)
    clean["profile_type"] = token
    clean["progeny_type"] = token
    clean["alias_associated_msn_id"] = alias_associated_msn_id
    clean.setdefault("msn_id", alias_associated_msn_id)
    target.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return target
