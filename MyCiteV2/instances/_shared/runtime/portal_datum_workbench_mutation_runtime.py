from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_rules import classify_row
from MyCiteV2.packages.core.datum_templates import (
    TemplateRegistry,
    scaffold_from_template,
)
from MyCiteV2.packages.core.document_naming import (
    _sanitize_segment,
    format_canonical_document_id,
)
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import sandbox_id_for_file_key

DATUM_WORKBENCH_MUTATION_SCHEMA = "mycite.v2.portal.datum_workbench.mutation_result.v1"
_ALLOWED_ACTIONS = {"stage", "validate", "preview", "apply", "discard"}
_ALLOWED_OPERATIONS = {
    "update_row_raw",
    "insert_datum",
    "delete_datum",
    "move_datum",
    "scaffold_datum",
    "create_document",
}
# Operations that mint a brand-new document (no pre-existing document_id).
# ``create_document`` is the title-only human-facing flow; ``scaffold_datum``
# remains for template-based import/intake.
_NEW_DOCUMENT_OPERATIONS = {"scaffold_datum", "create_document"}


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


def _reject_malformed_row(datum_address: str, raw: Any) -> None:
    """Reject writes of structurally malformed datum rows.

    Consistent with the engine's reject-non-canonical stance (datum_semantics
    refuses non-canonical families): only HARD malformity blocks. Advisory
    issues such as ``value_group_pair_mismatch`` are well-formed and allowed,
    and legacy ragged rows already in the catalog stay readable — they are
    simply not newly creatable in a malformed shape.
    """
    shape = classify_row(datum_address, raw)
    if not shape.well_formed:
        detail = ", ".join(shape.issues) or shape.shape
        raise ValueError(f"datum row shape is malformed ({detail})")


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


def _scaffold_datum(
    store: SqliteSystemDatumStoreAdapter,
    *,
    tenant_id: str,
    sandbox_id: str,
    payload: Mapping[str, Any],
    apply: bool,
) -> dict[str, Any]:
    template_id = _as_text(payload.get("template_id"))
    if not template_id:
        raise ValueError("template_id_required")
    msn_id = _as_text(payload.get("msn_id"))
    if not msn_id:
        raise ValueError("msn_id_required")
    context = payload.get("context") if isinstance(payload.get("context"), Mapping) else {}
    document_name = _as_text(payload.get("document_name")) or f"scaffold.{template_id}.json"
    relative_path = _as_text(payload.get("relative_path")) or (
        f"sandbox/{sandbox_id.replace('_', '-')}/{document_name}"
    )

    registry = TemplateRegistry()
    template = registry.get(template_id)
    if template is None:
        raise ValueError(f"template_not_found:{template_id}")
    if template.sandbox != sandbox_id:
        raise ValueError(
            f"template_sandbox_mismatch:{template.sandbox}!={sandbox_id}"
        )

    canonical_name = _as_text(payload.get("canonical_name")) or template.template_id
    placeholder_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
        sandbox=sandbox_id,
        name=canonical_name,
        version_hash="0" * 64,
    )
    candidate = scaffold_from_template(
        template,
        msn_id=msn_id,
        document_id=placeholder_id,
        document_name=document_name,
        relative_path=relative_path,
        canonical_name=canonical_name,
        context=context,
    )
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:") :]
    real_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
        sandbox=sandbox_id,
        name=canonical_name,
        version_hash=real_hash,
    )
    final_document = AuthoritativeDatumDocument(
        document_id=real_id,
        source_kind="sandbox_source",
        document_name=document_name,
        relative_path=relative_path,
        canonical_name=canonical_name,
        tool_id=sandbox_id,
        is_anchor=False,
        rows=candidate.rows,
        document_metadata=candidate.document_metadata,
    )

    result = {
        "operation": "scaffold_datum",
        "template_id": template.template_id,
        "document_id": real_id,
        "row_count": final_document.row_count,
        "scaffolded_document": final_document.to_dict(),
    }

    if apply:
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        )
        if any(d.document_id == real_id for d in catalog.documents):
            result["status"] = "already_present"
            return result
        next_documents = (*tuple(catalog.documents), final_document)
        next_catalog = AuthoritativeDatumDocumentCatalogResult(
            tenant_id=catalog.tenant_id,
            documents=next_documents,
            source_files=dict(catalog.source_files),
            readiness_status=dict(catalog.readiness_status),
            warnings=tuple(catalog.warnings),
        )
        store.store_authoritative_catalog(next_catalog)
        result["status"] = "created"
    else:
        result["status"] = "previewed"
    return result


