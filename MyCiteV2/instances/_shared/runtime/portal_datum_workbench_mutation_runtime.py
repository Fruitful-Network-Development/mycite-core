from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import sandbox_id_for_file_key

DATUM_WORKBENCH_MUTATION_SCHEMA = "mycite.v2.portal.datum_workbench.mutation_result.v1"
_ALLOWED_ACTIONS = {"stage", "validate", "preview", "apply", "discard"}
_ALLOWED_OPERATIONS = {"update_row_raw", "insert_datum", "delete_datum", "move_datum"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _error(code: str, message: str, *, status_code: int = 400) -> dict[str, Any]:
    return {
        "schema": DATUM_WORKBENCH_MUTATION_SCHEMA,
        "ok": False,
        "status_code": status_code,
        "error": {"code": code, "message": message},
    }


def _ok(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": DATUM_WORKBENCH_MUTATION_SCHEMA,
        "ok": True,
        "status_code": 200,
        "action": action,
        **payload,
    }


def _parse_payload_text(payload: Mapping[str, Any]) -> Any:
    if "raw" in payload:
        return payload.get("raw")
    text = _as_text(payload.get("payload_text"))
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _document_sandbox_from_table(
    *,
    authority_db_file: str | Path | None,
    document_id: str,
) -> tuple[str, str]:
    if not authority_db_file:
        return "", ""
    db_path = Path(authority_db_file)
    if not db_path.exists():
        return "", ""
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "select sandbox, legacy_alias from documents where document_id = ? or legacy_alias = ?",
            (document_id, document_id),
        ).fetchone()
    if row is None:
        return "", ""
    return _as_text(row[0]), _as_text(row[1])


def _document_sandbox_id(
    *,
    authority_db_file: str | Path | None,
    document_id: str,
) -> str:
    sandbox, _ = _document_sandbox_from_table(authority_db_file=authority_db_file, document_id=document_id)
    if sandbox:
        return sandbox
    parsed = sandbox_id_for_file_key(document_id)
    return parsed or "system"


def _document_for_mutation(
    store: SqliteSystemDatumStoreAdapter,
    *,
    tenant_id: str,
    document_id: str,
) -> AuthoritativeDatumDocument:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant_id))
    for document in catalog.documents:
        if document.document_id == document_id:
            return document
        metadata = document.document_metadata if isinstance(document.document_metadata, dict) else {}
        if _as_text(metadata.get("legacy_alias")) == document_id:
            return document
    raise ValueError("authoritative_document_missing")


def _replace_row_raw(
    store: SqliteSystemDatumStoreAdapter,
    *,
    tenant_id: str,
    document_id: str,
    datum_address: str,
    raw: Any,
    apply: bool,
) -> dict[str, Any]:
    document = _document_for_mutation(store, tenant_id=tenant_id, document_id=document_id)
    rows: list[AuthoritativeDatumDocumentRow] = []
    found = False
    for row in document.rows:
        row_payload = row.to_dict()
        if row.datum_address == datum_address:
            row_payload["raw"] = raw
            found = True
        rows.append(AuthoritativeDatumDocumentRow.from_dict(row_payload))
    if not found:
        raise ValueError("datum_address_missing")
    updated_document = AuthoritativeDatumDocument(
        document_id=document.document_id,
        source_kind=document.source_kind,
        document_name=document.document_name,
        relative_path=document.relative_path,
        canonical_name=document.canonical_name,
        tool_id=document.tool_id,
        source_authority=document.source_authority,
        document_metadata=document.document_metadata,
        is_anchor=document.is_anchor,
        anchor_document_name=document.anchor_document_name,
        anchor_document_path=document.anchor_document_path,
        anchor_document_metadata=document.anchor_document_metadata,
        anchor_rows=document.anchor_rows,
        rows=tuple(rows),
        warnings=document.warnings,
    )
    result = {
        "operation": "update_row_raw",
        "document_id": document.document_id,
        "datum_address": datum_address,
        "updated_document": updated_document.to_dict(),
    }
    if apply:
        store.replace_authoritative_document(
            tenant_id=tenant_id,
            document_id=document.document_id,
            updated_document=updated_document,
        )
        identity = store.read_document_version_identity(tenant_id=tenant_id, document_id=document.document_id)
        result["persisted_version_hash"] = _as_text((identity or {}).get("version_hash"))
    return result


