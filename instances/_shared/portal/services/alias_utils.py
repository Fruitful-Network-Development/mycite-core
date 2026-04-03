from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable


def format_sidebar_entity_title(raw: str) -> str:
    token = re.sub(r"[_-]+", " ", str(raw or "").strip())
    token = re.sub(r"\s+", " ", token).strip()
    return token.upper()


def alias_label(alias_payload: dict[str, Any], alias_id: str | None = None) -> str:
    host_title = str(alias_payload.get("host_title") or "").strip()
    if host_title:
        return format_sidebar_entity_title(host_title)
    if alias_id:
        return format_sidebar_entity_title(alias_id)
    return "UNNAMED ALIAS"


def canonical_progeny_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if token in {"board_member", "constituent_farm", "tenant"}:
        return "member"
    if token == "poc":
        return "admin"
    return token


def extract_tenant_msn_id(alias_payload: dict[str, Any]) -> str:
    return str(alias_payload.get("child_msn_id") or alias_payload.get("tenant_id") or "").strip()


def extract_contract_id(alias_payload: dict[str, Any]) -> str:
    return str(alias_payload.get("contract_id") or alias_payload.get("symmetric_key_contract") or "").strip()


def extract_member_msn_id(alias_payload: dict[str, Any]) -> str:
    return str(
        alias_payload.get("member_msn_id")
        or alias_payload.get("child_msn_id")
        or alias_payload.get("tenant_id")
        or alias_payload.get("msn_id")
        or ""
    ).strip()


def alias_contact_collection_ref(record: dict[str, Any]) -> str:
    profile_refs = record.get("profile_refs") if isinstance(record.get("profile_refs"), dict) else {}
    alias_ref = str(profile_refs.get("contact_collection_ref") or "").strip()
    if alias_ref:
        return alias_ref
    tenant_progeny = record.get("tenant_progeny") if isinstance(record.get("tenant_progeny"), dict) else {}
    tenant_refs = tenant_progeny.get("profile_refs") if isinstance(tenant_progeny.get("profile_refs"), dict) else {}
    progeny_ref = str(tenant_refs.get("contact_collection_ref") or "").strip()
    if progeny_ref:
        return progeny_ref
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    return str(fields.get("contact_collection_ref") or "").strip()


def list_aliases_for_sidebar(
    private_dir: Path,
    *,
    list_alias_records_fn: Callable[[Path], tuple[list[dict[str, Any]], dict[str, Any]]],
) -> list[dict[str, Any]]:
    records, _ = list_alias_records_fn(private_dir)
    aliases: list[dict[str, Any]] = []
    for record in records:
        alias_id = str(record.get("alias_id") or "").strip()
        if not alias_id:
            continue
        aliases.append(
            {
                "alias_id": alias_id,
                "label": alias_label(record, alias_id),
                "org_title": str(record.get("host_title") or "").strip(),
                "org_msn_id": str(record.get("alias_host") or "").strip(),
                "contract_id": str(record.get("contract_id") or "").strip(),
                "progeny_type": canonical_progeny_type(str(record.get("progeny_type") or "").strip()),
                "tenant_id": str(record.get("child_msn_id") or record.get("tenant_id") or "").strip(),
                "member_id": extract_member_msn_id(record),
                "contact_collection_ref": alias_contact_collection_ref(record),
            }
        )
    return aliases
