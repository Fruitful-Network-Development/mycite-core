from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


_KEYCLOAK_ALIASES = {"key_glock", "keyglock", "key-clock", "key clock", "identity"}
_LEGACY_PROGENY_TYPE_MAP = {"tenant": "member", "board_member": "member"}
_DEFAULT_CHANNELS = [
    {
        "channel_id": "paypal",
        "display_name": "PayPal",
        "description": "Payment-processing channel metadata for alias-backed operations.",
        "required_fields": [],
    },
    {
        "channel_id": "aws",
        "display_name": "AWS",
        "description": "Cloud operations channel metadata for alias-backed operations.",
        "required_fields": [],
    },
    {
        "channel_id": "keycloak",
        "display_name": "Keycloak",
        "description": "Identity and access channel metadata for alias-backed operations.",
        "required_fields": [],
    },
]


def _canonical_progeny_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return "unknown"
    return _LEGACY_PROGENY_TYPE_MAP.get(token, token)


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _read_json_relaxed(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r",(\s*[\]}])", r"\1", text)
        payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def _normalize_channel_id(raw: str) -> str:
    token = str(raw or "").strip().lower().replace("_", "-")
    if token in _KEYCLOAK_ALIASES:
        return "keycloak"
    return token


def _default_broadcast_config(portal_instance_id: str, portal_title: str, msn_id: str) -> Dict[str, Any]:
    title = str(portal_title or msn_id or portal_instance_id or "Portal").strip() or "Portal"
    return {
        "schema": "mycite.portal.broadcast_config.v1",
        "type": "broadcast",
        "enabled": str(portal_instance_id or "").strip().lower() == "fnd",
        "title": title,
        "channels": [dict(channel) for channel in _DEFAULT_CHANNELS],
        "members": {
            "source": "progeny_cards",
            "description": "Member cards are sourced from progeny metadata and alias linkage.",
        },
        "homepage_sections": [
            {
                "id": "profile",
                "title": "Profile",
                "description": "Identity and participation context for this broadcast portal.",
            },
            {
                "id": "channels",
                "title": "Channels",
                "description": "Optional engagement surfaces for configured broadcast channels.",
            },
        ],
        "inheritance_rules": {
            "alias_profile_overrides": True,
            "progeny_profile_overrides": True,
            "anthology_reference_mode": "planned",
        },
    }


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(dict(out.get(key) or {}), value)
        else:
            out[key] = value
    return out


