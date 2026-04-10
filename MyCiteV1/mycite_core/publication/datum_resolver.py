"""
Public and contact-card datum resolver.

Resolution order (canonical):
  1. local anthology
  2. local projection cache (optional, stub)
  3. local contract compact-array snapshot
  4. public contact-card exported datum metadata
  5. remote fetch (optional, stub)
  6. negotiated/private contract path

Public/exported datums must resolve without requiring a contract. This module
exposes a single resolve entrypoint that tries each source in order and returns
the first match plus source metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mycite_core.mss_resolution import (
    DatumResolution,
    resolve_to_contract_entry,
    resolve_to_local_row,
    to_canonical_dot,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass(frozen=True)
class ResolverContext:
    """Context passed to the resolver (all optional)."""

    local_msn_id: str
    anthology_rows: Optional[List[Dict[str, Any]]] = None
    contract_decoded_rows: Optional[List[Dict[str, Any]]] = None
    contract_source_msn_id: str = ""
    public_export_metadata: Optional[Dict[str, Any]] = None


def _normalize_public_export_key(key: str, *, local_msn_id: str) -> str:
    """Normalize a key from contact-card accessible/exported to canonical dot form."""
    key = _as_text(key)
    if not key:
        return ""
    try:
        return to_canonical_dot(key, local_msn_id=local_msn_id, require_qualified=False, field_name="export_key")
    except Exception:
        return key


def resolve_from_public_export(
    canonical_dot: str,
    *,
    public_export_metadata: Dict[str, Any],
    local_msn_id: str = "",
) -> DatumResolution:
    """
    Resolve a canonical datum path from public contact-card exported metadata.

    public_export_metadata is typically the contact card's `accessible` or
    exported-datum map. Keys may be datum refs (any form); they are normalized
    for lookup. Values are metadata (e.g. display_title, magnitude_hint).
    """
    if not public_export_metadata or not isinstance(public_export_metadata, dict):
        return DatumResolution(
            ok=False,
            datum_path=canonical_dot,
            source="",
            row={},
            storage_address=None,
            reason="no public export metadata",
        )
    for key, value in public_export_metadata.items():
        try:
            norm = _normalize_public_export_key(key, local_msn_id=local_msn_id)
        except Exception:
            continue
        if norm == canonical_dot:
            meta = value if isinstance(value, dict) else {"display_title": _as_text(value)}
            return DatumResolution(
                ok=True,
                datum_path=canonical_dot,
                source="public_export",
                row=dict(meta),
                storage_address=None,
                reason="",
            )
    return DatumResolution(
        ok=False,
        datum_path=canonical_dot,
        source="",
        row={},
        storage_address=None,
        reason="datum not in public export metadata",
    )


def resolve_datum_path(
    datum_ref: object,
    *,
    context: ResolverContext,
    require_qualified: bool = False,
) -> DatumResolution:
    """
    Resolve a datum ref to a row or metadata using the canonical resolution order.

    Order: local anthology -> contract snapshot -> public contact-card exported.
    (Projection cache and remote/negotiated are left for future implementation.)

    Returns the first successful resolution; if none match, returns ok=False with reason.
    """
    try:
        canonical_dot = to_canonical_dot(
            datum_ref,
            local_msn_id=context.local_msn_id,
            require_qualified=require_qualified,
            field_name="datum_ref",
        )
    except Exception as e:
        return DatumResolution(
            ok=False,
            datum_path=_as_text(datum_ref),
            source="",
            row={},
            storage_address=None,
            reason=f"invalid ref: {e}",
        )

    # 1. Local anthology
    if context.anthology_rows is not None:
        res = resolve_to_local_row(
            canonical_dot,
            anthology_rows=context.anthology_rows,
            local_msn_id=context.local_msn_id,
        )
        if res.ok:
            return res

    # 2. (Projection cache — stub; skip)

    # 3. Contract snapshot
    if context.contract_decoded_rows is not None:
        res = resolve_to_contract_entry(
            canonical_dot,
            contract_payloads=[],
            decoded_mss_rows=context.contract_decoded_rows,
        )
        if res.ok:
            return res

    # 4. Public contact-card exported
    if context.public_export_metadata not in (None, {}):
        res = resolve_from_public_export(
            canonical_dot,
            public_export_metadata=context.public_export_metadata,
            local_msn_id=context.local_msn_id,
        )
        if res.ok:
            return res

    # 5. Remote / 6. Negotiated — stubs
    return DatumResolution(
        ok=False,
        datum_path=canonical_dot,
        source="",
        row={},
        storage_address=None,
        reason="datum not found in local anthology, contract snapshot, or public export",
    )


def public_export_metadata_from_contact_card(card_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract public/exported datum metadata from a contact card payload.

    Uses the card's `public_resources` field when present. Legacy `accessible`
    maps are no longer canonical runtime input.
    """
    if not isinstance(card_payload, dict):
        return {}
    catalog = card_payload.get("public_resources")
    if isinstance(catalog, list):
        out: Dict[str, Any] = {}
        for item in catalog:
            if not isinstance(item, dict):
                continue
            reference_id = _as_text(item.get("reference_id") or item.get("resource_id"))
            if reference_id:
                normalized = dict(item)
                normalized.setdefault("reference_id", reference_id)
                out[reference_id] = normalized
        return out
    return {}
