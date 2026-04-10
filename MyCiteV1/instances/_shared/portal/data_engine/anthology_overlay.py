from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .anthology_registry import BaseRegistry, load_base_registry, load_compact_payload, validate_registry_collisions
from .anthology_schema import NormalizedDatum, normalize_compact_row, sort_key


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass(frozen=True)
class MergeReport:
    merged_payload: dict[str, Any]
    source_scope_by_id: dict[str, str]
    normalized_rows: list[NormalizedDatum]
    warnings: list[str]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def merge_base_and_overlay(
    *,
    base_registry: BaseRegistry,
    overlay_payload: dict[str, Any],
    strict: bool = False,
    allow_overlay_override: bool = True,
) -> MergeReport:
    overlay = dict(overlay_payload if isinstance(overlay_payload, dict) else {})
    warnings = list(base_registry.warnings)
    errors: list[str] = []
    collisions = validate_registry_collisions(base_registry, overlay)
    if collisions and not allow_overlay_override:
        errors.extend(collisions)
    elif collisions:
        warnings.extend(collisions)

    merged = dict(base_registry.compact_payload)
    source_scope_by_id: dict[str, str] = {key: "base" for key in merged.keys()}
    for row_id, raw in overlay.items():
        token = _as_text(row_id)
        if not token:
            continue
        merged[token] = raw
        source_scope_by_id[token] = "portal"

    normalized_rows: list[NormalizedDatum] = []
    for row_id in sorted(merged.keys(), key=lambda token: sort_key(token, token)):
        scope = source_scope_by_id.get(row_id) or "portal"
        datum, row_warnings = normalize_compact_row(
            row_id,
            merged.get(row_id),
            source_scope=scope,
            strict=strict,
        )
        warnings.extend(list(row_warnings or []))
        if datum is None:
            continue
        normalized_rows.append(datum)
    ordered_payload = {datum.datum_id: merged.get(datum.datum_id) for datum in normalized_rows}
    return MergeReport(
        merged_payload=ordered_payload,
        source_scope_by_id=source_scope_by_id,
        normalized_rows=normalized_rows,
        warnings=warnings,
        errors=errors,
    )


def load_overlay_merge_for_path(
    *,
    overlay_path: Path,
    base_path: Path | None = None,
    strict: bool = False,
    allow_overlay_override: bool = True,
) -> MergeReport:
    base_registry = load_base_registry(base_path=base_path, strict=strict)
    overlay_payload = load_compact_payload(overlay_path)
    return merge_base_and_overlay(
        base_registry=base_registry,
        overlay_payload=overlay_payload,
        strict=strict,
        allow_overlay_override=allow_overlay_override,
    )


@dataclass(frozen=True)
class OverlayMigrationReport:
    removed_duplicate_ids: list[str]
    kept_ids: list[str]
    output_payload: dict[str, Any]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "removed_duplicate_ids": list(self.removed_duplicate_ids),
            "kept_ids": list(self.kept_ids),
            "output_payload": dict(self.output_payload),
            "warnings": list(self.warnings),
        }


def strip_base_duplicates_from_overlay(
    *,
    overlay_payload: dict[str, Any],
    base_registry: BaseRegistry,
) -> OverlayMigrationReport:
    out: dict[str, Any] = {}
    removed: list[str] = []
    kept: list[str] = []
    warnings: list[str] = []
    for row_id, raw in dict(overlay_payload or {}).items():
        token = _as_text(row_id)
        if not token:
            continue
        base_raw = base_registry.compact_payload.get(token)
        if base_raw is not None and base_raw == raw:
            removed.append(token)
            continue
        out[token] = raw
        kept.append(token)
        if base_raw is not None and base_raw != raw:
            warnings.append(f"overlay overrides base row: {token}")
    ordered_out = {key: out[key] for key in sorted(out.keys(), key=lambda item: sort_key(item, item))}
    return OverlayMigrationReport(
        removed_duplicate_ids=sorted(removed, key=lambda item: sort_key(item, item)),
        kept_ids=sorted(kept, key=lambda item: sort_key(item, item)),
        output_payload=ordered_out,
        warnings=warnings,
    )


def migrate_overlay_file(
    *,
    overlay_path: Path,
    base_registry: BaseRegistry | None = None,
    apply_changes: bool = False,
) -> OverlayMigrationReport:
    registry = base_registry if isinstance(base_registry, BaseRegistry) else load_base_registry(strict=False)
    try:
        payload = json.loads(overlay_path.read_text(encoding="utf-8")) if overlay_path.exists() else {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    report = strip_base_duplicates_from_overlay(
        overlay_payload=payload,
        base_registry=registry,
    )
    if apply_changes:
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        overlay_path.write_text(json.dumps(report.output_payload, indent=2) + "\n", encoding="utf-8")
    return report
