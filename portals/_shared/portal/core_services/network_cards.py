from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..datum_refs import normalize_datum_ref, parse_datum_ref
from ..progeny_model.compat import LEGAL_ENTITY_BASE_TYPES, canonical_progeny_type
from ..progeny_model.inheritance import resolve_inherited_fields
from ..runtime_paths import (
    alias_read_dirs,
    contract_read_dirs,
    internal_progeny_read_dirs,
    network_dir,
    unified_progeny_read_paths,
)

ProfileCard = dict[str, Any]

_ALIAS_EXPECTED_BY_TYPE = {
    "admin": True,
    "member": False,
    "user": False,
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
    canonical_type = canonical_progeny_type(progeny_type)
    card: ProfileCard = {
        "schema": "mycite.progeny.profile_card.v1",
        "progeny_id": progeny_id,
        "msn_id": msn_id,
        "progeny_type": canonical_type,
        "display": {
            "title": _derive_display_title(payload, fallback=progeny_id or msn_id or canonical_type.title()),
            "subtitle": str(payload.get("entity_type") or "").strip(),
        },
        "contact": _derive_contact(payload),
        "alias_expected": bool(
            payload.get("alias_expected")
            if isinstance(payload.get("alias_expected"), bool)
            else _ALIAS_EXPECTED_BY_TYPE.get(canonical_type, False)
        ),
        "status": _normalize_status(payload),
        "source": {
            "kind": source_kind,
            "ref": source_ref,
            "path": str(source_path) if source_path else "",
            "exists": bool(source_path and source_path.exists()),
        },
    }
    if canonical_type != str(progeny_type or "").strip().lower():
        card.setdefault("status", {})["note"] = f"legacy progeny type '{progeny_type}' normalized to '{canonical_type}'"
    if _contains_forbidden_key(payload):
        card.setdefault("status", {})["note"] = "secret-like keys detected; ignored for UI"
    card["raw"] = payload
    return card


def _iter_progeny_refs(raw: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _push(progeny_type: str, ref_token: Any) -> None:
        t = str(progeny_type or "").strip().lower()
        r = str(ref_token or "").strip()
        if not t or not r:
            return
        out.append((t, r))

    def _walk(node: Any, fallback_type: str = "") -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item, fallback_type=fallback_type)
            return

        if isinstance(node, dict):
            explicit_type = str(node.get("progeny_type") or node.get("type") or fallback_type or "").strip().lower()
            explicit_ref = (
                node.get("ref")
                or node.get("path")
                or node.get("file")
                or node.get("source")
            )
            if explicit_type and explicit_ref:
                _push(explicit_type, explicit_ref)
                refs = node.get("refs")
                if isinstance(refs, list):
                    for ref_item in refs:
                        _push(explicit_type, ref_item)
                return

            for key, value in node.items():
                key_token = str(key or "").strip().lower()
                if key_token in {"progeny_type", "type", "ref", "path", "file", "source", "refs"}:
                    continue
                if isinstance(value, str):
                    _push(key_token or fallback_type, value)
                    continue
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            _push(key_token or fallback_type, item)
                        else:
                            _walk(item, fallback_type=key_token or fallback_type)
                    continue
                if isinstance(value, dict):
                    _walk(value, fallback_type=key_token or fallback_type)
            return

    _walk(raw)
    return out


def _progeny_source_path(private_dir: Path, ref_token: str) -> Path | None:
    rel = Path(str(ref_token or "").strip())
    if not str(rel) or rel.is_absolute() or ".." in rel.parts:
        return None
    candidates: list[Path] = []
    if rel.parts and rel.parts[0] == "network":
        candidates.append(private_dir / rel)
    elif rel.parts and rel.parts[0] == "progeny":
        candidates.append(network_dir(private_dir) / rel)
        candidates.append(private_dir / rel)
    else:
        candidates.append(network_dir(private_dir) / "progeny" / rel)
        candidates.append(private_dir / "progeny" / rel)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def _from_config_refs(private_dir: Path, config: dict[str, Any]) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    raw = config.get("progeny")
    refs = _iter_progeny_refs(raw)
    if not refs:
        return out

    for idx, (progeny_type, ref_token) in enumerate(refs):
        source_path = _progeny_source_path(private_dir, ref_token)
        if source_path is None:
            continue

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
    seen_paths: set[Path] = set()
    for root in internal_progeny_read_dirs(private_dir):
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.json")):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            payload = _read_json(path)
            if payload is None:
                continue
            progeny_type = canonical_progeny_type(str(payload.get("progeny_type") or "member").strip().lower())
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


def _from_unified_registry(private_dir: Path) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    for path in unified_progeny_read_paths(private_dir):
        payload = _read_json(path)
        if payload is None:
            continue

        if isinstance(payload.get("items"), list):
            entries = list(payload.get("items") or [])
        elif isinstance(payload.get("entries"), list):
            entries = list(payload.get("entries") or [])
        else:
            entries = []
        for index, item in enumerate(entries):
            if not isinstance(item, dict):
                continue
            progeny_type = canonical_progeny_type(str(item.get("progeny_type") or "member").strip().lower())
            progeny_id = str(item.get("progeny_id") or item.get("msn_id") or f"entry-{index + 1}").strip()
            msn_id = str(item.get("msn_id") or "").strip()
            card = _card(
                progeny_id=progeny_id,
                msn_id=msn_id,
                progeny_type=progeny_type,
                payload=item,
                source_kind="unified_registry",
                source_ref=path.name,
                source_path=path,
            )
            out.append(card)
        break
    return out


def build_alias_cards(private_dir: Path) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    seen_alias_ids: set[str] = set()
    for alias_dir in alias_read_dirs(private_dir):
        if not alias_dir.exists() or not alias_dir.is_dir():
            continue
        for path in sorted(alias_dir.glob("*.json")):
            alias_id = path.stem
            if alias_id in seen_alias_ids:
                continue
            seen_alias_ids.add(alias_id)
            payload = _read_json(path)
            if payload is None:
                continue
            merged = dict(payload)
            merged.setdefault("title", str(payload.get("host_title") or alias_id).strip())
            progeny_type = canonical_progeny_type(str(payload.get("progeny_type") or "alias").strip().lower() or "alias")
            out.append(
                _card(
                    progeny_id=alias_id,
                    msn_id=str(payload.get("msn_id") or payload.get("alias_host") or "").strip(),
                    progeny_type=progeny_type,
                    payload=merged,
                    source_kind="alias_json",
                    source_ref=path.name,
                    source_path=path,
                )
            )
    return out


def build_contract_cards(private_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_contract_ids: set[str] = set()
    for root in contract_read_dirs(private_dir):
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.json")):
            contract_id = path.stem
            if contract_id in seen_contract_ids:
                continue
            seen_contract_ids.add(contract_id)
            payload = _read_json(path)
            if payload is None:
                continue
            out.append(
                {
                    "id": contract_id,
                    "title": str(payload.get("contract_type") or payload.get("type") or contract_id),
                    "counterparty_msn_id": str(payload.get("counterparty_msn_id") or "").strip(),
                    "status": str(payload.get("status") or "active").strip(),
                    "source": path.name,
                }
            )
    return out


def build_progeny_cards(private_dir: Path, config: dict[str, Any]) -> list[ProfileCard]:
    out: list[ProfileCard] = []
    out.extend(_from_unified_registry(private_dir))
    seen = {str(card.get("progeny_id") or "") for card in out}

    for card in _from_config_refs(private_dir, config):
        progeny_id = str(card.get("progeny_id") or "")
        if progeny_id in seen:
            continue
        seen.add(progeny_id)
        out.append(card)
    for card in _from_internal_progeny(private_dir):
        progeny_id = str(card.get("progeny_id") or "")
        if progeny_id in seen:
            continue
        seen.add(progeny_id)
        out.append(card)
    return out


def _inheritance_rules(config: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    root = dict(config or {})
    candidates: list[dict[str, Any]] = [root]
    org = root.get("organization_config")
    if isinstance(org, dict):
        candidates.append(org)
    broadcast = root.get("broadcast_config")
    if isinstance(broadcast, dict):
        candidates.append(broadcast)

    for candidate in candidates:
        section = candidate.get("inheritance_rules")
        if isinstance(section, dict):
            out.update(section)
    return out


def _identity_tokens(payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    keys = (
        "progeny_id",
        "msn_id",
        "member_id",
        "member_msn_id",
        "tenant_id",
        "tenant_msn_id",
        "child_msn_id",
        "alias_id",
    )
    for key in keys:
        token = str(payload.get(key) or "").strip()
        if token:
            out.add(token)
    return out


def _progeny_index(cards: list[ProfileCard]) -> dict[str, list[ProfileCard]]:
    out: dict[str, list[ProfileCard]] = {}
    for card in cards:
        raw = card.get("raw") if isinstance(card.get("raw"), dict) else {}
        payload = {**raw, **card}
        for token in _identity_tokens(payload):
            bucket = out.setdefault(token, [])
            bucket.append(card)
    return out


def _ref_provenance(
    *,
    field_id: str,
    resolved_value: str,
    alias_fields: dict[str, Any],
    progeny_fields: dict[str, Any],
) -> str:
    alias_token = str(alias_fields.get(field_id) or "").strip()
    progeny_token = str(progeny_fields.get(field_id) or "").strip()
    if alias_token and alias_token == resolved_value:
        return "alias"
    if progeny_token and progeny_token == resolved_value:
        return "progeny"
    if alias_token:
        return "alias"
    if progeny_token:
        return "progeny"
    return "default"


def _normalized_ref_map(
    *,
    resolved_fields: dict[str, Any],
    alias_fields: dict[str, Any],
    progeny_fields: dict[str, Any],
    fallback_msn_id: str,
) -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, str]]:
    ref_map: dict[str, dict[str, str]] = {}
    provenance_map: dict[str, str] = {}
    legacy_echo: dict[str, str] = {}

    for field_id, value in resolved_fields.items():
        raw_value = str(value or "").strip()
        if not raw_value:
            continue
        try:
            parsed = parse_datum_ref(raw_value, field_name=field_id)
        except Exception:
            continue

        normalized_dot = normalize_datum_ref(
            raw_value,
            local_msn_id=fallback_msn_id,
            require_qualified=bool(fallback_msn_id),
            write_format="dot",
            field_name=field_id,
        )
        normalized_hyphen = normalize_datum_ref(
            raw_value,
            local_msn_id=fallback_msn_id,
            require_qualified=bool(fallback_msn_id),
            write_format="hyphen",
            field_name=field_id,
        )
        provenance = _ref_provenance(
            field_id=field_id,
            resolved_value=raw_value,
            alias_fields=alias_fields,
            progeny_fields=progeny_fields,
        )
        provenance_map[field_id] = provenance
        ref_map[field_id] = {
            "field": field_id,
            "raw_ref": raw_value,
            "normalized_ref": normalized_dot,
            "normalized_ref_hyphen": normalized_hyphen,
            "datum_address": parsed.datum_address,
            "msn_id": str(parsed.msn_id or fallback_msn_id or "").strip(),
            "provenance": provenance,
        }
        if parsed.legacy_hyphen_source:
            legacy_echo[field_id] = parsed.legacy_hyphen_source
            ref_map[field_id]["legacy_hyphen_source"] = parsed.legacy_hyphen_source
    return ref_map, provenance_map, legacy_echo


def _link_alias_inheritance(
    *,
    alias_cards: list[ProfileCard],
    progeny_cards: list[ProfileCard],
    inheritance_rules: dict[str, Any],
) -> None:
    by_identity = _progeny_index(progeny_cards)
    for alias in alias_cards:
        alias_raw = alias.get("raw") if isinstance(alias.get("raw"), dict) else {}
        alias_payload = {**alias_raw, **alias}
        tokens = _identity_tokens(alias_payload)
        matched: ProfileCard | None = None
        for token in tokens:
            candidates = by_identity.get(token) or []
            if candidates:
                matched = candidates[0]
                break

        progeny_payload = matched.get("raw") if isinstance(matched, dict) and isinstance(matched.get("raw"), dict) else {}
        inherited = resolve_inherited_fields(
            alias_payload=alias_payload,
            progeny_payload=progeny_payload,
            inheritance_rules=inheritance_rules,
        )
        resolved_fields = dict(inherited.get("resolved_fields") or {})
        alias_fields = dict(inherited.get("alias_fields") or {})
        progeny_fields = dict(inherited.get("progeny_fields") or {})
        fallback_msn_id = str(alias_payload.get("msn_id") or progeny_payload.get("msn_id") or "").strip()
        normalized_map, provenance_map, legacy_echo = _normalized_ref_map(
            resolved_fields=resolved_fields,
            alias_fields=alias_fields,
            progeny_fields=progeny_fields,
            fallback_msn_id=fallback_msn_id,
        )
        alias["inheritance"] = {
            "matched_progeny_id": str(matched.get("progeny_id") or "") if isinstance(matched, dict) else "",
            "matched_progeny_type": (
                canonical_progeny_type(str(matched.get("progeny_type") or ""))
                if isinstance(matched, dict)
                else ""
            ),
            **inherited,
            "normalized_reference_map": normalized_map,
            "reference_provenance": provenance_map,
            "legacy_ref_echo": legacy_echo,
        }
        alias["resolved_profile"] = {
            "fields": resolved_fields,
            "alias_fields": alias_fields,
            "progeny_fields": progeny_fields,
            "normalized_reference_map": normalized_map,
            "reference_provenance": provenance_map,
        }


def build_network_cards(private_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    progeny_cards = build_progeny_cards(private_dir, config)
    alias_cards = build_alias_cards(private_dir)
    rules = _inheritance_rules(config)
    _link_alias_inheritance(
        alias_cards=alias_cards,
        progeny_cards=progeny_cards,
        inheritance_rules=rules,
    )
    return {
        "contracts": build_contract_cards(private_dir),
        "progeny": progeny_cards,
        "alias": alias_cards,
        "model": {
            "legal_entity_baseline_classes": list(LEGAL_ENTITY_BASE_TYPES),
            "inheritance_rules": rules,
        },
    }
