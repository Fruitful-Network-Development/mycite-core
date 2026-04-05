from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from .actions import SHELL_ACTION_FOCUS_SUBJECT, SHELL_ACTION_OPEN_TOOL, SHELL_ACTION_SET_LENS, action_for_shell_verb, build_shell_action
from .controls import (
    SELECTION_CONTEXT_SCHEMA,
    build_inspector_card,
    build_shell_controls_payload,
    normalize_shell_verb,
)
from .document import DOCUMENT_SCHEMA, build_workbench_document
from .reducer import reduce_shell_action
from .state import DataViewState
from .tool_capabilities import compatible_tools_for_context

TOOL_SANDBOX_MEDIATION_SCOPE = "tool_sandbox"


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
    facet_kind = _text(row.get("facet_kind") or row.get("facet") or "")
    facet_ref = _text(row.get("facet_ref"))
    if row and facet_kind:
        focus_kind = "facet"
    else:
        focus_kind = "datum" if row else "file"
    active_directive = normalize_shell_verb(shell_verb, default="navigate")
    attention_value = row_identifier if row else filename
    intention_value = active_directive if active_directive else "idle"
    archetype_value = _text(resolved.get("family") or resolved.get("type")) if row else ""
    if focus_kind == "facet":
        attention_address = f"facet:{filename}/{row_identifier}/{facet_kind}"
        if facet_ref:
            attention_address = f"{attention_address}/{facet_ref}"
    elif row:
        attention_address = f"datum:{filename}/{row_identifier}"
    else:
        attention_address = f"file:{filename}"
    machine_state = reduce_shell_action(
        DataViewState(
            focus_source="anthology" if row else "auto",
            focus_subject=attention_value or file_key,
            selection={"selected_ref_or_document_id": row_identifier},
            aitas_context={
                "attention": attention_value or file_key,
                "intention": intention_value or "idle",
                "archetype": archetype_value or "",
                "spatial": str(2 if row else 1),
            },
            aitas_phase=active_directive,
        ),
        build_shell_action(
            action_for_shell_verb(active_directive),
            payload={"shell_verb": active_directive},
        ),
    )
    return {
        "focus_kind": focus_kind,
        "active_file_key": file_key,
        "active_filename": filename,
        "active_directive": active_directive,
        "directive": active_directive,
        "attention_address": attention_address,
        "attention_plane": focus_kind,
        "subject": {
            "kind": focus_kind,
            "file": filename,
            "datum_id": row_identifier,
            "datum_label": row_label,
            "facet_kind": facet_kind,
            "facet_ref": facet_ref,
        },
        "selected_datum_id": row_identifier,
        "selected_datum_label": row_label,
        "aitas": {
            "attention": {"kind": focus_kind, "value": attention_value or file_key},
            "intention": {"kind": "directive", "value": intention_value or "idle"},
            "time": {"kind": "placeholder", "value": "null"},
            "archetype": {"kind": "resolved" if archetype_value else "placeholder", "value": archetype_value or "null"},
            "spatial": {"kind": "focus_level", "value": 2 if row else 1},
        },
        "machine_state": machine_state.to_dict(),
        "available_actions": build_shell_controls_payload(active_directive, focus_subject=attention_address),
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
                title="Source Relationship",
                summary=_text(inheritance.get("relation")),
                body=inheritance,
                kind="source_relationship",
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
    mediation_scope: str | None = None,
    shell_surface: str | None = None,
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
    ms = _text(mediation_scope).lower()
    if ms:
        context["mediation_scope"] = ms
    surface = _text(shell_surface).lower()
    if surface:
        context["shell_surface"] = surface
    context["compatible_tools"] = compatible_tools_for_context(tool_tabs, context)
    context["inspector_cards"] = _build_inspector_cards(context)
    context["shell_actions"] = build_shell_controls_payload(
        context.get("shell_verb"),
        focus_subject=context["system_state"].get("attention_address"),
    )
    return context


def build_system_sandbox_context_payload(
    *,
    tool_tabs: list[dict[str, Any]] | None = None,
    portal_instance_context: Any | None = None,
    shell_verb: object = "mediate",
    tool_id: str = "",
) -> dict[str, Any]:
    """Synthetic selected-context for SYSTEM sandbox mediation (no datum/file anchor)."""
    token = _text(tool_id).lower().replace("_", "-")
    sandbox_attention = f"sandbox:utilities/tools/{token}" if token else "sandbox:utilities/tools"
    document = build_workbench_document(
        document_id="workbench:system:tool_sandbox",
        instance_id="system",
        logical_key="portal-tool-sandbox",
        display_name="Portal tool sandbox",
        family_kind="system",
        family_type="tool_sandbox",
        family_subtype="mediation",
        scope_kind="local",
        workspace="system",
        payload={
            "mediation_host_path": "/portal/system",
            "sandbox_root": "private/utilities/tools",
            "tool_id": _text(tool_id).lower(),
            "note": "Synthetic sandbox context for config-context service tools.",
        },
    )
    context = build_selected_context_payload(
        document=document,
        selected_row=None,
        shell_verb=shell_verb,
        tool_tabs=tool_tabs,
        portal_instance_context=portal_instance_context,
        mediation_scope=TOOL_SANDBOX_MEDIATION_SCOPE,
        shell_surface="tool_mediation",
    )
    system_state = context.get("system_state") if isinstance(context.get("system_state"), dict) else {}
    if system_state:
        system_state["focus_kind"] = "sandbox"
        system_state["attention_plane"] = "sandbox"
        system_state["attention_address"] = sandbox_attention
        system_state["active_filename"] = _text(tool_id).lower() or "tool_sandbox"
        system_state["focus_depth"] = 0
        subject = system_state.get("subject") if isinstance(system_state.get("subject"), dict) else {}
        subject.update({"kind": "sandbox", "file": _text(tool_id).lower(), "datum_id": "", "datum_label": ""})
        system_state["subject"] = subject
        aitas = system_state.get("aitas") if isinstance(system_state.get("aitas"), dict) else {}
        spatial = aitas.get("spatial") if isinstance(aitas.get("spatial"), dict) else {}
        spatial.update({"kind": "focus_level", "value": 0})
        attention = aitas.get("attention") if isinstance(aitas.get("attention"), dict) else {}
        attention.update({"kind": "sandbox", "value": sandbox_attention})
        aitas["spatial"] = spatial
        aitas["attention"] = attention
        system_state["aitas"] = aitas
        context["system_state"] = system_state
    return context
