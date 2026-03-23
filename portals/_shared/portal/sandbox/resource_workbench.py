"""
View-model helpers for canonical resource JSON workbenches.

Builds anthology-esque structured row summaries and SAMRAS hints from the same
resource bodies returned by ``GET /portal/api/data/sandbox/resources/<id>``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _shared.portal.data_contract import compact_payload_to_rows
from _shared.portal.samras import (
    build_workspace_view_model,
    load_workspace_from_compact_payload,
    load_workspace_from_resource_body,
)


def _looks_like_compact_row_key(value: object) -> bool:
    token = _as_text(value)
    parts = token.split("-")
    if len(parts) != 3:
        return False
    return all(part.isdigit() for part in parts)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _identifier_coordinates(identifier: object) -> tuple[int | None, int | None, int | None]:
    token = _as_text(identifier)
    parts = token.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return (None, None, None)
    return (int(parts[0], 10), int(parts[1], 10), int(parts[2], 10))


def extract_anthology_rows_payload(resource_body: dict[str, Any]) -> dict[str, Any]:
    """Return a payload shaped like anthology ``{ \"rows\": { id: row } }`` when present."""
    acp = resource_body.get("anthology_compatible_payload")
    if isinstance(acp, dict):
        rows = acp.get("rows")
        if isinstance(rows, dict) and rows:
            return acp
    cs = resource_body.get("canonical_state")
    if isinstance(cs, dict):
        cp = cs.get("compact_payload")
        if isinstance(cp, dict):
            rows = cp.get("rows")
            if isinstance(rows, dict) and rows:
                return cp
    return {"rows": {}}


def is_samras_backed_resource(resource_body: dict[str, Any]) -> bool:
    kind = _as_text(resource_body.get("kind") or resource_body.get("resource_kind")).lower()
    if "samras" in kind:
        return True
    acp = resource_body.get("anthology_compatible_payload")
    if isinstance(acp, dict):
        for row in compact_payload_to_rows(acp, strict=False):
            if _as_text(row.get("reference")) == "0-0-5":
                return True
    cs = resource_body.get("canonical_state")
    if isinstance(cs, dict):
        cp = cs.get("compact_payload")
        if isinstance(cp, dict):
            for row in compact_payload_to_rows(cp, strict=False):
                if _as_text(row.get("reference")) == "0-0-5":
                    return True
    rba = resource_body.get("rows_by_address")
    if isinstance(rba, dict) and rba:
        return True
    if _as_text(resource_body.get("structure_payload")) or _as_text(resource_body.get("canonical_magnitude")):
        return True
    return False


def _address_sort_key(address_id: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in str(address_id).split("-"):
        try:
            parts.append(int(p, 10))
        except ValueError:
            parts.append(10**9)
    return tuple(parts)


def build_samras_row_summaries(resource_body: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        workspace = load_workspace_from_resource_body(resource_body)
        return [
            {
                "address_id": node.address_id,
                "title": node.title,
                "source": "derived_structure",
            }
            for node in workspace.nodes
        ]
    except Exception:
        pass
    rows_by_address = resource_body.get("rows_by_address") if isinstance(resource_body.get("rows_by_address"), dict) else {}
    out: list[dict[str, Any]] = []
    for key, value in rows_by_address.items():
        aid = _as_text(key)
        if not aid:
            continue
        names = value if isinstance(value, list) else [value]
        title = _as_text(names[0] if names else "")
        out.append({"address_id": aid, "title": title, "source": "rows_by_address"})
    out.sort(key=lambda r: _address_sort_key(str(r["address_id"])))
    return out


def build_anthology_row_summaries(
    rows_payload: dict[str, Any],
    *,
    rule_policy_by_id: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = rows_payload.get("rows") if isinstance(rows_payload.get("rows"), dict) else {}
    policies = rule_policy_by_id if isinstance(rule_policy_by_id, dict) else {}
    out: list[dict[str, Any]] = []
    for key, row in rows.items():
        if not isinstance(row, dict):
            continue
        rid = _as_text(row.get("identifier") or row.get("row_id") or key)
        if not rid:
            continue
        pol = policies.get(rid) if rid in policies else policies.get(key)
        pol_d = pol if isinstance(pol, dict) else {}
        out.append(
            {
                "row_id": _as_text(row.get("row_id") or rid),
                "identifier": rid,
                "label": _as_text(row.get("label")),
                "layer": row.get("layer"),
                "value_group": row.get("value_group"),
                "iteration": row.get("iteration"),
                "reference": _as_text(row.get("reference")),
                "magnitude": _as_text(row.get("magnitude")),
                "rule_family": pol_d.get("rule_family"),
                "lens_id": pol_d.get("lens_id"),
                "source": "anthology_compatible_payload",
            }
        )
        layer, value_group, iteration = _identifier_coordinates(rid)
        if out[-1].get("layer") is None:
            out[-1]["layer"] = layer
        if out[-1].get("value_group") is None:
            out[-1]["value_group"] = value_group
        if out[-1].get("iteration") is None:
            out[-1]["iteration"] = iteration
    def _layer_key(row: dict[str, Any]) -> tuple[int, int, str]:
        try:
            layer = int(row.get("layer"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            layer = 10**9
        try:
            vg = int(row.get("value_group"))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            vg = 10**9
        return (layer, vg, str(row.get("identifier") or ""))

    out.sort(key=_layer_key)
    return out


def _group_rows_by_layer_vg(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    order: list[tuple[Any, Any]] = []
    for row in summaries:
        key = (row.get("layer"), row.get("value_group"))
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)
    layers: list[dict[str, Any]] = []
    for layer, vg in order:
        layers.append(
            {
                "layer": layer,
                "value_group": vg,
                "row_count": len(buckets[(layer, vg)]),
                "rows": list(buckets[(layer, vg)]),
            }
        )
    return layers


def understanding_brief(datum_understanding: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(datum_understanding, dict):
        return {"ok": False, "warnings": [], "errors": [], "understandings_count": 0}
    return {
        "ok": bool(datum_understanding.get("ok", True)),
        "warnings": [str(w) for w in list(datum_understanding.get("warnings") or [])],
        "errors": [str(e) for e in list(datum_understanding.get("errors") or [])],
        "understandings_count": len(list(datum_understanding.get("understandings") or [])),
    }


def build_resource_workbench_view_model(
    *,
    resource_body: dict[str, Any],
    staged_present: bool,
    staged_payload: dict[str, Any] | None,
    datum_understanding: dict[str, Any] | None = None,
    rule_policy_by_id: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Assemble a JSON-serializable workbench view-model for the resource editor.

    ``resource_body`` is the saved sandbox resource dict (not wrapped with ``missing``).
    """
    rid = _as_text(resource_body.get("resource_id"))
    kind = _as_text(resource_body.get("kind") or resource_body.get("resource_kind"))
    rows_payload = extract_anthology_rows_payload(resource_body)
    anthology_summaries = build_anthology_row_summaries(rows_payload, rule_policy_by_id=rule_policy_by_id)
    samras_summaries = build_samras_row_summaries(resource_body) if is_samras_backed_resource(resource_body) else []
    samras_workspace = None
    if is_samras_backed_resource(resource_body):
        try:
            workspace = load_workspace_from_resource_body(resource_body)
            samras_workspace = build_workspace_view_model(workspace, selected_address_id="", staged_entries=[])
        except Exception:
            samras_workspace = None
    grouped_anthology = _group_rows_by_layer_vg(anthology_summaries) if anthology_summaries else []

    return {
        "schema": "mycite.portal.resource.workbench.v1",
        "resource_id": rid,
        "resource_kind": kind,
        "saved_label": "sandbox/resources (saved)",
        "staged_present": bool(staged_present),
        "staged_label": "sandbox/staging (*.stage.json)" if staged_present else "",
        "is_samras_backed": is_samras_backed_resource(resource_body),
        "anthology_rows_payload_present": bool(rows_payload.get("rows")),
        "anthology_row_summaries": anthology_summaries,
        "anthology_layers": grouped_anthology,
        "samras_row_summaries": samras_summaries,
        "samras_workspace": samras_workspace,
        "understanding": understanding_brief(datum_understanding),
        "rule_policy_keys": sorted(rule_policy_by_id.keys()) if isinstance(rule_policy_by_id, dict) else [],
    }


__all__ = [
    "build_resource_workbench_view_model",
    "build_system_resource_workbench_view_model",
    "build_samras_row_summaries",
    "extract_anthology_rows_payload",
    "is_samras_backed_resource",
    "system_workbench_stage_dir",
    "system_workbench_stage_path",
    "understanding_brief",
]


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json_object_one_entry_per_line(path: Path, payload: dict[str, Any]) -> None:
    """
    Write stable JSON where each top-level entry is serialized on one line.

    This keeps datum collections scan-friendly and deterministic across reloads.
    """
    items = sorted(payload.items(), key=lambda kv: str(kv[0]))
    lines = ["{"]
    for idx, (key, value) in enumerate(items):
        is_last_top = idx == len(items) - 1
        key_token = json.dumps(str(key))
        if str(key) == "rows" and isinstance(value, dict):
            lines.append(f"  {key_token}: {{")
            row_items = sorted(value.items(), key=lambda kv: str(kv[0]))
            for row_idx, (row_key, row_value) in enumerate(row_items):
                row_comma = "," if row_idx < len(row_items) - 1 else ""
                lines.append(
                    "    "
                    + json.dumps(str(row_key))
                    + ": "
                    + json.dumps(row_value, ensure_ascii=True, separators=(",", ": "))
                    + row_comma
                )
            lines.append("  }" + ("" if is_last_top else ","))
            continue
        comma = "" if is_last_top else ","
        lines.append(f"  {key_token}: {json.dumps(value, ensure_ascii=True, separators=(',', ': '))}{comma}")
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _extract_rows_payload_from_json(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows")
    if isinstance(rows, dict):
        return {"rows": rows}
    compact_rows = {
        str(key): value
        for key, value in payload.items()
        if _looks_like_compact_row_key(key) and isinstance(value, list)
    }
    if compact_rows:
        try:
            parsed_rows = compact_payload_to_rows(compact_rows, strict=False)
        except Exception:
            parsed_rows = []
        if parsed_rows:
            return {
                "rows": {
                    _as_text(row.get("identifier") or row.get("row_id") or index): row
                    for index, row in enumerate(parsed_rows, start=1)
                    if isinstance(row, dict)
                }
            }
    return extract_anthology_rows_payload(payload)


def _resolve_canonical_data_file(*, data_root: Path, canonical_filename: str, aliases: list[str]) -> tuple[Path, dict[str, Any], bool]:
    canonical = Path(data_root) / canonical_filename
    if canonical.is_file():
        payload = _read_json_object(canonical)
        if not payload:
            payload = {}
        _write_json_object_one_entry_per_line(canonical, payload)
        return canonical, payload, True

    for alias in aliases:
        alias_path = Path(data_root) / str(alias)
        if not alias_path.is_file():
            continue
        payload = _read_json_object(alias_path)
        if not payload:
            payload = {}
        _write_json_object_one_entry_per_line(canonical, payload)
        return canonical, payload, True

    payload: dict[str, Any] = {}
    _write_json_object_one_entry_per_line(canonical, payload)
    return canonical, payload, False


def system_workbench_stage_dir(data_root: Path) -> Path:
    return Path(data_root) / ".system_workbench_staging"


def system_workbench_stage_path(*, data_root: Path, filename: str) -> Path:
    return system_workbench_stage_dir(data_root) / f"{filename}.stage.json"


def _normalize_samras_rows_by_address(payload: dict[str, Any]) -> dict[str, list[str]]:
    raw = payload.get("rows_by_address") if isinstance(payload.get("rows_by_address"), dict) else {}
    out: dict[str, list[str]] = {}
    for key, value in raw.items():
        aid = _as_text(key)
        if not aid:
            continue
        if isinstance(value, list):
            out[aid] = [_as_text(v) for v in value]
        else:
            out[aid] = [_as_text(value)]
    return out


def _rows_by_address_from_workspace(workspace_vm: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    rows = workspace_vm.get("title_table_rows") if isinstance(workspace_vm, dict) else []
    for item in list(rows or []):
        if not isinstance(item, dict):
            continue
        aid = _as_text(item.get("address_id"))
        if not aid:
            continue
        titles = item.get("titles") if isinstance(item.get("titles"), list) else None
        if titles:
            out[aid] = [_as_text(token) for token in titles if _as_text(token)]
        else:
            out[aid] = [_as_text(item.get("title"))]
    return out


def _table_rows_for_canonical_file(
    *,
    file_key: str,
    filename: str,
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[str]] | None, dict[str, Any] | None]:
    """Return flattened explorer rows and optional SAMRAS address map for mediation UIs."""
    rows_payload = _extract_rows_payload_from_json(payload) if payload else {"rows": {}}
    summaries = build_anthology_row_summaries(rows_payload)
    samras_workspace_vm: dict[str, Any] | None = None
    samras_map: dict[str, list[str]] = {}
    if file_key in {"txa", "msn"}:
        try:
            workspace = load_workspace_from_compact_payload(payload)
            samras_workspace_vm = build_workspace_view_model(workspace, selected_address_id="", staged_entries=[])
            samras_map = _rows_by_address_from_workspace(samras_workspace_vm)
        except Exception:
            samras_workspace_vm = None
    if not samras_map:
        samras_map = _normalize_samras_rows_by_address(payload)
    samras_for_file: dict[str, list[str]] | None = samras_map if samras_map else None

    table_rows: list[dict[str, Any]] = []
    for row in summaries:
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        table_rows.append(
            {
                "file_key": file_key,
                "filename": filename,
                "identifier": rid,
                "row_id": _as_text(row.get("row_id")),
                "label": _as_text(row.get("label")),
                "reference": _as_text(row.get("reference")),
                "magnitude": _as_text(row.get("magnitude")),
                "layer": row.get("layer"),
                "value_group": row.get("value_group"),
                "iteration": row.get("iteration"),
                "source": _as_text(row.get("source") or "rows"),
                "lens_id": row.get("lens_id"),
            }
        )

    if not summaries and samras_map:
        for item in build_samras_row_summaries({"rows_by_address": samras_map}):
            aid = _as_text(item.get("address_id"))
            if not aid:
                continue
            table_rows.append(
                {
                    "file_key": file_key,
                    "filename": filename,
                    "identifier": aid,
                    "row_id": aid,
                    "label": _as_text(item.get("title")),
                    "reference": "",
                    "magnitude": "",
                    "layer": None,
                    "value_group": None,
                    "iteration": None,
                    "source": "samras_rows_by_address",
                    "address_id": aid,
                    "lens_id": None,
                }
            )

    return table_rows, samras_for_file, samras_workspace_vm


def build_system_resource_workbench_view_model(*, data_root: Path) -> dict[str, Any]:
    """
    Build a table-first workbench model for canonical local JSON files.

    Baseline files are fixed by product contract:
    - anthology.json
    - samras-txa.json
    - samras-msn.json
    """
    files = [
        {"file_key": "anthology", "filename": "anthology.json", "aliases": []},
        {"file_key": "txa", "filename": "samras-txa.json", "aliases": ["samras-txa.legacy.json", "samras.txa.json"]},
        {"file_key": "msn", "filename": "samras-msn.json", "aliases": ["samras-msn.legacy.json", "samras.msn.json", "demo-SAMRAS_MSN.json"]},
    ]
    out_files: list[dict[str, Any]] = []
    table_rows: list[dict[str, Any]] = []
    samras_by_file_key: dict[str, dict[str, list[str]]] = {}
    samras_workspace_by_file_key: dict[str, dict[str, Any]] = {}
    layers_by_file_key: dict[str, list[dict[str, Any]]] = {}
    resource_surface_file_keys = ("anthology", "txa", "msn")

    for entry in files:
        filename = str(entry["filename"])
        file_key = str(entry["file_key"])
        aliases = [str(item) for item in list(entry.get("aliases") or [])]
        path, payload, found_existing = _resolve_canonical_data_file(
            data_root=Path(data_root),
            canonical_filename=filename,
            aliases=aliases,
        )
        staged_path = system_workbench_stage_path(data_root=Path(data_root), filename=filename)
        staged_payload = _read_json_object(staged_path) if file_key != "anthology" and staged_path.is_file() else {}
        active_payload = staged_payload if staged_payload else payload
        per_file_rows, samras_map, samras_workspace = _table_rows_for_canonical_file(
            file_key=file_key,
            filename=filename,
            payload=active_payload,
        )
        file_obj: dict[str, Any] = {
            "file_key": file_key,
            "filename": filename,
            "path": str(path),
            "canonical_path": str(path),
            "exists": True,
            "materialized_from_existing_file": bool(found_existing),
            "row_count": len(per_file_rows),
            "layers": _group_rows_by_layer_vg(per_file_rows) if per_file_rows else [],
            "errors": [],
            "samras_rows_by_address": samras_map,
            "samras_workspace": samras_workspace,
            "write_mode": "direct" if file_key == "anthology" else "stage_then_promote",
            "staged_present": bool(staged_payload),
            "staged_path": str(staged_path),
        }
        if file_obj["layers"]:
            layers_by_file_key[file_key] = list(file_obj["layers"])
        if samras_map:
            samras_by_file_key[file_key] = samras_map
        if samras_workspace:
            samras_workspace_by_file_key[file_key] = samras_workspace
        table_rows.extend(per_file_rows)
        out_files.append(file_obj)

    return {
        "ok": True,
        "schema": "mycite.portal.system.resource_workbench.v1",
        "files": out_files,
        "rows": table_rows,
        "total_rows": len(table_rows),
        "resource_surface_file_keys": list(resource_surface_file_keys),
        "layers_by_file_key": layers_by_file_key,
        "samras_rows_by_address_by_file_key": samras_by_file_key,
        "samras_workspace_by_file_key": samras_workspace_by_file_key,
    }
