from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data_contract.anthology_pairs import compact_row_to_record, record_to_compact_row
from .anthology_overlay import load_overlay_merge_for_path, merge_base_and_overlay
from .anthology_registry import load_base_registry
from .anthology_schema import sort_key


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _rows_from_compact_payload(compact_payload: dict[str, Any], *, source_scope: str = "portal") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row_id, raw in dict(compact_payload or {}).items():
        record, _warnings, _valid = compact_row_to_record(str(row_id), raw)
        identifier = _as_text(record.get("identifier") or record.get("row_id") or row_id)
        if not identifier:
            continue
        item = dict(record)
        item["source_scope"] = source_scope
        out[identifier] = item
    return out


def _rows_from_list(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = _as_text(row.get("identifier") or row.get("row_id") or row.get("id"))
        if not identifier:
            continue
        out[identifier] = dict(row)
    return out


def _compact_from_rows(rows_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    ordered = sorted(rows_by_id.keys(), key=lambda token: sort_key(token, token))
    for index, token in enumerate(ordered, start=1):
        row = rows_by_id.get(token) or {}
        key, value = record_to_compact_row(row, index)
        if key:
            out[key] = value
    return out


@dataclass(frozen=True)
class AnthologyContext:
    compact_payload: dict[str, Any]
    rows_by_id: dict[str, dict[str, Any]]
    source_scope_by_id: dict[str, str]
    warnings: list[str]
    errors: list[str]

    @property
    def rows_payload(self) -> dict[str, Any]:
        return {"rows": dict(self.rows_by_id)}

    @property
    def ok(self) -> bool:
        return not self.errors


def build_canonical_anthology_context(
    *,
    overlay_payload: dict[str, Any] | None = None,
    overlay_path: Path | None = None,
) -> AnthologyContext:
    warnings: list[str] = []
    errors: list[str] = []
    source_scope_by_id: dict[str, str] = {}

    # Preferred canonical path: overlay file + base registry merge.
    if isinstance(overlay_path, Path):
        report = load_overlay_merge_for_path(
            overlay_path=overlay_path,
            strict=False,
            allow_overlay_override=True,
        )
        rows_by_id = _rows_from_compact_payload(report.merged_payload)
        for rid, scope in dict(report.source_scope_by_id or {}).items():
            source_scope_by_id[str(rid)] = str(scope or "portal")
            if rid in rows_by_id:
                rows_by_id[rid]["source_scope"] = source_scope_by_id[rid]
        return AnthologyContext(
            compact_payload=dict(report.merged_payload),
            rows_by_id=rows_by_id,
            source_scope_by_id=source_scope_by_id,
            warnings=list(report.warnings or []),
            errors=list(report.errors or []),
        )

    payload = dict(overlay_payload or {})
    # Provider may already pass {"rows": ...}.
    rows_obj = payload.get("rows") if isinstance(payload, dict) else None
    if isinstance(rows_obj, dict):
        # Could be compact dict or row-object dict.
        is_compact = all(isinstance(value, list) for value in rows_obj.values()) if rows_obj else False
        if is_compact:
            compact_payload = dict(rows_obj)
            rows_by_id = _rows_from_compact_payload(compact_payload)
        else:
            rows_by_id = _rows_from_list([dict(value) for value in rows_obj.values() if isinstance(value, dict)])
            compact_payload = _compact_from_rows(rows_by_id)
        return AnthologyContext(
            compact_payload=compact_payload,
            rows_by_id=rows_by_id,
            source_scope_by_id={key: "portal" for key in rows_by_id.keys()},
            warnings=warnings,
            errors=errors,
        )
    if isinstance(rows_obj, list):
        rows_by_id = _rows_from_list([dict(item) for item in rows_obj if isinstance(item, dict)])
        compact_payload = _compact_from_rows(rows_by_id)
        return AnthologyContext(
            compact_payload=compact_payload,
            rows_by_id=rows_by_id,
            source_scope_by_id={key: "portal" for key in rows_by_id.keys()},
            warnings=warnings,
            errors=errors,
        )

    # Fallback: treat provider payload itself as overlay compact and merge against base.
    report = merge_base_and_overlay(
        base_registry=load_base_registry(strict=False),
        overlay_payload=payload,
        strict=False,
        allow_overlay_override=True,
    )
    rows_by_id = _rows_from_compact_payload(report.merged_payload)
    for rid, scope in dict(report.source_scope_by_id or {}).items():
        source_scope_by_id[str(rid)] = str(scope or "portal")
        if rid in rows_by_id:
            rows_by_id[rid]["source_scope"] = source_scope_by_id[rid]
    return AnthologyContext(
        compact_payload=dict(report.merged_payload),
        rows_by_id=rows_by_id,
        source_scope_by_id=source_scope_by_id,
        warnings=list(report.warnings or []),
        errors=list(report.errors or []),
    )
