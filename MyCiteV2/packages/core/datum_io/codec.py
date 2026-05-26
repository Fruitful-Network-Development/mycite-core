"""Conventionalized datum-document YAML codec (transport only).

Serializes an :class:`AuthoritativeDatumDocument` to a human-readable YAML form
and back, for transformation / extraction / ingestion pipelines that apply MOS
and datum rules step by step. This is a TRANSPORT format only: the MOS database
remains the canonical authority (see the MOS-only datum storage rule); nothing
here writes datum state to disk.

Round-trip guarantee: ``from_yaml(to_yaml(document))`` preserves the MSS version
identity (``compute_mss_hash``), because ``source_kind``, ``document_metadata``,
and every row's ``{datum_address, raw}`` are carried verbatim.
"""

from __future__ import annotations

from typing import Any

import yaml

from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

DATUM_IO_SCHEMA = "mycite.v2.datum_io.document.v1"

_VALID_SOURCE_KINDS = ("system_anthology", "sandbox_source")


def _row_mapping(row: Any) -> dict[str, Any]:
    if isinstance(row, AuthoritativeDatumDocumentRow):
        return {"address": row.datum_address, "raw": row.raw}
    if isinstance(row, dict):
        return {"address": row.get("datum_address"), "raw": row.get("raw")}
    raise ValueError(f"unserializable datum row: {row!r}")


def to_yaml(document: AuthoritativeDatumDocument) -> str:
    """Render a datum document as conventionalized YAML text."""

    payload: dict[str, Any] = {
        "schema": DATUM_IO_SCHEMA,
        "document_id": document.document_id,
        "document_name": document.document_name,
        "canonical_name": document.canonical_name,
        "relative_path": document.relative_path,
        "source_kind": document.source_kind,
        "source_authority": document.source_authority,
        "tool_id": document.tool_id,
        "is_anchor": document.is_anchor,
        "document_metadata": document.document_metadata or {},
        "rows": [_row_mapping(row) for row in document.rows],
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, default_flow_style=False)


def from_yaml(text: str) -> AuthoritativeDatumDocument:
    """Reconstruct a datum document from conventionalized YAML text."""

    payload = yaml.safe_load(text) or {}
    if not isinstance(payload, dict):
        raise ValueError("datum_io payload must be a mapping")

    source_kind = str(payload.get("source_kind") or "sandbox_source")
    if source_kind not in _VALID_SOURCE_KINDS:
        raise ValueError(f"datum_io source_kind must be one of {_VALID_SOURCE_KINDS}: {source_kind!r}")

    rows = tuple(
        AuthoritativeDatumDocumentRow(
            datum_address=str((entry or {}).get("address") or ""),
            raw=(entry or {}).get("raw"),
        )
        for entry in (payload.get("rows") or [])
    )
    metadata = payload.get("document_metadata") or {}
    return AuthoritativeDatumDocument(
        document_id=str(payload.get("document_id") or ""),
        source_kind=source_kind,
        document_name=str(payload.get("document_name") or ""),
        relative_path=str(payload.get("relative_path") or ""),
        canonical_name=str(payload.get("canonical_name") or ""),
        tool_id=str(payload.get("tool_id") or ""),
        source_authority=str(payload.get("source_authority") or "authoritative"),
        document_metadata=dict(metadata) or None,
        is_anchor=bool(payload.get("is_anchor")),
        rows=rows,
    )
