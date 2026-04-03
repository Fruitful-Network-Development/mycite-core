from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data_contract.anthology_pairs import compact_row_to_record, record_to_compact_row
from ..data_engine.anthology_registry import load_base_registry


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _read_payload(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class SandboxAnthologyMigrationResult:
    ok: bool
    migrated_rows: list[str]
    extracted_resource_rows: list[str]
    removed_rows: list[str]
    retained_rows: list[str]
    sandbox_resources: list[str]
    resource_payload_paths: list[str]
    resource_summaries: list[dict[str, Any]]
    retained_local_id_rows: list[str]
    exact_live_txa_msn_rows: list[str]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "migrated_rows": list(self.migrated_rows),
            "extracted_resource_rows": list(self.extracted_resource_rows),
            "removed_rows": list(self.removed_rows),
            "retained_rows": list(self.retained_rows),
            "sandbox_resources": list(self.sandbox_resources),
            "resource_payload_paths": list(self.resource_payload_paths),
            "resource_summaries": [dict(item) for item in self.resource_summaries],
            "retained_local_id_rows": list(self.retained_local_id_rows),
            "exact_live_txa_msn_rows": list(self.exact_live_txa_msn_rows),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def _pairs(row: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in list(row.get("pairs") or []):
        if not isinstance(item, dict):
            continue
        out.append((_as_text(item.get("reference")), _as_text(item.get("magnitude"))))
    if out:
        return out
    ref = _as_text(row.get("reference"))
    mag = _as_text(row.get("magnitude"))
    if ref or mag:
        return [(ref, mag)]
    return []


def _rows_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, value in payload.items():
        record, _warnings, _valid = compact_row_to_record(str(key), value)
        identifier = _as_text(record.get("identifier") or record.get("row_id") or key)
        if not identifier:
            continue
        out[identifier] = dict(record)
    return out


def _children(rows: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {key: set() for key in rows.keys()}
    for child_id, row in rows.items():
        for ref, _mag in _pairs(row):
            if ref in rows:
                out.setdefault(ref, set()).add(child_id)
    return out


def _descendants(seed: set[str], child_map: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(seed)
    while stack:
        token = _as_text(stack.pop())
        if not token or token in seen:
            continue
        seen.add(token)
        for child in child_map.get(token, set()):
            if child not in seen:
                stack.append(child)
    return seen


def _parse_selection_ids(magnitude: str) -> list[str]:
    token = _as_text(magnitude)
    if not token.startswith("[") or not token.endswith("]"):
        return []
    try:
        parsed = json.loads(token)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        rid = _as_text(item)
        if rid:
            out.append(rid)
    return out


def _infer_resource_kind(row: dict[str, Any], rows: dict[str, dict[str, Any]]) -> str:
    label = _as_text(row.get("label")).lower()
    if "txa" in label:
        return "txa"
    if "msn" in label:
        return "msn"
    ref = _as_text(row.get("reference"))
    # heuristic from known seed references in existing anthologies
    if ref == "4-1-403":
        return "txa"
    if ref == "4-1-1":
        return "msn"
    # ancestor hint fallback
    cursor = ref
    hops = 0
    while cursor and cursor in rows and hops < 64:
        if cursor in {"1-1-4", "2-1-14", "3-1-8"}:
            return "txa"
        if cursor in {"1-1-5", "2-1-13", "3-1-7"}:
            return "msn"
        next_ref = _as_text(rows[cursor].get("reference"))
        if not next_ref or next_ref == cursor:
            break
        cursor = next_ref
        hops += 1
    return "unknown"


def _resource_id(kind: str, selector_row_id: str) -> str:
    token = _as_text(kind) or "samras"
    return f"{token}.samras.{_as_text(selector_row_id)}"


def _resource_payload_path(data_root: Path, resource_id: str) -> Path:
    token = _as_text(resource_id).replace("/", "_")
    return data_root / "sandbox" / "resources" / f"{token}.json"


def _canonical_resource_payload(
    *,
    resource_id: str,
    resource_kind: str,
    origin_kind: str,
    source_selector_row: str,
    abstraction_root: str,
    selected_ids: list[str],
    extracted_rows: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "mycite.sandbox.singular_mss_resource.v1",
        "resource_id": resource_id,
        "resource_kind": resource_kind,
        "origin_kind": origin_kind,
        "source_portal": "",
        "source_ref": source_selector_row,
        "draft_state": {
            "selected_ids": list(selected_ids),
            "compact_payload": dict(extracted_rows),
        },
        "canonical_state": {
            "selected_ids": list(selected_ids),
            "compact_payload": dict(extracted_rows),
        },
        "mss_form": {
            "bitstring": "",
            "wire_variant": "",
        },
        "abstraction_root": abstraction_root,
        "compile_metadata": {
            "compiled": False,
            "warnings": [],
        },
        "updated_at": 0,
    }


def _retained_ids_from_outside_usage(
    *,
    rows: dict[str, dict[str, Any]],
    removed_tree: set[str],
) -> set[str]:
    retained: set[str] = set()
    for rid, row in rows.items():
        if rid in removed_tree:
            continue
        for ref, _mag in _pairs(row):
            if ref in removed_tree:
                retained.add(ref)
        for token in _parse_selection_ids(_as_text(row.get("magnitude"))):
            if token in removed_tree:
                retained.add(token)
    return retained


def _semantic_seed_ids_from_base() -> set[str]:
    out: set[str] = set()
    base = load_base_registry(strict=False)
    for rid, raw in dict(base.compact_payload or {}).items():
        if not isinstance(raw, list):
            continue
        label = ""
        if len(raw) > 1 and isinstance(raw[1], list) and raw[1]:
            label = _as_text(raw[1][0]).lower()
        if "samras" in label or "txa" in label or "msn" in label:
            out.add(_as_text(rid))
    return out


def migrate_fnd_samras_rows_to_sandbox(
    *,
    anthology_path: Path,
    data_root: Path,
    apply_changes: bool,
) -> SandboxAnthologyMigrationResult:
    payload = _read_payload(anthology_path)
    if not payload:
        return SandboxAnthologyMigrationResult(
            ok=False,
            migrated_rows=[],
            extracted_resource_rows=[],
            removed_rows=[],
            retained_rows=[],
            sandbox_resources=[],
            resource_payload_paths=[],
            resource_summaries=[],
            retained_local_id_rows=[],
            exact_live_txa_msn_rows=[],
            warnings=[],
            errors=[f"unable to load anthology payload: {anthology_path}"],
        )
    rows = _rows_by_id(payload)
    child_map = _children(rows)

    migrated_rows: list[str] = []
    extracted_resource_rows: list[str] = []
    removed_rows: list[str] = []
    retained_rows: list[str] = []
    sandbox_resources: list[str] = []
    resource_payload_paths: list[str] = []
    resource_summaries: list[dict[str, Any]] = []
    retained_local_id_rows: list[str] = []
    exact_live_txa_msn_rows: list[str] = []
    warnings: list[str] = []

    # Live selector rows are those with SAMRAS-set labels and large selection magnitudes.
    selector_ids: list[str] = []
    for rid, row in rows.items():
        label = _as_text(row.get("label")).lower()
        magnitude = _as_text(row.get("magnitude"))
        if "samras_set" in label and magnitude.startswith("[") and magnitude.endswith("]"):
            selector_ids.append(rid)
    selector_ids.sort()
    exact_live_txa_msn_rows.extend(selector_ids)

    removed_tree: set[str] = set()
    out_rows: dict[str, dict[str, Any]] = {rid: dict(row) for rid, row in rows.items()}
    for selector_id in selector_ids:
        row = rows.get(selector_id) or {}
        kind = _infer_resource_kind(row, rows)
        resource_id = _resource_id(kind, selector_id)
        selected_ids = _parse_selection_ids(_as_text(row.get("magnitude")))
        root_ref = _as_text(row.get("reference"))
        seed = set(selected_ids)
        if root_ref:
            seed.add(root_ref)
        tree_ids = _descendants(seed, child_map)
        tree_ids.add(selector_id)
        removed_tree.update(tree_ids)

        extracted_compact: dict[str, Any] = {}
        for tid in sorted(tree_ids):
            source_row = rows.get(tid)
            if not isinstance(source_row, dict):
                continue
            key, value = record_to_compact_row(source_row, len(extracted_compact) + 1)
            if key:
                extracted_compact[key] = value

        resource_payload = _canonical_resource_payload(
            resource_id=resource_id,
            resource_kind=kind,
            origin_kind="local",
            source_selector_row=selector_id,
            abstraction_root=root_ref,
            selected_ids=selected_ids,
            extracted_rows=extracted_compact,
        )
        resource_path = _resource_payload_path(data_root, resource_id)
        if apply_changes:
            resource_path.parent.mkdir(parents=True, exist_ok=True)
            resource_path.write_text(json.dumps(resource_payload, indent=2) + "\n", encoding="utf-8")
        resource_payload_paths.append(str(resource_path))
        sandbox_resources.append(resource_id)
        migrated_rows.append(selector_id)
        extracted_resource_rows.extend(sorted(tree_ids))
        resource_summaries.append(
            {
                "resource_id": resource_id,
                "resource_kind": kind,
                "selector_row": selector_id,
                "abstraction_root": root_ref,
                "selected_id_count": len(selected_ids),
                "extracted_row_count": len(tree_ids),
            }
        )

    retained_from_usage = _retained_ids_from_outside_usage(rows=rows, removed_tree=removed_tree)
    retained_local_id_rows = sorted(retained_from_usage)

    # Base-vs-portal policy: keep creation/seed datums in base only when rows are exact duplicates.
    base = load_base_registry(strict=False)
    seed_ids = _semantic_seed_ids_from_base()
    for rid in sorted(seed_ids):
        if rid in retained_from_usage:
            continue
        if rid not in out_rows:
            continue
        overlay_compact = payload.get(rid)
        base_compact = base.compact_payload.get(rid)
        if overlay_compact == base_compact:
            del out_rows[rid]
            removed_rows.append(rid)
            warnings.append(f"removed base-duplicate semantic seed row from overlay: {rid}")

    for rid in list(removed_tree):
        if rid in retained_from_usage:
            continue
        if rid in out_rows:
            del out_rows[rid]
            removed_rows.append(rid)

    for rid in sorted(out_rows.keys()):
        retained_rows.append(rid)

    if apply_changes:
        out_payload: dict[str, Any] = {}
        ordered = sorted(list(out_rows.values()), key=lambda item: _as_text(item.get("identifier") or item.get("row_id")))
        for index, row in enumerate(ordered):
            out_key, out_value = record_to_compact_row(row, index + 1)
            if out_key:
                out_payload[out_key] = out_value
        _write_payload(anthology_path, out_payload)

    return SandboxAnthologyMigrationResult(
        ok=True,
        migrated_rows=migrated_rows,
        extracted_resource_rows=sorted(set(extracted_resource_rows)),
        removed_rows=sorted(set(removed_rows)),
        retained_rows=retained_rows,
        sandbox_resources=sandbox_resources,
        resource_payload_paths=resource_payload_paths,
        resource_summaries=resource_summaries,
        retained_local_id_rows=retained_local_id_rows,
        exact_live_txa_msn_rows=exact_live_txa_msn_rows,
        warnings=warnings,
        errors=[],
    )
