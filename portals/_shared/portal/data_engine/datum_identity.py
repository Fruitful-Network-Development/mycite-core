"""
Datum identity layer: separate semantic identity (datum path) from storage location.

Rule:
  - datum path = semantic identity (canonical, stable across compactions and portals)
  - layer / value_group / iteration = storage address (local anthology or compact array)

This module does not depend on Flask or app context. Callers pass in anthology payloads,
contract snapshots, or public metadata as needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..datum_refs import (
    ParsedDatumRef,
    datum_identifier_candidates,
    normalize_datum_ref,
    parse_datum_ref,
)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


# ---------------------------------------------------------------------------
# Parse and normalize (delegate to datum_refs)
# ---------------------------------------------------------------------------


def parse_datum_path(value: object, *, field_name: str = "datum_ref") -> ParsedDatumRef:
    """Parse any supported ref form into ParsedDatumRef."""
    return parse_datum_ref(value, field_name=field_name)


def to_canonical_dot(
    value: object,
    *,
    local_msn_id: str = "",
    require_qualified: bool = False,
    field_name: str = "datum_ref",
) -> str:
    """Normalize ref to canonical dot form (msn_id.datum_address)."""
    return normalize_datum_ref(
        value,
        local_msn_id=local_msn_id,
        require_qualified=require_qualified,
        write_format="dot",
        field_name=field_name,
    )


# ---------------------------------------------------------------------------
# Semantic equivalence
# ---------------------------------------------------------------------------


def datum_paths_equivalent(
    ref_a: object,
    ref_b: object,
    *,
    local_msn_id: str = "",
) -> bool:
    """
    Return True if both refs denote the same semantic datum (by canonical dot form).

    Local refs are interpreted in the context of local_msn_id so that
    "4-1-1" and "3-2-3-17-77-1-6-4-1-4.4-1-1" can be considered equivalent when
    local_msn_id is the FND msn.
    """
    a = _as_text(ref_a)
    b = _as_text(ref_b)
    if not a or not b:
        return a == b
    try:
        canon_a = to_canonical_dot(a, local_msn_id=local_msn_id, field_name="ref_a")
    except Exception:
        return False
    try:
        canon_b = to_canonical_dot(b, local_msn_id=local_msn_id, field_name="ref_b")
    except Exception:
        return False
    return canon_a == canon_b


def stable_datum_id(value: object, *, local_msn_id: str = "", field_name: str = "datum_ref") -> str:
    """
    Return a stable identifier for the datum independent of local iteration compaction.

    Uses canonical dot form as the identity. For local refs, local_msn_id is applied
    so the same logical datum always yields the same id even if the local row id
    (layer-value_group-iteration) changes after compaction.
    """
    return to_canonical_dot(value, local_msn_id=local_msn_id, require_qualified=False, field_name=field_name)


# ---------------------------------------------------------------------------
# Resolve: canonical datum path -> source and row/metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatumResolution:
    """Result of resolving a canonical datum path."""

    ok: bool
    datum_path: str
    source: str  # "local_anthology" | "contract_snapshot" | "public_export" | "remote" | ""
    row: Dict[str, Any]
    storage_address: Optional[str]  # local row_id when applicable
    reason: str = ""


def resolve_to_local_row(
    canonical_dot: str,
    *,
    anthology_rows: List[Dict[str, Any]],
    local_msn_id: str = "",
) -> DatumResolution:
    """
    Resolve a canonical datum path to a local anthology row if it belongs to this portal.

    anthology_rows should be a list of dicts with 'identifier' or 'row_id'.
    """
    parsed = parse_datum_ref(canonical_dot, field_name="datum_path")
    if parsed.msn_id and parsed.msn_id != _as_text(local_msn_id):
        return DatumResolution(
            ok=False,
            datum_path=canonical_dot,
            source="",
            row={},
            storage_address=None,
            reason="datum is foreign, not in local anthology",
        )
    # Look up by datum address (local) or by canonical in case rows store it
    candidates = datum_identifier_candidates(canonical_dot, local_msn_id=local_msn_id)
    for row in anthology_rows or []:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        if rid in candidates:
            return DatumResolution(
                ok=True,
                datum_path=canonical_dot,
                source="local_anthology",
                row=dict(row),
                storage_address=rid,
                reason="",
            )
    return DatumResolution(
        ok=False,
        datum_path=canonical_dot,
        source="",
        row={},
        storage_address=None,
        reason="datum not found in local anthology",
    )


def resolve_to_contract_entry(
    canonical_dot: str,
    *,
    contract_payloads: List[Dict[str, Any]],
    decoded_mss_rows: Optional[List[Dict[str, Any]]] = None,
) -> DatumResolution:
    """
    Resolve a canonical datum path to a row from a contract's decoded MSS (compact array).

    If decoded_mss_rows is provided, it is used directly (e.g. from decode_mss_payload).
    Otherwise we do not decode here; caller can pass decoded rows from the matching contract.
    """
    parsed = parse_datum_ref(canonical_dot, field_name="datum_path")
    datum_address = parsed.datum_address
    candidates = [canonical_dot, parsed.canonical_hyphen, datum_address]
    rows = list(decoded_mss_rows or [])
    for row in rows:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        if rid in candidates or rid == datum_address:
            return DatumResolution(
                ok=True,
                datum_path=canonical_dot,
                source="contract_snapshot",
                row=dict(row),
                storage_address=rid,
                reason="",
            )
    return DatumResolution(
        ok=False,
        datum_path=canonical_dot,
        source="",
        row={},
        storage_address=None,
        reason="datum not found in contract snapshot",
    )


def compile_compact_array_entries_keyed_by_path(
    rows: List[Dict[str, Any]],
    *,
    source_msn_id: str = "",
) -> Dict[str, Dict[str, Any]]:
    """
    Build a map from canonical datum path to entry metadata for a compiled compact array.

    Each entry is keyed by canonical path (source_msn_id.datum_address for each row)
    so that recompilation or reordering does not break identity. Uses stable_datum_id
    with source_msn_id so that the same logical datum always has the same key.
    """
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        if not rid:
            continue
        path = stable_datum_id(rid, local_msn_id=source_msn_id, field_name="identifier")
        result[path] = {
            "datum_path": path,
            "storage_address": rid,
            "label": _as_text(row.get("label")),
            "row": dict(row),
        }
    return result


# ---------------------------------------------------------------------------
# Compiled compact-array index (contract-level view)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompiledDatumIndex:
    """
    Contract-level compiled view of a compact array (MSS bitstring).

    This is the concrete shape described in docs/CONTRACT_COMPACT_INDEX.md:
      - top-level snapshot metadata (contract_id, relationship/access/sync modes)
      - entries keyed by canonical datum path
    """

    contract_id: str
    relationship_mode: str
    access_mode: str
    sync_mode: str
    source_msn_id: str
    target_msn_id: str
    revision: int
    compiled_at_unix_ms: int
    source_card_revision: Optional[str]
    entries: Dict[str, Dict[str, Any]]


def build_compiled_index(
    *,
    contract_id: str,
    source_msn_id: str,
    target_msn_id: str,
    decoded_rows: List[Dict[str, Any]],
    relationship_mode: str = "",
    access_mode: str = "",
    sync_mode: str = "",
    revision: int = 0,
    compiled_at_unix_ms: int = 0,
    source_card_revision: Optional[str] = None,
) -> CompiledDatumIndex:
    """
    Build a CompiledDatumIndex from decoded MSS rows and contract metadata.

    - decoded_rows: list of rows from decode_mss_payload / preview_mss_context
    - source_msn_id: MSN that authored this snapshot (owner or counterparty)
    - target_msn_id: MSN this snapshot is for (counterparty or owner)

    Entries are keyed by canonical datum path so recompilation and
    reordering do not break identity.
    """

    entries = compile_compact_array_entries_keyed_by_path(decoded_rows, source_msn_id=source_msn_id)
    return CompiledDatumIndex(
        contract_id=str(contract_id or "").strip(),
        relationship_mode=str(relationship_mode or "").strip() or "unilateral_local",
        access_mode=str(access_mode or "").strip() or "contract",
        sync_mode=str(sync_mode or "").strip() or "none",
        source_msn_id=_as_text(source_msn_id),
        target_msn_id=_as_text(target_msn_id),
        revision=int(revision or 0),
        compiled_at_unix_ms=int(compiled_at_unix_ms or 0),
        source_card_revision=_as_text(source_card_revision) or None,
        entries=entries,
    )