def _preview_or_apply(
    store: SqliteSystemDatumStoreAdapter,
    *,
    action: str,
    tenant_id: str,
    operation: str,
    document_id: str,
    datum_address: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    apply = action == "apply"
    if operation == "update_row_raw":
        return _replace_row_raw(
            store,
            tenant_id=tenant_id,
            document_id=document_id,
            datum_address=datum_address,
            raw=_parse_payload_text(payload),
            apply=apply,
        )
    if operation == "insert_datum":
        raw = _parse_payload_text(payload)
        target_address = _as_text(payload.get("target_address")) or datum_address
        method = store.apply_document_insert if apply else store.preview_document_insert
        return method(tenant_id=tenant_id, document_id=document_id, target_address=target_address, raw=raw)
    if operation == "delete_datum":
        method = store.apply_document_delete if apply else store.preview_document_delete
        return method(tenant_id=tenant_id, document_id=document_id, target_address=datum_address)
    if operation == "move_datum":
        destination = _as_text(payload.get("destination_address"))
        if not destination:
            raise ValueError("destination_address_required")
        method = store.apply_document_move if apply else store.preview_document_move
        return method(
            tenant_id=tenant_id,
            document_id=document_id,
            source_address=datum_address,
            destination_address=destination,
        )
    raise ValueError("unsupported_operation")


def run_datum_workbench_mutation_action(
    action: str,
    payload: Mapping[str, Any] | None,
    *,
    authority_db_file: str | Path | None,
    portal_instance_id: str,
) -> dict[str, Any]:
    normalized = dict(payload or {})
    action = _as_text(action).lower()
    if action not in _ALLOWED_ACTIONS:
        return _error("unsupported_mutation_action", f"Unsupported datum workbench mutation action: {action}")
    if action == "discard":
        return _ok(action, {"stage_state": "discarded"})
    target_authority = _as_text(normalized.get("target_authority"))
    if target_authority not in {"datum_workbench", "datum_document"}:
        return _error("unsupported_mutation_target", "Mutation target_authority must be datum_workbench.")
    document_id = _as_text(normalized.get("document_id"))
    datum_address = _as_text(normalized.get("datum_address"))
    sandbox_id = _as_text(normalized.get("sandbox_id")) or "system"
    operation = _as_text(normalized.get("operation") or normalized.get("action_kind") or "update_row_raw")
    if operation not in _ALLOWED_OPERATIONS:
        return _error("unsupported_operation", f"Unsupported datum workbench operation: {operation}")
    if not document_id:
        return _error("document_id_required", "document_id is required.")
    if operation != "insert_datum" and not datum_address:
        return _error("datum_address_required", "datum_address is required.")
    actual_sandbox = _document_sandbox_id(authority_db_file=authority_db_file, document_id=document_id)
    if actual_sandbox != sandbox_id:
        return _error(
            "sandbox_document_mismatch",
            f"Document {document_id} belongs to sandbox {actual_sandbox}, not {sandbox_id}.",
        )
    envelope = {
        "verb": "manipulate",
        "target_authority": "datum_workbench",
        "document_id": document_id,
        "target": {
            "sandbox_id": sandbox_id,
            "datum_address": datum_address,
        },
        "operation": operation,
    }
    if action in {"stage", "validate"}:
        return _ok(
            action,
            {
                "stage_state": "staged" if action == "stage" else "validated",
                "nimm_envelope": envelope,
                "validation": {"ok": True, "sandbox_owned": True},
            },
        )
    if authority_db_file is None:
        return _error("authority_db_required", "authority_db_file is required.", status_code=503)
    store = SqliteSystemDatumStoreAdapter(authority_db_file)
    try:
        preview = _preview_or_apply(
            store,
            action=action,
            tenant_id=_as_text(portal_instance_id) or "fnd",
            operation=operation,
            document_id=document_id,
            datum_address=datum_address,
            payload=normalized,
        )
    except ValueError as exc:
        return _error("datum_mutation_failed", str(exc))
    return _ok(
        action,
        {
            "stage_state": "applied" if action == "apply" else "previewed",
            "nimm_envelope": envelope,
            "preview": preview,
        },
    )


__all__ = ["DATUM_WORKBENCH_MUTATION_SCHEMA", "run_datum_workbench_mutation_action"]
