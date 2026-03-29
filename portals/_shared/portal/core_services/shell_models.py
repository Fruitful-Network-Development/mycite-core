from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def sanitize_public_profile(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"msn_id", "schema", "title", "public_key", "entity_type", "public_resources", "accessible"}
    out = {k: payload.get(k) for k in allowed if k in payload}
    public_resources = payload.get("public_resources") if isinstance(payload.get("public_resources"), list) else []
    out["public_resources"] = [item for item in public_resources if isinstance(item, dict)]
    out.setdefault("accessible", {})
    return out


def sanitize_fnd_profile(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"schema", "msn_id", "title", "summary", "logo", "banner", "links"}
    out = {key: payload.get(key) for key in allowed if key in payload}
    links = payload.get("links") if isinstance(payload.get("links"), list) else []
    out["links"] = [item for item in links if isinstance(item, dict)]
    return out


def build_portal_profile_model(
    *,
    local_msn_id: str,
    read_json_fn: Callable[[Path], dict[str, Any]],
    resolve_public_profile_path_fn: Callable[[str], Path | None],
    resolve_fnd_profile_path_fn: Callable[[str], Path | None],
) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    token = str(local_msn_id or "").strip()
    if not token:
        return profile

    public_path = resolve_public_profile_path_fn(token)
    if public_path is not None and public_path.exists():
        try:
            payload = read_json_fn(public_path)
            if isinstance(payload, dict):
                profile["public_profile"] = sanitize_public_profile(payload)
                profile["public_profile_source"] = str(public_path)
        except Exception:
            pass

    fnd_path = resolve_fnd_profile_path_fn(token)
    if fnd_path is not None and fnd_path.exists():
        try:
            payload = read_json_fn(fnd_path)
            if isinstance(payload, dict):
                profile["fnd_profile"] = sanitize_fnd_profile(payload)
                profile["fnd_profile_source"] = str(fnd_path)
        except Exception:
            pass
    return profile


def build_network_sidebar_alias_items(
    *,
    private_dir: Path,
    list_aliases_for_sidebar_fn: Callable[[Path], list[dict[str, Any]]],
    alias_label_fn: Callable[[dict[str, Any], str], str],
    extract_member_msn_id_fn: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in list_aliases_for_sidebar_fn(private_dir):
        alias_id = str(record.get("alias_id") or "").strip()
        alias_payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
        member_msn_id = extract_member_msn_id_fn(alias_payload)
        if not member_msn_id:
            continue
        items.append({"alias_id": alias_id, "member_msn_id": member_msn_id, "label": alias_label_fn(alias_payload, alias_id)})
    return items