def _split_default_and_added(payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    defaults: Dict[str, Any] = {}
    added: Dict[str, Any] = {}
    for key in ("default_values", "defaults"):
        value = payload.get(key)
        if isinstance(value, dict):
            defaults = _deep_merge(defaults, value)
    for key in ("added_values", "added", "overrides"):
        value = payload.get(key)
        if isinstance(value, dict):
            added = _deep_merge(added, value)

    has_only_layer_keys = all(key in {"default_values", "defaults", "added_values", "added", "overrides"} for key in payload.keys())
    if not has_only_layer_keys:
        added = _deep_merge(added, payload)
        for key in ("default_values", "defaults", "added_values", "added", "overrides"):
            added.pop(key, None)
    return defaults, added


def _local_active_private_config(private_dir: Path) -> Dict[str, Any]:
    for path in sorted(private_dir.glob("mycite-config-*.json")):
        try:
            payload = _read_json_relaxed(path)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _broadcast_layers_from_payload(payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    defaults: Dict[str, Any] = {}
    added: Dict[str, Any] = {}

    for layer_key in ("default_values", "defaults"):
        layer = payload.get(layer_key)
        if isinstance(layer, dict):
            section = layer.get("broadcast_config")
            if isinstance(section, dict):
                defaults = _deep_merge(defaults, section)
    for layer_key in ("added_values", "added", "overrides"):
        layer = payload.get(layer_key)
        if isinstance(layer, dict):
            section = layer.get("broadcast_config")
            if isinstance(section, dict):
                added = _deep_merge(added, section)

    direct = payload.get("broadcast_config")
    if isinstance(direct, dict):
        direct_defaults, direct_added = _split_default_and_added(direct)
        defaults = _deep_merge(defaults, direct_defaults)
        added = _deep_merge(added, direct_added)
    return defaults, added


def ensure_broadcast_body_config(
    *,
    private_dir: Path,
    portal_instance_id: str,
    portal_title: str,
    msn_id: str,
) -> Path:
    _ = (portal_instance_id, portal_title, msn_id)
    # Compatibility shim: broadcast config now comes from mycite-config, not private/body.
    return private_dir


def _load_broadcast_config(
    *,
    private_dir: Path,
    portal_instance_id: str,
    portal_title: str,
    msn_id: str,
    active_private_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    config = _default_broadcast_config(portal_instance_id, portal_title, msn_id)
    active_cfg = active_private_config if isinstance(active_private_config, dict) else _local_active_private_config(private_dir)

    defaults: Dict[str, Any] = {}
    added: Dict[str, Any] = {}
    if isinstance(active_cfg, dict) and active_cfg:
        root_defaults, root_added = _broadcast_layers_from_payload(active_cfg)
        defaults = _deep_merge(defaults, root_defaults)
        added = _deep_merge(added, root_added)

        org_cfg = active_cfg.get("organization_config")
        if isinstance(org_cfg, dict):
            org_defaults, org_added = _broadcast_layers_from_payload(org_cfg)
            defaults = _deep_merge(defaults, org_defaults)
            added = _deep_merge(added, org_added)

        progeny_type_configs = active_cfg.get("progeny_type_configs")
        if isinstance(progeny_type_configs, dict):
            broadcast_cfg = progeny_type_configs.get("broadcast")
            if isinstance(broadcast_cfg, dict):
                type_defaults, type_added = _split_default_and_added(broadcast_cfg)
                defaults = _deep_merge(defaults, type_defaults)
                added = _deep_merge(added, type_added)

    config = _deep_merge(config, defaults)
    config = _deep_merge(config, added)

    if not isinstance(config.get("members"), dict):
        config["members"] = _default_broadcast_config(portal_instance_id, portal_title, msn_id)["members"]
    if not isinstance(config.get("homepage_sections"), list):
        config["homepage_sections"] = _default_broadcast_config(portal_instance_id, portal_title, msn_id)[
            "homepage_sections"
        ]
    if not isinstance(config.get("inheritance_rules"), dict):
        config["inheritance_rules"] = _default_broadcast_config(portal_instance_id, portal_title, msn_id)[
            "inheritance_rules"
        ]

    channels = config.get("channels")
    if not isinstance(channels, list) or not channels:
        channels = [dict(channel) for channel in _DEFAULT_CHANNELS]

    normalized_channels: List[Dict[str, Any]] = []
    for raw in channels:
        if isinstance(raw, str):
            channel = {
                "channel_id": _normalize_channel_id(raw),
                "display_name": str(raw).strip() or str(raw),
            }
        elif isinstance(raw, dict):
            channel = dict(raw)
            channel_id = channel.get("channel_id") or channel.get("id") or channel.get("key")
            channel["channel_id"] = _normalize_channel_id(str(channel_id or ""))
            if not channel.get("display_name"):
                channel["display_name"] = str(channel_id or "channel").replace("_", " ").replace("-", " ").title()
        else:
            continue

        if not channel.get("channel_id"):
            continue
        if not isinstance(channel.get("required_fields"), list):
            channel["required_fields"] = []
        normalized_channels.append(channel)

    config["channels"] = normalized_channels
    config["type"] = "broadcast"
    config["schema"] = str(config.get("schema") or "mycite.portal.broadcast_config.v1")
    config["enabled"] = bool(config.get("enabled", str(portal_instance_id).lower() == "fnd"))
    return config


def _extract_alias_id_from_ref(token: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        return ""
    name = Path(raw).name
    if name.endswith(".json"):
        return Path(name).stem
    return name


def _collect_alias_hints(private_dir: Path) -> Dict[str, Dict[str, str]]:
    hints: Dict[str, Dict[str, str]] = {}
    for cfg_path in sorted(private_dir.glob("mycite-config-*.json")):
        try:
            payload = _read_json_relaxed(cfg_path)
        except Exception:
            continue
        alias_entries = payload.get("aliases")
        if not isinstance(alias_entries, list):
            continue
        for entry in alias_entries:
            if not isinstance(entry, dict):
                continue
            for host_msn_id, alias_ref in entry.items():
                alias_id = _extract_alias_id_from_ref(str(alias_ref or ""))
                if not alias_id:
                    continue
                hints.setdefault(alias_id, {})
                hints[alias_id]["host_msn_id"] = str(host_msn_id or "").strip()
                hints[alias_id]["host_title"] = str(host_msn_id or "").strip()
    return hints


def _infer_progeny_type(payload: Dict[str, Any], path: Path) -> str:
    token = str(payload.get("progeny_type") or payload.get("role") or "").strip().lower()
    if token:
        return _canonical_progeny_type(token)
    name = path.name.lower()
    if "board_member" in name:
        return "member"
    if "constituent_farm" in name:
        return "constituent_farm"
    if "poc" in name:
        return "poc"
    if "tenant" in name:
        return "member"
    return "unknown"


def _extract_member_msn_id(payload: Dict[str, Any], path: Path) -> str:
    member = str(
        payload.get("member_msn_id")
        or payload.get("child_msn_id")
        or payload.get("tenant_msn_id")
        or payload.get("msn_id")
        or ""
    ).strip()
    if member:
        return member

    match = re.search(r"progeny-([0-9-]+)-", path.name)
    if match:
        return str(match.group(1) or "").strip()
    return ""


def _extract_display_name(payload: Dict[str, Any], path: Path, member_msn_id: str) -> str:
    display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    return str(
        display.get("title")
        or payload.get("display_name")
        or payload.get("title")
        or payload.get("name")
        or payload.get("label")
        or member_msn_id
        or path.stem
    ).strip()


def _alias_member_msn_id(record: Dict[str, Any]) -> str:
    return str(
        record.get("member_msn_id")
        or record.get("child_msn_id")
        or record.get("member_id")
        or record.get("tenant_id")
        or record.get("tenant_msn_id")
        or record.get("msn_id")
        or ""
    ).strip()


def build_embed_progeny_landing(
    *,
    private_dir: Path,
    alias_records: List[Dict[str, Any]],
    member_msn_id: str,
    as_alias_id: str,
    alias_label_builder: Callable[[Dict[str, Any], Optional[str]], str],
    widget_url_builder: Callable[[str, Dict[str, Any]], str],
    portal_instance_id: str,
    portal_title: str,
    msn_id: str,
    active_private_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    requested_member = str(member_msn_id or "").strip()
    requested_alias = str(as_alias_id or "").strip()

    alias_by_id: Dict[str, Dict[str, Any]] = {}
    for record in alias_records:
        alias_id = str(record.get("alias_id") or "").strip()
        if not alias_id:
            continue
        alias_by_id[alias_id] = record

    alias_hints = _collect_alias_hints(private_dir)
    cards: List[Dict[str, Any]] = []
    dedupe_keys: set[str] = set()

    def _add_card(raw: Dict[str, Any]) -> None:
        key = "|".join(
            [
                str(raw.get("progeny_type") or ""),
                str(raw.get("member_msn_id") or ""),
                str(raw.get("alias_id") or ""),
                str(raw.get("display_name") or ""),
            ]
        )
        if key in dedupe_keys:
            return
        dedupe_keys.add(key)
        cards.append(raw)

    progeny_root = private_dir / "progeny"
    if progeny_root.exists() and progeny_root.is_dir():
        for path in sorted(progeny_root.rglob("*.json")):
            if not path.is_file():
                continue
            try:
                payload = _read_json(path)
            except Exception:
                continue

            progeny_type = _infer_progeny_type(payload, path)
            member_id = _extract_member_msn_id(payload, path)
            display_name = _extract_display_name(payload, path, member_id)

            explicit_alias_id = str(payload.get("alias_id") or payload.get("alias_ref") or "").strip()
            alias_id = _extract_alias_id_from_ref(explicit_alias_id)

            if not alias_id and member_id:
                for candidate_id, candidate in alias_by_id.items():
                    candidate_member = _alias_member_msn_id(candidate)
                    candidate_type = _canonical_progeny_type(str(candidate.get("progeny_type") or "").strip().lower())
                    if candidate_member != member_id:
                        continue
                    if candidate_type and progeny_type != "unknown" and candidate_type != progeny_type:
                        continue
                    alias_id = candidate_id
                    break

            alias_record = alias_by_id.get(alias_id) if alias_id else None
            hint = alias_hints.get(alias_id, {}) if alias_id else {}

            alias_url = f"/portal/alias/{alias_id}" if alias_record is not None and alias_id else ""
            embed_url = widget_url_builder(alias_id, alias_record) if alias_record is not None and alias_id else ""

            _add_card(
                {
                    "card_id": f"progeny:{path.stem}",
                    "progeny_id": str(payload.get("progeny_id") or path.stem),
                    "progeny_type": progeny_type,
                    "member_msn_id": member_id,
                    "display_name": display_name,
                    "alias_id": alias_id,
                    "alias_url": alias_url,
                    "embed_url": embed_url,
                    "status": "eligible" if alias_record is not None else "not_configured",
                    "host_msn_id": str((alias_record or {}).get("alias_host") or hint.get("host_msn_id") or "").strip(),
                    "host_title": str((alias_record or {}).get("host_title") or hint.get("host_title") or "").strip(),
                    "source": "progeny_file",
                    "is_selected": False,
                }
            )

    represented_aliases = {str(card.get("alias_id") or "").strip() for card in cards if str(card.get("alias_id") or "").strip()}
    for alias_id, record in alias_by_id.items():
        if alias_id in represented_aliases:
            continue
        member_id = _alias_member_msn_id(record)
        display_name = alias_label_builder(record, alias_id)
        _add_card(
            {
                "card_id": f"alias:{alias_id}",
                "progeny_id": "",
                "progeny_type": _canonical_progeny_type(str(record.get("progeny_type") or "unknown").strip().lower()),
                "legacy_progeny_type": str(record.get("progeny_type") or "").strip().lower(),
                "member_msn_id": member_id,
                "display_name": display_name,
                "alias_id": alias_id,
                "alias_url": f"/portal/alias/{alias_id}",
                "embed_url": widget_url_builder(alias_id, record),
                "status": "eligible",
                "host_msn_id": str(record.get("alias_host") or "").strip(),
                "host_title": str(record.get("host_title") or "").strip(),
                "source": "alias_record",
                "is_selected": False,
            }
        )

    warnings: List[str] = []
    selected_count = 0
    for card in cards:
        is_selected = False
        if requested_member and str(card.get("member_msn_id") or "").strip() == requested_member:
            is_selected = True
        elif not requested_member and requested_alias and str(card.get("alias_id") or "").strip() == requested_alias:
            is_selected = True
        card["is_selected"] = is_selected
        if is_selected:
            selected_count += 1

    if requested_member and selected_count == 0:
        warnings.append(f"No progeny/member card found for member_msn_id={requested_member}.")

    cards.sort(
        key=lambda card: (
            0 if card.get("is_selected") else 1,
            str(card.get("display_name") or "").lower(),
            str(card.get("member_msn_id") or "").lower(),
            str(card.get("alias_id") or "").lower(),
        )
    )

    broadcast = _load_broadcast_config(
        private_dir=private_dir,
        portal_instance_id=portal_instance_id,
        portal_title=portal_title,
        msn_id=msn_id,
        active_private_config=active_private_config,
    )
    alias_ready_count = sum(1 for card in cards if str(card.get("alias_id") or "").strip())
    member_count = sum(1 for card in cards if str(card.get("member_msn_id") or "").strip())

    normalized_channels: List[Dict[str, Any]] = []
    for raw_channel in broadcast.get("channels") if isinstance(broadcast.get("channels"), list) else []:
        channel = dict(raw_channel) if isinstance(raw_channel, dict) else {}
        channel_id = _normalize_channel_id(str(channel.get("channel_id") or ""))
        if not channel_id:
            continue
        channel["channel_id"] = channel_id
        channel.setdefault("display_name", channel_id.replace("_", " ").replace("-", " ").title())
        if not isinstance(channel.get("required_fields"), list):
            channel["required_fields"] = []

        if channel_id == "keycloak":
            eligible_count = member_count
        else:
            eligible_count = alias_ready_count

        channel["eligible_count"] = eligible_count
        channel["status"] = "eligible" if eligible_count > 0 else "not_configured"
        normalized_channels.append(channel)

    broadcast["channels"] = normalized_channels
    broadcast["summary"] = {
        "members_total": member_count,
        "alias_ready_total": alias_ready_count,
        "cards_total": len(cards),
    }

    return {
        "cards": cards,
        "warnings": warnings,
        "selected_member_msn_id": requested_member,
        "selected_alias_id": requested_alias,
        "broadcast": broadcast,
    }
