from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlencode


def sanitize_env_suffix(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", value).upper()


def resolve_embed_port(
    alias_host: str,
    *,
    known_embed_port_by_msn: dict[str, str],
    default_port: str,
) -> str:
    host = (alias_host or "").strip()
    if host:
        per_host_key = f"EMBED_HOST_PORT_{sanitize_env_suffix(host)}"
        if os.environ.get(per_host_key):
            return str(os.environ.get(per_host_key)).strip()
        known = known_embed_port_by_msn.get(host)
        if known:
            return known
    if os.environ.get("EMBED_HOST_PORT"):
        return str(os.environ.get("EMBED_HOST_PORT")).strip()
    return default_port


def build_widget_url(
    *,
    alias_id: str,
    alias_payload: dict[str, Any],
    local_msn_id: str,
    known_embed_port_by_msn: dict[str, str],
    default_embed_port: str,
    canonical_progeny_type_fn,
    extract_tenant_msn_id_fn,
    extract_contract_id_fn,
    extract_member_msn_id_fn,
    local_member_path: str,
    remote_member_path: str,
    local_member_tab: str,
    remote_member_tab: str,
    support_tenant_embed: bool,
    request_host_url: str | None,
) -> str:
    org_msn_id = str(alias_payload.get("alias_host") or "").strip()
    org_title = str(alias_payload.get("host_title") or "").strip()
    if org_msn_id and local_msn_id and org_msn_id != local_msn_id:
        url_key = f"EMBED_HOST_URL_{sanitize_env_suffix(org_msn_id)}"
        base_url = (os.environ.get(url_key) or "").strip().rstrip("/")
        if not base_url:
            embed_port = resolve_embed_port(
                org_msn_id,
                known_embed_port_by_msn=known_embed_port_by_msn,
                default_port=default_embed_port,
            )
            base_url = f"http://127.0.0.1:{embed_port}"
    else:
        if request_host_url:
            base_url = request_host_url.rstrip("/")
        else:
            embed_port = resolve_embed_port(
                org_msn_id,
                known_embed_port_by_msn=known_embed_port_by_msn,
                default_port=default_embed_port,
            )
            base_url = f"http://127.0.0.1:{embed_port}"

    progeny_type = canonical_progeny_type_fn(str(alias_payload.get("progeny_type") or "").strip().lower())
    tenant_msn_id = extract_tenant_msn_id_fn(alias_payload)
    member_msn_id = extract_member_msn_id_fn(alias_payload)

    if support_tenant_embed and str(alias_payload.get("progeny_type") or "").strip().lower() == "tenant" and tenant_msn_id:
        query = urlencode(
            {
                "tenant_msn_id": tenant_msn_id,
                "contract_id": extract_contract_id_fn(alias_payload),
                "as_alias_id": alias_id,
            }
        )
        return f"{base_url}/portal/embed/tenant?{query}"

    if progeny_type == "member" and member_msn_id:
        is_remote = bool(org_msn_id and local_msn_id and org_msn_id != local_msn_id)
        target_path = remote_member_path if is_remote else local_member_path
        tab = remote_member_tab if is_remote else local_member_tab
        query = urlencode({"member_msn_id": member_msn_id, "as_alias_id": alias_id, "tab": tab})
        return f"{base_url}{target_path}?{query}"

    query = urlencode({"org_msn_id": org_msn_id, "as_alias_id": alias_id, "org_title": org_title})
    return f"{base_url}/portal/embed/poc?{query}"
