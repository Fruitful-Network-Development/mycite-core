"""Read-only datum INFORMATION surface for the datum-editing overlay.

Backs ``GET /portal/api/v2/datum/info``: given a document + datum address, returns the datum's
hyphae abstraction path (its minimum-but-complete dependency closure, in chain order — the
"abstraction path graph") and its computed hyphae value. The overlay's INFORMATION tab renders
the path graph and a "generate hyphae value" control from this payload. No mutation, no side
effects — the closure + hyphae hash are recomputed from the live document on each call.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_semantics.engine import build_document_semantics

from .portal_datum_workbench_mutation_runtime import _document_for_mutation

DATUM_INFO_SCHEMA = "mycite.v2.portal.datum.info.v1"


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def run_datum_info(
    *,
    authority_db_file: str | Path | None,
    portal_instance_id: str,
    document_id: str,
    datum_address: str,
) -> dict[str, Any]:
    document_id = _text(document_id)
    datum_address = _text(datum_address)
    if not document_id or not datum_address:
        return {
            "schema": DATUM_INFO_SCHEMA,
            "ok": False,
            "error": "document_id and address are required",
            "status_code": 400,
        }
    tenant_id = _text(portal_instance_id) or "fnd"
    try:
        store = SqliteSystemDatumStoreAdapter(authority_db_file, allow_legacy_writes=False)
        document = _document_for_mutation(store, tenant_id=tenant_id, document_id=document_id)
    except ValueError as exc:
        return {"schema": DATUM_INFO_SCHEMA, "ok": False, "error": str(exc), "status_code": 404}

    semantics = build_document_semantics(document)
    row = (semantics.get("rows") or {}).get(datum_address)
    if not row:
        return {
            "schema": DATUM_INFO_SCHEMA,
            "ok": False,
            "error": "datum_address_missing",
            "status_code": 404,
        }
    chain = row.get("hyphae_chain") or {}
    path = [
        {
            "datum_address": _text(node.get("datum_address")),
            "semantic_hash": _text(node.get("semantic_hash")),
            "is_target": _text(node.get("datum_address")) == datum_address,
        }
        for node in (chain.get("chain") or [])
    ]
    return {
        "schema": DATUM_INFO_SCHEMA,
        "ok": True,
        "document_id": document_id,
        "datum_address": datum_address,
        "hyphae_hash": row.get("hyphae_hash"),
        "semantic_hash": row.get("semantic_hash"),
        "anchor_context_hash": semantics.get("anchor_context_hash"),
        "local_references": list(row.get("local_references") or []),
        "warnings": list(row.get("warnings") or []),
        "path": path,
        "status_code": 200,
    }