def _create_empty_document(
    store: SqliteSystemDatumStoreAdapter,
    *,
    tenant_id: str,
    sandbox_id: str,
    payload: Mapping[str, Any],
    apply: bool,
) -> dict[str, Any]:
    """Title-only datum-document creation.

    The user supplies only a human title; document shape (rows, columns) is
    authored later inside the document, not chosen at the creation gate. No
    template is required — implementation templates (product_profile, etc.)
    must not leak into the user-facing create flow (review finding).
    """
    msn_id = _as_text(payload.get("msn_id"))
    if not msn_id:
        raise ValueError("msn_id_required")
    title = (
        _as_text(payload.get("document_name"))
        or _as_text(payload.get("canonical_name"))
        or _as_text(payload.get("title"))
    )
    if not title:
        raise ValueError("document_title_required")
    # Sanitize the free-text title into a canonical name segment. A raw title
    # containing '.' or one that strips to empty would otherwise raise
    # CanonicalNameError inside format_canonical_document_id (review finding #2).
    canonical_name = _sanitize_segment(title)

    # An empty document is content-addressed over (source_kind, metadata, rows).
    # With zero rows and no template metadata, two same-titled empty documents
    # would hash identically and the second create would silently dedupe to
    # ``already_present`` (review finding #3). A per-creation nonce in the
    # metadata makes each intentional creation a distinct, addressable document
    # while leaving content-addressing intact for authored rows.
    document_metadata = {
        "source_kind": "sandbox_source",
        "sandbox_id": sandbox_id,
        "title": title,
        "created_at": datetime.now(UTC).isoformat(),
        "creation_nonce": uuid.uuid4().hex,
        "empty_document": True,
    }
    document_name = title if title.endswith(".json") else f"{canonical_name}.json"
    relative_path = _as_text(payload.get("relative_path")) or (
        f"sandbox/{sandbox_id.replace('_', '-')}/{document_name}"
    )

    placeholder_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
        sandbox=sandbox_id,
        name=canonical_name,
        version_hash="0" * 64,
    )
    candidate = AuthoritativeDatumDocument(
        document_id=placeholder_id,
        source_kind="sandbox_source",
        document_name=document_name,
        relative_path=relative_path,
        canonical_name=canonical_name,
        tool_id=sandbox_id,
        is_anchor=False,
        rows=(),
        document_metadata=document_metadata,
    )
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:") :]
    real_id = format_canonical_document_id(
        prefix="lv",
        msn_id=msn_id,
        sandbox=sandbox_id,
        name=canonical_name,
        version_hash=real_hash,
    )
    final_document = AuthoritativeDatumDocument(
        document_id=real_id,
        source_kind="sandbox_source",
        document_name=document_name,
        relative_path=relative_path,
        canonical_name=canonical_name,
        tool_id=sandbox_id,
        is_anchor=False,
        rows=(),
        document_metadata=document_metadata,
    )

    result = {
        "operation": "create_document",
        "document_id": real_id,
        "canonical_name": canonical_name,
        "title": title,
        "row_count": final_document.row_count,
        "scaffolded_document": final_document.to_dict(),
    }
    if apply:
        catalog = store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        )
        if any(d.document_id == real_id for d in catalog.documents):
            result["status"] = "already_present"
            return result
        next_documents = (*tuple(catalog.documents), final_document)
        next_catalog = AuthoritativeDatumDocumentCatalogResult(
            tenant_id=catalog.tenant_id,
            documents=next_documents,
            source_files=dict(catalog.source_files),
            readiness_status=dict(catalog.readiness_status),
            warnings=tuple(catalog.warnings),
        )
        store.store_authoritative_catalog(next_catalog)
        result["status"] = "created"
    else:
        result["status"] = "previewed"
    return result


