from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ProfileCard

_ALIAS_EXPECTED_BY_TYPE = {
    "board_member": False,
    "poc": True,
    "constituent_farm": True,
}

_FORBIDDEN_KEYS = {
    "secret",
    "token",
    "password",
    "private_key",
    "client_secret",
    "aws_secret_access_key",
}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _contains_forbidden_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(value):
                return True
        return False
    if isinstance(obj, list):
        return any(_contains_forbidden_key(item) for item in obj)
    return False


def _derive_display_title(payload: dict[str, Any], fallback: str) -> str:
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    title = str(display.get("title") or payload.get("title") or fallback).strip()
    return title or fallback


def _derive_contact(payload: dict[str, Any]) -> dict[str, str]:
    contact = payload.get("contact") if isinstance(payload.get("contact"), dict) else {}
    fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
    name = str(contact.get("name") or fields.get("name") or fields.get("full_name") or "").strip()
    email = str(contact.get("email") or fields.get("email") or "").strip()
    out: dict[str, str] = {}
    if name:
        out["name"] = name
    if email:
        out["email"] = email
    return out


def _normalize_status(payload: dict[str, Any]) -> dict[str, str]:
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
    state = str(status.get("state") or status.get("status") or payload.get("state") or "active").strip().lower()
    note = str(status.get("note") or "").strip()
    out: dict[str, str] = {"state": state or "active"}
    if note:
        out["note"] = note
    return out


def _card(
    *,
    progeny_id: str,
    msn_id: str,
    progeny_type: str,
    payload: dict[str, Any],
    source_kind: str,
    source_ref: str,
    source_path: Path | None,
) -> ProfileCard:
    card: ProfileCard = {
        "schema": "mycite.progeny.profile_card.v1",
        "progeny_id": progeny_id,
        "msn_id": msn_id,
        "progeny_type": progeny_type,
        "display": {
            "title": _derive_display_title(payload, fallback=progeny_id or msn_id or progeny_type.title()),
            "subtitle": str(payload.get("entity_type") or "").strip(),
        },
        "contact": _derive_contact(payload),
        "alias_expected": bool(
            payload.get("alias_expected")
            if isinstance(payload.get("alias_expected"), bool)
            else _ALIAS_EXPECTED_BY_TYPE.get(progeny_type, False)
        ),
        "status": _normalize_status(payload),
        "source": {
            "kind": source_kind,
            "ref": source_ref,
            "path": str(source_path) if source_path else "",
            "exists": bool(source_path and source_path.exists()),
        },
    }
    if _contains_forbidden_key(payload):
        card.setdefault("status", {})["note"] = "secret-like keys detected; ignored for UI"
    card["raw"] = payload
    return card


def _from_config_refs(private_dir: Path, config: dict[str, Any]) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    raw = config.get("progeny")
    if not isinstance(raw, list):
        return out

    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict) or not entry:
            continue
        progeny_type, ref = next(iter(entry.items()))
        progeny_type = str(progeny_type or "").strip().lower()
        ref_token = str(ref or "").strip()
        if not progeny_type or not ref_token:
            continue

        source_path = private_dir / "progeny" / ref_token
        payload = _read_json(source_path) or {}

        stem = Path(ref_token).stem
        card = _card(
            progeny_id=stem or f"cfg-{idx}",
            msn_id=str(payload.get("msn_id") or "").strip(),
            progeny_type=progeny_type,
            payload=payload,
            source_kind="config_ref",
            source_ref=ref_token,
            source_path=source_path,
        )
        out.append(card)
    return out


def _from_internal_progeny(private_dir: Path) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    root = private_dir / "progeny" / "internal"
    if not root.exists() or not root.is_dir():
        return out

    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        if payload is None:
            continue
        progeny_type = str(payload.get("progeny_type") or "board_member").strip().lower()
        progeny_id = str(payload.get("progeny_id") or path.stem).strip() or path.stem
        msn_id = str(payload.get("msn_id") or "").strip()
        out.append(
            _card(
                progeny_id=progeny_id,
                msn_id=msn_id,
                progeny_type=progeny_type,
                payload=payload,
                source_kind="internal_json",
                source_ref=path.name,
                source_path=path,
            )
        )
    return out


def build_alias_cards(private_dir: Path) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    alias_dir = private_dir / "aliases"
    if not alias_dir.exists() or not alias_dir.is_dir():
        return out

    for path in sorted(alias_dir.glob("*.json")):
        payload = _read_json(path)
        if payload is None:
            continue
        alias_id = path.stem
        merged = dict(payload)
        merged.setdefault("title", str(payload.get("host_title") or alias_id).strip())
        out.append(
            _card(
                progeny_id=alias_id,
                msn_id=str(payload.get("msn_id") or payload.get("alias_host") or "").strip(),
                progeny_type=str(payload.get("progeny_type") or "alias").strip().lower() or "alias",
                payload=merged,
                source_kind="alias_json",
                source_ref=path.name,
                source_path=path,
            )
        )
    return out


def build_contract_cards(private_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    root = private_dir / "contracts"
    if not root.exists() or not root.is_dir():
        return out

    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        if payload is None:
            continue
        out.append(
            {
                "id": path.stem,
                "title": str(payload.get("contract_type") or payload.get("type") or path.stem),
                "counterparty_msn_id": str(payload.get("counterparty_msn_id") or "").strip(),
                "status": str(payload.get("status") or "active").strip(),
                "source": path.name,
            }
        )
    return out


def build_magnetlink_cards(private_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    root = private_dir / "magnetlinks"
    if not root.exists() or not root.is_dir():
        return out

    for path in sorted(root.glob("*.json")):
        payload = _read_json(path)
        if payload is None:
            continue
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        out.append(
            {
                "id": path.stem,
                "title": str(target.get("name") or payload.get("contract_type") or path.stem).strip(),
                "counterparty_msn_id": str(payload.get("counterparty_msn_id") or "").strip(),
                "status": str(payload.get("status") or "active").strip(),
                "source": path.name,
            }
        )
    return out


def build_progeny_cards(private_dir: Path, config: dict[str, Any]) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    out.extend(_from_config_refs(private_dir, config))

    seen = {str(card.get("progeny_id") or "") for card in out}
    for card in _from_internal_progeny(private_dir):
        progeny_id = str(card.get("progeny_id") or "")
        if progeny_id in seen:
            continue
        seen.add(progeny_id)
        out.append(card)
    return out


def build_network_cards(private_dir: Path, config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "contracts": build_contract_cards(private_dir),
        "magnetlinks": build_magnetlink_cards(private_dir),
        "progeny": build_progeny_cards(private_dir, config),
        "alias": build_alias_cards(private_dir),
    }
