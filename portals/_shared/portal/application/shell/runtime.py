from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from _shared.portal.application.workbench.document_contract import DOCUMENT_SCHEMA

from .contracts import SELECTION_CONTEXT_SCHEMA, build_inspector_card, normalize_shell_verb
from .tools import compatible_tools_for_context


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _row_identity(selected_row: dict[str, Any]) -> tuple[str, str]:
    row_identifier = _text(selected_row.get("identifier") or selected_row.get("datum_id") or selected_row.get("resource_id"))
    row_label = _text(selected_row.get("label") or selected_row.get("title") or selected_row.get("resource_name") or row_identifier)
    return row_identifier, row_label


def _resolved_archetype(document: dict[str, Any], selected_row: dict[str, Any]) -> dict[str, Any]:
    family = _dict(document.get("family"))
    row_source = _text(selected_row.get("source")).lower()
    row_file_key = _text(selected_row.get("file_key")).lower()
    source_family = _text(selected_row.get("family")).lower()
    family_kind = _text(family.get("kind")).lower()
    family_type = _text(family.get("type")).lower()
    if row_file_key == "txa":
        source_family = source_family or "taxonomy"
    elif row_file_key == "msn":
        source_family = source_family or "identity"
    return {
        "family": source_family or family_kind,
        "type": family_type or family_kind,
        "file_key": row_file_key,
        "row_source": row_source,
    }


def _system_state_payload(document: dict[str, Any], selected_row: dict[str, Any], shell_verb: object) -> dict[str, Any]:
    row = _dict(selected_row)
    doc = _dict(document)
    identity = _dict(doc.get("identity"))
    payload = _dict(doc.get("payload"))
    resolved = _resolved_archetype(doc, row)
    file_key = _text(row.get("file_key") or payload.get("file_key") or identity.get("logical_key"))
    filename = _text(row.get("filename") or payload.get("filename") or identity.get("display_name") or file_key)
    row_identifier, row_label = _row_identity(row)
    focus_kind = "datum" if row else "file"
    active_directive = normalize_shell_verb(shell_verb, default="navigate")
    attention_value = row_identifier if row else filename
    intention_value = active_directive if active_directive else "idle"
    archetype_value = _text(resolved.get("family") or resolved.get("type")) if row else ""
    return {
        "focus_kind": focus_kind,
        "active_file_key": file_key,
        "active_filename": filename,
        "active_directive": active_directive,
        "selected_datum_id": row_identifier,
        "selected_datum_label": row_label,
        "aitas": {
            "attention": {
                "kind": focus_kind,
                "value": attention_value or file_key,
            },
            "intention": {
                "kind": "directive",
                "value": intention_value or "idle",
            },
            "time": {
                "kind": "placeholder",
                "value": "null",
            },
            "archetype": {
                "kind": "resolved" if archetype_value else "placeholder",
                "value": archetype_value or "null",
            },
            "spacial": {
                "kind": "focus_level",
                "value": 2 if row else 1,
            },
        },
    }


def _instance_payload(portal_instance_context: Any | None) -> dict[str, Any]:
    if portal_instance_context is None:
        return {}
    if is_dataclass(portal_instance_context):
        payload = asdict(portal_instance_context)
        return {str(key): str(value) for key, value in payload.items()}
    if isinstance(portal_instance_context, dict):
        return {str(key): str(value) for key, value in portal_instance_context.items()}
    return {}


def _build_inspector_cards(context: dict[str, Any]) -> list[dict[str, Any]]:
    document = _dict(context.get("document"))
    selection = _dict(context.get("selection"))
    provenance = _dict(context.get("provenance"))
    inheritance = _dict(context.get("inheritance"))
    compatible_tools = list(context.get("compatible_tools") or [])
    cards = [
        build_inspector_card(
            card_id="selection",
            title="Selection",
            summary=_text(selection.get("display_name") or selection.get("selected_ref_or_document_id")),
            body={
                "selected_ref_or_document_id": _text(selection.get("selected_ref_or_document_id")),
                "selection_kind": _text(selection.get("selection_kind")),
                "document_id": _text(selection.get("document_id")),
                "family": _dict(document.get("family")),
                "scope": _dict(document.get("scope")),
            },
        ),
        build_inspector_card(
            card_id="provenance",
            title="Provenance",
            summary=_text(provenance.get("source_adapter") or provenance.get("source_path")),
            body=provenance,
            kind="provenance",
        ),
    ]
    if inheritance:
        cards.append(
            build_inspector_card(
                card_id="inheritance",
                title="Inheritance",
                summary=_text(inheritance.get("relation")),
                body=inheritance,
                kind="inheritance",
            )
        )
    cards.append(
        build_inspector_card(
            card_id="mediations",
            title="Compatible Mediations",
            summary=f"{len(compatible_tools)} available",
            body={
                "tool_ids": [str(item.get("tool_id") or "") for item in compatible_tools if isinstance(item, dict)],
                "tools": [dict(item) for item in compatible_tools if isinstance(item, dict)],
            },
            kind="mediation",
        )
    )
    return cards


def build_selected_context_payload(
    *,
    document: dict[str, Any],
    selected_row: dict[str, Any] | None = None,
    shell_verb: object = "navigate",
    tool_tabs: list[dict[str, Any]] | None = None,
    portal_instance_context: Any | None = None,
) -> dict[str, Any]:
    normalized_document = _dict(document)
    row = _dict(selected_row)
    row_identifier, row_label = _row_identity(row)
    identity = _dict(normalized_document.get("identity"))
    selected_ref = row_identifier or _text(identity.get("document_id") or identity.get("logical_key"))
    context = {
        "ok": bool(normalized_document),
        "schema": SELECTION_CONTEXT_SCHEMA,
        "document_schema": _text(normalized_document.get("schema")) or DOCUMENT_SCHEMA,
        "selection": {
            "selection_kind": "document_row" if row else "document",
            "selected_ref_or_document_id": selected_ref,
            "document_id": _text(identity.get("document_id")),
            "logical_key": _text(identity.get("logical_key")),
            "display_name": row_label or _text(identity.get("display_name") or identity.get("logical_key")),
            "row_identifier": row_identifier,
            "row_label": row_label,
            "row_reference": _text(row.get("reference")),
            "row_file_key": _text(row.get("file_key")),
        },
        "document": normalized_document,
        "family": _dict(normalized_document.get("family")),
        "scope": _dict(normalized_document.get("scope")),
        "capabilities": _dict(normalized_document.get("capabilities")),
        "resolved_archetype": _resolved_archetype(normalized_document, row),
        "provenance": {
            **_dict(normalized_document.get("provenance")),
            "row_source": _text(row.get("source")),
            "row_address_id": _text(row.get("address_id")),
            "row_reference": _text(row.get("reference")),
        },
        "source_context": {
            "source_kind": "document_row" if row else "document",
            "source_adapter": _text(_dict(normalized_document.get("provenance")).get("source_adapter")),
            "source_scope": _text(_dict(normalized_document.get("scope")).get("kind")),
            "relationship": _text(_dict(normalized_document.get("inheritance")).get("relation") or "primary"),
        },
        "shell_verb": normalize_shell_verb(shell_verb),
        "system_state": _system_state_payload(normalized_document, row, shell_verb),
        "inheritance": _dict(normalized_document.get("inheritance")),
        "portal_instance_context": _instance_payload(portal_instance_context),
    }
    context["compatible_tools"] = compatible_tools_for_context(tool_tabs, context)
    context["inspector_cards"] = _build_inspector_cards(context)
    return context