def _preview_or_apply(
    store: SqliteSystemDatumStoreAdapter,
    *,
    action: str,
    tenant_id: str,
    operation: str,
    document_id: str,
    datum_address: str,
    sandbox_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    apply = action == "apply"
    if operation == "update_row_raw":
        raw = _parse_payload_text(payload)
        _reject_malformed_row(datum_address, raw)
        return _replace_row_raw(
            store,
            tenant_id=tenant_id,
            document_id=document_id,
            datum_address=datum_address,
            raw=raw,
            apply=apply,
        )
    if operation == "insert_datum":
        raw = _parse_payload_text(payload)
        target_address = _as_text(payload.get("target_address")) or datum_address
        _reject_malformed_row(target_address, raw)
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
    if operation == "scaffold_datum":
        return _scaffold_datum(
            store,
            tenant_id=tenant_id,
            sandbox_id=sandbox_id,
            payload=payload,
            apply=apply,
        )
    if operation == "create_document":
        return _create_empty_document(
            store,
            tenant_id=tenant_id,
            sandbox_id=sandbox_id,
            payload=payload,
            apply=apply,
        )
    raise ValueError("unsupported_operation")


def run_datum_workbench_mutation_action(
    action: str,
    payload: Mapping[str, Any] | None,
    *,
    authority_db_file: str | Path | None,
    portal_instance_id: str,
    private_dir: str | Path | None = None,
) -> dict[str, Any]:
    normalized = dict(payload or {})
    # Newsletter/contact-log + sender mutations resolve their filesystem store
    # from ``private_dir``. Inject the caller's private dir (without clobbering
    # an explicit payload value) so every writer lands in the one canonical
    # tree the dashboard reads.
    if private_dir is not None and not _as_text(normalized.get("private_dir")):
        normalized["private_dir"] = str(private_dir)
    action = _as_text(action).lower()
    if action not in _ALLOWED_ACTIONS:
        return _error("unsupported_mutation_action", f"Unsupported datum workbench mutation action: {action}")
    if action == "discard":
        return _ok(action, {"stage_state": "discarded"})
    target_authority = _as_text(normalized.get("target_authority"))
    if target_authority in _NEWSLETTER_TARGET_AUTHORITIES:
        return _run_newsletter_mutation_action(
            action=action,
            target_authority=target_authority,
            payload=normalized,
            authority_db_file=authority_db_file,
            portal_instance_id=portal_instance_id,
        )
    if target_authority not in {"datum_workbench", "datum_document"}:
        return _error("unsupported_mutation_target", "Mutation target_authority must be datum_workbench.")
    document_id = _as_text(normalized.get("document_id"))
    datum_address = _as_text(normalized.get("datum_address"))
    sandbox_id = _as_text(normalized.get("sandbox_id")) or "system"
    operation = _as_text(normalized.get("operation") or normalized.get("action_kind") or "update_row_raw")
    if operation not in _ALLOWED_OPERATIONS:
        return _error("unsupported_operation", f"Unsupported datum workbench operation: {operation}")
    if operation in _NEW_DOCUMENT_OPERATIONS:
        # Scaffold (and similar) mint a brand-new document; the existing-doc
        # sandbox check would always miss. Validate by template/sandbox match
        # inside the operation handler instead.
        pass
    else:
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
    # allow_legacy_writes stays True while the legacy-id back-compat contract is
    # live (legacy_alias reads + legacy-keyed test fixtures). Live data is fully
    # canonical; flip to False with the 2026-06-05 legacy_alias retirement.
    store = SqliteSystemDatumStoreAdapter(authority_db_file, allow_legacy_writes=True)
    try:
        preview = _preview_or_apply(
            store,
            action=action,
            tenant_id=_as_text(portal_instance_id) or "fnd",
            operation=operation,
            document_id=document_id,
            datum_address=datum_address,
            sandbox_id=sandbox_id,
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


_NEWSLETTER_TARGET_AUTHORITIES = frozenset(
    {
        "newsletter_contact_log",
        "newsletter_profile",
        "paypal_webhook",
    }
)
_NEWSLETTER_OPERATIONS = frozenset(
    {
        "upsert_subscriber",
        # Phase 16a: operator-side inline row edit for the newsletter
        # Contacts table. Updates non-subscription fields only.
        "edit_subscriber",
        # Phase 17a: Connect-form submission. Upserts a contact with
        # subscribed=false, source=connect_form, plus subject+message
        # so the operator sees the full record in the Connect tab.
        "submit_connect_form",
        "mark_unsubscribed",
        "update_subscription",
        "record_dispatch_result",
        "assign_sender",
        "save_webhook",
    }
)


def _run_newsletter_mutation_action(
    *,
    action: str,
    target_authority: str,
    payload: Mapping[str, Any],
    authority_db_file: str | Path | None,
    portal_instance_id: str,
) -> dict[str, Any]:
    """Dispatch AWS-CSM-family mutations through the canonical lifecycle.

    Replaces direct adapter ``save_*()`` calls scattered across the
    runtime + public ``/__fnd/newsletter/*`` endpoints with one
    canonical entry point. Every FND-CSM mutation now goes through this
    function, so the NIMM directive envelope is composed identically
    regardless of caller.
    """
    operation = _as_text(payload.get("operation"))
    if operation not in _NEWSLETTER_OPERATIONS:
        return _error(
            "unsupported_operation",
            f"Unsupported AWS-CSM mutation operation: {operation}",
        )
    envelope = {
        "verb": "manipulate",
        "target_authority": target_authority,
        "operation": operation,
        "target": dict(payload.get("target") or {}),
    }
    if action == "stage":
        return _ok(action, {"stage_state": "staged", "nimm_envelope": envelope})
    if action == "validate":
        return _ok(
            action,
            {
                "stage_state": "validated",
                "nimm_envelope": envelope,
                "validation": {"ok": True},
            },
        )
    if authority_db_file is None:
        return _error("authority_db_required", "authority_db_file is required.", status_code=503)
    tenant_id = _as_text(portal_instance_id) or "fnd"

    try:
        result = _newsletter_apply_or_preview(
            target_authority=target_authority,
            operation=operation,
            payload=payload,
            authority_db_file=authority_db_file,
            tenant_id=tenant_id,
            apply=(action == "apply"),
        )
    except ValueError as exc:
        return _error("aws_mutation_failed", str(exc))
    except Exception as exc:
        return _error("aws_mutation_error", str(exc), status_code=500)
    return _ok(
        action,
        {
            "stage_state": "applied" if action == "apply" else "previewed",
            "nimm_envelope": envelope,
            "preview": result,
        },
    )


def _newsletter_apply_or_preview(
    *,
    target_authority: str,
    operation: str,
    payload: Mapping[str, Any],
    authority_db_file: str | Path,
    tenant_id: str,
    apply: bool,
) -> dict[str, Any]:
    """Execute the operation against the appropriate MOS adapter.

    For ``preview`` actions (apply=False), the operation runs in a
    read-only fashion when possible. For mutations where preview would
    require materializing the change (e.g. computing the next version
    hash), we just return the planned action — the actual write
    happens on ``apply``.
    """
    from MyCiteV2.packages.adapters.filesystem import (
        FilesystemNewsletterStateAdapter,
    )
    from MyCiteV2.packages.domain import canonical_contact_entry, split_legacy_name

    if target_authority == "newsletter_contact_log":
        domain = _as_text(payload.get("domain"))
        if not domain:
            raise ValueError("domain is required for newsletter contact log mutations")
        # Single canonical store, rooted at the live private dir — the same
        # tree the dashboard reads. (The retired MosDatum shim derived a
        # doubled ``private/private`` path from the authority-db location.)
        private_dir = _as_text(payload.get("private_dir"))
        if not private_dir:
            raise ValueError("private_dir is required for newsletter contact log mutations")
        adapter = FilesystemNewsletterStateAdapter(private_dir)
        if operation == "upsert_subscriber":
            email = _as_text(payload.get("email")).lower()
            if not email:
                raise ValueError("email is required for upsert_subscriber")
            # source="operator" => an operator added the row from the admin
            # surface; a website self-signup carries no source.
            source = _as_text(payload.get("source"))
            is_operator = source == "operator"
            first_name = _as_text(payload.get("first_name"))
            middle_name = _as_text(payload.get("middle_name"))
            last_name = _as_text(payload.get("last_name"))
            name = _as_text(payload.get("name"))
            if not (first_name or middle_name or last_name) and name:
                first_name, middle_name, last_name = split_legacy_name(name)
            now_iso = _now_iso()
            today_date = now_iso[:10] if len(now_iso) >= 10 else now_iso
            log = adapter.load_contact_log(domain=domain)
            if not log:
                # Empty means either no file yet (safe to start fresh) or a file
                # exists but didn't load (unaccepted schema / parse error). In the
                # latter case, saving a fresh list would DROP every existing
                # contact, so refuse rather than silently lose data.
                if adapter.contact_log_present(domain=domain):
                    raise ValueError("contact_log_unreadable")
                log = {"domain": domain, "contacts": [], "dispatches": []}
            contacts = list(log.get("contacts") or [])
            index = next(
                (
                    i
                    for i, c in enumerate(contacts)
                    if _as_text(c.get("email")).lower() == email
                ),
                None,
            )
            existing = contacts[index] if index is not None else None
            patch: dict[str, Any] = {
                "email": email,
                "name": name,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "phone": _as_text(payload.get("phone")),
                "zip": _as_text(payload.get("zip")),
                "organization": _as_text(payload.get("organization")),
            }
            if existing is None:
                # New contact: stamp acquisition source + first-seen date, opt in.
                patch["source"] = source or "website_signup"
                patch["signup_date"] = _as_text(payload.get("signup_date")) or today_date
                patch["subscribed"] = True
            elif not is_operator:
                # Website re-signup re-opts-in an existing contact.
                patch["subscribed"] = True
            # Operator add of an EXISTING contact: leave subscribed / source /
            # signup_date untouched — never resurrect an opt-out.
            row = canonical_contact_entry(existing=existing, patch=patch, now=now_iso)
            if index is not None:
                contacts[index] = row
            else:
                contacts.append(row)
            log["contacts"] = contacts
            log["updated_at"] = now_iso
            if apply:
                adapter.save_contact_log(domain=domain, payload=log)
            return {
                "operation": operation,
                "domain": domain,
                "email": email,
                "subscribed": row["subscribed"],
                "applied": apply,
                "contact_count": len(contacts),
            }
        if operation == "edit_subscriber":
            # Operator-side row edit. Patches the named identity fields on an
            # existing contact without changing subscribed state. Empty values
            # are ignored (no clobber). Raises if the contact doesn't exist.
            email = _as_text(payload.get("email")).lower()
            if not email:
                raise ValueError("email is required for edit_subscriber")
            log = adapter.load_contact_log(domain=domain)
            if not log:
                raise ValueError("contact_log_missing_for_domain")
            now_iso = _now_iso()
            patch: dict[str, Any] = {"email": email}
            updated_fields: list[str] = []
            for key in (
                "first_name",
                "middle_name",
                "last_name",
                "phone",
                "zip",
                "organization",
                "signup_date",
                # forward_status stays editable so operators can mark a record
                # sent after a manual retry.
                "forward_status",
            ):
                if key in payload:
                    patch[key] = _as_text(payload.get(key))
                    updated_fields.append(key)
            contacts = list(log.get("contacts") or [])
            index = next(
                (
                    i
                    for i, c in enumerate(contacts)
                    if _as_text(c.get("email")).lower() == email
                ),
                None,
            )
            if index is None:
                raise ValueError("contact_not_found")
            contacts[index] = canonical_contact_entry(
                existing=contacts[index], patch=patch, now=now_iso
            )
            log["contacts"] = contacts
            log["updated_at"] = now_iso
            if apply:
                adapter.save_contact_log(domain=domain, payload=log)
            return {
                "operation": operation,
                "domain": domain,
                "email": email,
                "applied": apply,
                "updated_fields": updated_fields,
            }
        if operation == "submit_connect_form":
            # A website visitor used the Connect form. Land/refresh the contact
            # with source=connect_form, the latest forward_status, and the
            # submitted subject + message so the operator can read it from the
            # dashboard. A new contact lands UNSUBSCRIBED (they opt into the
            # newsletter separately); an existing subscriber keeps their state.
            email = _as_text(payload.get("email")).lower()
            if not email:
                raise ValueError("email is required for submit_connect_form")
            now_iso = _now_iso()
            today_date = now_iso[:10] if len(now_iso) >= 10 else now_iso
            log = adapter.load_contact_log(domain=domain)
            if not log:
                # Empty means either no file yet (safe to start fresh) or a file
                # exists but didn't load (unaccepted schema / parse error). In the
                # latter case, saving a fresh list would DROP every existing
                # contact, so refuse rather than silently lose data.
                if adapter.contact_log_present(domain=domain):
                    raise ValueError("contact_log_unreadable")
                log = {"domain": domain, "contacts": [], "dispatches": []}
            contacts = list(log.get("contacts") or [])
            index = next(
                (
                    i
                    for i, c in enumerate(contacts)
                    if _as_text(c.get("email")).lower() == email
                ),
                None,
            )
            existing = contacts[index] if index is not None else None
            patch: dict[str, Any] = {
                "email": email,
                "first_name": _as_text(payload.get("first_name")),
                "middle_name": _as_text(payload.get("middle_name")),
                "last_name": _as_text(payload.get("last_name")),
                "phone": _as_text(payload.get("phone")),
                "zip": _as_text(payload.get("zip")),
                "organization": _as_text(payload.get("organization")),
                "subject": _as_text(payload.get("subject")),
                "message": _as_text(payload.get("message")),
                "forward_status": _as_text(payload.get("forward_status")),
                "source": "connect_form",
                "last_contacted_at": now_iso,
            }
            if existing is None:
                patch["signup_date"] = today_date
                patch["subscribed"] = False
            row = canonical_contact_entry(existing=existing, patch=patch, now=now_iso)
            if index is not None:
                contacts[index] = row
            else:
                contacts.append(row)
            log["contacts"] = contacts
            log["updated_at"] = now_iso
            if apply:
                adapter.save_contact_log(domain=domain, payload=log)
            return {
                "operation": operation,
                "domain": domain,
                "email": email,
                "subscribed": row["subscribed"],
                "forward_status": row["forward_status"],
                "applied": apply,
                "contact_count": len(contacts),
            }
        if operation == "mark_unsubscribed":
            email = _as_text(payload.get("email")).lower()
            if not email:
                raise ValueError("email is required for mark_unsubscribed")
            # A missing/empty log just means the email isn't on the list — that
            # is matched=False (the caller returns 404), not a 500.
            log = adapter.load_contact_log(domain=domain) or {}
            now_iso = _now_iso()
            matched = False
            for c in log.get("contacts") or []:
                if _as_text(c.get("email")).lower() == email:
                    c["subscribed"] = False
                    c["source"] = "unsubscribe_link"
                    c["unsubscribed_at"] = now_iso
                    c["updated_at"] = now_iso
                    matched = True
            log["updated_at"] = now_iso
            if apply and matched:
                adapter.save_contact_log(domain=domain, payload=log)
            return {
                "operation": operation,
                "domain": domain,
                "email": email,
                "subscribed": False,
                "applied": apply and matched,
                "matched": matched,
            }
        if operation == "record_dispatch_result":
            email = _as_text(payload.get("email")).lower()
            status = _as_text(payload.get("status")).lower()
            message_id = _as_text(payload.get("message_id"))
            error_message = _as_text(payload.get("error_message"))
            if not email:
                raise ValueError("email is required for record_dispatch_result")
            log = adapter.load_contact_log(domain=domain)
            if not log:
                raise ValueError("contact_log_missing_for_domain")
            now_iso = _now_iso()
            matched = False
            for c in log.get("contacts") or []:
                if _as_text(c.get("email")).lower() != email:
                    continue
                matched = True
                if status == "sent":
                    c["last_newsletter_sent_at"] = now_iso
                    c["send_count"] = int(c.get("send_count") or 0) + 1
                c["updated_at"] = now_iso
                if message_id:
                    c["last_message_id"] = message_id
                if error_message:
                    c["last_error"] = error_message
            log["updated_at"] = now_iso
            if apply and matched:
                adapter.save_contact_log(domain=domain, payload=log)
            return {
                "operation": operation,
                "domain": domain,
                "email": email,
                "status": status,
                "matched": matched,
                "applied": apply and matched,
            }
        if operation == "update_subscription":
            email = _as_text(payload.get("email")).lower()
            subscribed_value = bool(payload.get("subscribed"))
            if not email:
                raise ValueError("email is required for update_subscription")
            log = adapter.load_contact_log(domain=domain)
            if not log:
                raise ValueError("contact_log_missing_for_domain")
            matched = False
            for c in log.get("contacts") or []:
                if _as_text(c.get("email")).lower() == email:
                    c["subscribed"] = subscribed_value
                    matched = True
            if apply and matched:
                adapter.save_contact_log(domain=domain, payload=log)
            return {
                "operation": operation,
                "domain": domain,
                "email": email,
                "subscribed": subscribed_value,
                "matched": matched,
                "applied": apply and matched,
            }
        raise ValueError(f"unsupported_newsletter_contact_log_operation:{operation}")

    if target_authority == "newsletter_profile":
        if operation == "assign_sender":
            domain = _as_text(payload.get("domain")).lower()
            sender = _as_text(payload.get("sender_address")).lower()
            if not domain or not sender:
                raise ValueError("domain and sender_address are required for assign_sender")
            # Sender assignment still goes through the filesystem newsletter
            # adapter (the v2 contact log datum doesn't carry sender info).
            # When the sender-profile datum lands as part of a future
            # migration, swap this path.
            from MyCiteV2.packages.adapters.filesystem import (
                FilesystemNewsletterStateAdapter,
            )

            private_dir = _as_text(payload.get("private_dir"))
            if not private_dir:
                raise ValueError("private_dir is required for assign_sender")
            fs_adapter = FilesystemNewsletterStateAdapter(private_dir)
            profile = dict(fs_adapter.load_profile(domain=domain) or {})
            profile["selected_sender_address"] = sender
            if apply:
                fs_adapter.save_profile(domain=domain, payload=profile)
            return {
                "operation": operation,
                "domain": domain,
                "sender_address": sender,
                "applied": apply,
            }
        raise ValueError(f"unsupported_newsletter_profile_operation:{operation}")

    if target_authority == "paypal_webhook":
        if operation == "save_webhook":
            from MyCiteV2.packages.adapters.sql.fnd_paypal import (
                MosDatumPayPalWebhookAdapter,
            )

            grantee_msn = _as_text(payload.get("grantee_msn_id"))
            webhook_url = _as_text(payload.get("webhook_url"))
            if not grantee_msn:
                raise ValueError("grantee_msn_id is required for save_webhook")
            adapter = MosDatumPayPalWebhookAdapter(
                authority_db_file=authority_db_file, tenant_id=tenant_id
            )
            if apply:
                adapter.save_webhook(grantee_msn_id=grantee_msn, webhook_url=webhook_url)
            return {
                "operation": operation,
                "grantee_msn_id": grantee_msn,
                "webhook_url": webhook_url,
                "applied": apply,
            }
        raise ValueError(f"unsupported_paypal_webhook_operation:{operation}")

    raise ValueError(f"unsupported_target_authority:{target_authority}")


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()


_DOCUMENT_ACTION_KINDS = {"rename_document", "delete_document"}


def run_document_workbench_action(
    action_kind: str,
    payload: Mapping[str, Any] | None,
    *,
    authority_db_file: str | Path | None,
    portal_instance_id: str,
) -> dict[str, Any]:
    normalized = dict(payload or {})
    action_kind = _as_text(action_kind).lower()
    if action_kind not in _DOCUMENT_ACTION_KINDS:
        return _error("unsupported_document_action", f"Unsupported document workbench action: {action_kind}")
    if authority_db_file is None:
        return _error("authority_db_required", "authority_db_file is required.", status_code=503)
    document_id = _as_text(normalized.get("document_id"))
    if not document_id:
        return _error("document_id_required", "document_id is required.")
    # allow_legacy_writes stays True while the legacy-id back-compat contract is
    # live (legacy_alias reads + legacy-keyed test fixtures). Live data is fully
    # canonical; flip to False with the 2026-06-05 legacy_alias retirement.
    store = SqliteSystemDatumStoreAdapter(authority_db_file, allow_legacy_writes=True)
    tenant_id = _as_text(portal_instance_id) or "fnd"
    try:
        document = _document_for_mutation(store, tenant_id=tenant_id, document_id=document_id)
    except ValueError as exc:
        return _error("document_not_found", str(exc))
    if action_kind == "rename_document":
        new_name = _as_text(normalized.get("new_name"))
        if not new_name:
            return _error("new_name_required", "new_name is required.")
        updated_document = AuthoritativeDatumDocument(
            document_id=document.document_id,
            source_kind=document.source_kind,
            document_name=new_name,
            relative_path=document.relative_path,
            canonical_name=new_name,
            tool_id=document.tool_id,
            source_authority=document.source_authority,
            document_metadata=document.document_metadata,
            is_anchor=document.is_anchor,
            anchor_document_name=document.anchor_document_name,
            anchor_document_path=document.anchor_document_path,
            anchor_document_metadata=document.anchor_document_metadata,
            anchor_rows=document.anchor_rows,
            rows=document.rows,
            warnings=document.warnings,
        )
        try:
            store.replace_authoritative_document(
                tenant_id=tenant_id,
                document_id=document.document_id,
                updated_document=updated_document,
            )
        except ValueError as exc:
            return _error("rename_failed", str(exc))
        return _ok("rename_document", {"document_id": document.document_id, "new_name": new_name})
    if action_kind == "delete_document":
        if document.is_anchor:
            return _error("anchor_delete_forbidden", "Anchor documents cannot be deleted.", status_code=403)
        try:
            store.delete_authoritative_document(tenant_id=tenant_id, document_id=document.document_id)
        except ValueError as exc:
            return _error("delete_failed", str(exc))
        return _ok("delete_document", {"document_id": document.document_id, "deleted": True})
    return _error("unsupported_document_action", f"Unsupported document workbench action: {action_kind}")


__all__ = [
    "DATUM_WORKBENCH_MUTATION_SCHEMA",
    "run_datum_workbench_mutation_action",
    "run_document_workbench_action",
]
