from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mycite_core.datum_refs import ParsedDatumRef, datum_identifier_candidates, normalize_datum_ref, parse_datum_ref


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_datum_path(value: object, *, field_name: str = "datum_ref") -> ParsedDatumRef:
    return parse_datum_ref(value, field_name=field_name)


def to_canonical_dot(
    value: object,
    *,
    local_msn_id: str = "",
    require_qualified: bool = False,
    field_name: str = "datum_ref",
) -> str:
    return normalize_datum_ref(
        value,
        local_msn_id=local_msn_id,
        require_qualified=require_qualified,
        write_format="dot",
        field_name=field_name,
    )


def datum_paths_equivalent(ref_a: object, ref_b: object, *, local_msn_id: str = "") -> bool:
    a = _as_text(ref_a)
    b = _as_text(ref_b)
    if not a or not b:
        return a == b
    try:
        canon_a = to_canonical_dot(a, local_msn_id=local_msn_id, field_name="ref_a")
        canon_b = to_canonical_dot(b, local_msn_id=local_msn_id, field_name="ref_b")
    except Exception:
        return False
    return canon_a == canon_b


def stable_datum_id(value: object, *, local_msn_id: str = "", field_name: str = "datum_ref") -> str:
    return to_canonical_dot(value, local_msn_id=local_msn_id, require_qualified=False, field_name=field_name)


@dataclass(frozen=True)
class DatumResolution:
    ok: bool
    datum_path: str
    source: str
    row: dict[str, Any]
    storage_address: str | None
    reason: str = ""


def resolve_to_local_row(
    canonical_dot: str,
    *,
    anthology_rows: list[dict[str, Any]],
    local_msn_id: str = "",
) -> DatumResolution:
    parsed = parse_datum_ref(canonical_dot, field_name="datum_path")
    if parsed.msn_id and parsed.msn_id != _as_text(local_msn_id):
        return DatumResolution(False, canonical_dot, "", {}, None, "datum is foreign, not in local anthology")
    candidates = datum_identifier_candidates(canonical_dot, local_msn_id=local_msn_id)
    for row in anthology_rows or []:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        if rid in candidates:
            return DatumResolution(True, canonical_dot, "local_anthology", dict(row), rid, "")
    return DatumResolution(False, canonical_dot, "", {}, None, "datum not found in local anthology")


def resolve_to_contract_entry(
    canonical_dot: str,
    *,
    contract_payloads: list[dict[str, Any]],
    decoded_mss_rows: list[dict[str, Any]] | None = None,
) -> DatumResolution:
    parsed = parse_datum_ref(canonical_dot, field_name="datum_path")
    datum_address = parsed.datum_address
    candidates = [canonical_dot, parsed.canonical_hyphen, datum_address]
    rows = list(decoded_mss_rows or [])
    for row in rows:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        source_id = _as_text(row.get("source_identifier"))
        if rid in candidates or source_id in candidates or rid == datum_address or source_id == datum_address:
            return DatumResolution(True, canonical_dot, "contract_snapshot", dict(row), rid, "")
    return DatumResolution(False, canonical_dot, "", {}, None, "datum not found in contract snapshot")


def compile_compact_array_entries_keyed_by_path(
    rows: list[dict[str, Any]],
    *,
    source_msn_id: str = "",
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        semantic_id = _as_text(row.get("source_identifier")) or rid
        if not rid:
            continue
        path = stable_datum_id(semantic_id, local_msn_id=source_msn_id, field_name="identifier")
        result[path] = {
            "datum_path": path,
            "storage_address": rid,
            "semantic_address": semantic_id,
            "label": _as_text(row.get("label")),
            "row": dict(row),
        }
    return result


@dataclass(frozen=True)
class CompiledDatumIndex:
    contract_id: str
    relationship_mode: str
    access_mode: str
    sync_mode: str
    source_msn_id: str
    target_msn_id: str
    revision: int
    compiled_at_unix_ms: int
    source_card_revision: str | None
    entries: dict[str, dict[str, Any]]


def build_compiled_index(
    *,
    contract_id: str,
    source_msn_id: str,
    target_msn_id: str,
    decoded_rows: list[dict[str, Any]],
    relationship_mode: str,
    access_mode: str,
    sync_mode: str,
    revision: int,
    compiled_at_unix_ms: int,
    source_card_revision: str | None,
) -> CompiledDatumIndex:
    return CompiledDatumIndex(
        contract_id=_as_text(contract_id),
        relationship_mode=_as_text(relationship_mode),
        access_mode=_as_text(access_mode),
        sync_mode=_as_text(sync_mode),
        source_msn_id=_as_text(source_msn_id),
        target_msn_id=_as_text(target_msn_id),
        revision=int(revision or 0),
        compiled_at_unix_ms=int(compiled_at_unix_ms or 0),
        source_card_revision=_as_text(source_card_revision) or None,
        entries=compile_compact_array_entries_keyed_by_path(decoded_rows, source_msn_id=source_msn_id),
    )
