from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from _shared.portal.data_engine.anthology_context import build_canonical_anthology_context
from _shared.portal.data_engine.field_contracts import default_profile_field_contracts
from _shared.portal.data_engine.inherited_txa_adapter import select_inherited_binding_for_field
from _shared.portal.data_engine.property_workspace import resolve_property_workspace
from _shared.portal.data_engine.profile_config_refs import get_path
from _shared.portal.data_engine.write_pipeline import apply_write_preview, preview_write_intent
from _shared.portal.data_engine.external_resources.resolver import ExternalResourceResolver
from _shared.portal.sandbox.engine import SandboxEngine
from _shared.portal.services.portal_model import canonicalize_portal_model_config
from portal.core_services.runtime import resolve_active_private_config_path
from portal.services.contract_store import get_contract, list_contracts
from portal.services.datum_refs import normalize_datum_ref
from portal.services.inherited_taxonomy import load_inherited_taxonomy
from portal.services.local_audit_log import append_audit_event
from portal.tools.specs import ToolDataSpec, load_tool_spec_for_id

agro_erp_bp = Blueprint("agro_erp", __name__)

TOOL_ID = "agro_erp"
TOOL_TITLE = "AGRO ERP"
TOOL_HOME_PATH = "/portal/tools/agro_erp/home"
TOOL_BLUEPRINT = agro_erp_bp

_HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")
_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_COORD_SCALE = 10_000_000.0

# Default FND taxonomy collection reference for AGRO ERP.
# This value can be overridden in future iterations via tool-specific
# configuration/specs, but is wired here to support the initial taxonomy viewer.
_DEFAULT_TAXONOMY_REF = "3-2-3-17-77-1-6-4-1-4.5-0-4"
_CAPABILITIES_PATH = Path(__file__).resolve().with_name("capabilities.json")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _private_dir() -> Path:
    env = str(os.environ.get("PRIVATE_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(current_app.root_path) / "private"


def _data_dir() -> Path:
    env = str(os.environ.get("DATA_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(current_app.root_path) / "data"


def _workspace():
    return current_app.config.get("MYCITE_DATA_WORKSPACE")


def _sandbox_engine() -> SandboxEngine:
    return SandboxEngine(data_root=_data_dir())


def _external_resolver() -> ExternalResourceResolver:
    return ExternalResourceResolver(
        data_dir=_data_dir(),
        public_dir=Path(str(os.environ.get("PUBLIC_DIR") or "")).resolve()
        if str(os.environ.get("PUBLIC_DIR") or "").strip()
        else (_data_dir().parent / "public"),
        local_msn_id=str(current_app.config.get("MYCITE_MSN_ID") or "").strip(),
    )


def _load_active_config_for_write() -> dict[str, Any]:
    payload, _path = _active_config()
    return payload if isinstance(payload, dict) else {}


def _save_active_config_for_write(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    target = resolve_active_private_config_path(_private_dir(), msn_id or None)
    if target is None:
        return False
    try:
        canonical_payload = canonicalize_portal_model_config(dict(payload))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(canonical_payload, indent=2) + "\n", encoding="utf-8")
        current_app.config["MYCITE_ACTIVE_PRIVATE_CONFIG"] = dict(canonical_payload)
        return True
    except Exception:
        return False


def _canonical_anthology_context():
    overlay_path = _data_dir() / "anthology.json"
    if overlay_path.exists():
        return build_canonical_anthology_context(overlay_path=overlay_path)
    return build_canonical_anthology_context(overlay_payload={})


def _parcel_workspace_payload() -> dict[str, Any]:
    config, _ = _active_config()
    context = _canonical_anthology_context()
    rows_by_id = context.rows_by_id if isinstance(context.rows_by_id, dict) else {}
    return resolve_property_workspace(config=config, rows_by_id=rows_by_id)


def _parcel_by_id(parcel_workspace: dict[str, Any], parcel_id: str) -> dict[str, Any] | None:
    token = str(parcel_id or "").strip()
    for item in list(parcel_workspace.get("parcels") or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("parcel_id") or "").strip() == token:
            return item
    return None


def _coerce_number(value: Any, *, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    token = str(value or "").strip()
    if not token:
        return default
    try:
        return float(token)
    except Exception:
        return default


def _polygon_svg_for_parcel(parcel: dict[str, Any]) -> dict[str, Any]:
    coords = parcel.get("polygon") if isinstance(parcel.get("polygon"), list) else []
    if not coords:
        return {"available": False, "viewbox": "0 0 420 240", "points": "", "focus": {}}
    rows: list[dict[str, Any]] = []
    for item in coords:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "decoded": {
                    "longitude": item.get("longitude"),
                    "latitude": item.get("latitude"),
                }
            }
        )
    svg = _polygon_svg(rows)
    svg["focus"] = dict(parcel.get("focus_hint") if isinstance(parcel.get("focus_hint"), dict) else {})
    return svg


def _plot_overlay_for_parcel(parcel: dict[str, Any], grid_spec: dict[str, Any]) -> dict[str, Any]:
    polygon = parcel.get("polygon") if isinstance(parcel.get("polygon"), list) else []
    bbox = parcel.get("bbox_summary") if isinstance(parcel.get("bbox_summary"), dict) else {}
    if not polygon or not bbox:
        return {"ok": False, "error": "selected parcel has no resolvable geometry"}
    rows = max(1, int(_coerce_number(grid_spec.get("rows"), default=4)))
    cols = max(1, int(_coerce_number(grid_spec.get("columns"), default=4)))
    spacing = max(0.0, _coerce_number(grid_spec.get("spacing"), default=0.0))
    inset = max(0.0, _coerce_number(grid_spec.get("inset"), default=0.0))
    orientation = _coerce_number(grid_spec.get("orientation"), default=0.0)
    min_lon = float(bbox.get("longitude_min") or 0.0) + inset
    max_lon = float(bbox.get("longitude_max") or 0.0) - inset
    min_lat = float(bbox.get("latitude_min") or 0.0) + inset
    max_lat = float(bbox.get("latitude_max") or 0.0) - inset
    if max_lon <= min_lon or max_lat <= min_lat:
        return {"ok": False, "error": "grid inset exceeds parcel bounds"}
    lon_span = max_lon - min_lon
    lat_span = max_lat - min_lat
    cell_lon = max((lon_span - (spacing * (cols - 1))) / cols, 0.0)
    cell_lat = max((lat_span - (spacing * (rows - 1))) / rows, 0.0)
    plots: list[dict[str, Any]] = []
    for row_idx in range(rows):
        for col_idx in range(cols):
            left = min_lon + (col_idx * (cell_lon + spacing))
            right = left + cell_lon
            bottom = min_lat + (row_idx * (cell_lat + spacing))
            top = bottom + cell_lat
            if right > max_lon or top > max_lat:
                continue
            plots.append(
                {
                    "plot_id": f"r{row_idx + 1}c{col_idx + 1}",
                    "row": row_idx + 1,
                    "column": col_idx + 1,
                    "bbox": {
                        "longitude_min": left,
                        "longitude_max": right,
                        "latitude_min": bottom,
                        "latitude_max": top,
                    },
                }
            )
    return {
        "ok": True,
        "selected_parcel_id": str(parcel.get("parcel_id") or ""),
        "grid_spec": {
            "rows": rows,
            "columns": cols,
            "orientation": orientation,
            "spacing": spacing,
            "inset": inset,
        },
        "plot_count": len(plots),
        "plots": plots,
        "policy": {
            "draft_only": True,
            "writes_anthology": False,
        },
    }


def _no_external_plan(_payload: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
    return True, {"ok": True, "ordered_writes": []}, ""


def _split_refs(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    token = str(value or "").strip()
    return [token] if token else []


def _safe_local_id(canonical_ref: str) -> str:
    token = str(canonical_ref or "").strip()
    if "." in token:
        return token.split(".", 1)[1]
    return token


def _extract_updated_at(row: dict[str, Any]) -> int:
    magnitude = str((row or {}).get("magnitude") or "").strip()
    if magnitude.startswith("{") and magnitude.endswith("}"):
        try:
            payload = json.loads(magnitude)
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            try:
                return int(payload.get("updated_at") or 0)
            except Exception:
                return 0
    return 0


def _build_readback_items(
    *,
    canonical_refs: list[str],
    resource_id_used: str,
    source_scope_hint: str,
) -> list[dict[str, Any]]:
    context = _canonical_anthology_context()
    rows_by_id = context.rows_by_id if isinstance(context.rows_by_id, dict) else {}
    out: list[dict[str, Any]] = []
    for canonical in canonical_refs:
        local_id = _safe_local_id(canonical)
        row = rows_by_id.get(local_id) if isinstance(rows_by_id, dict) else {}
        row = row if isinstance(row, dict) else {}
        source_scope = str(row.get("source_scope") or source_scope_hint or "inherited").strip() or "inherited"
        updated_at = _extract_updated_at(row)
        out.append(
            {
                "canonical_ref": canonical,
                "local_id": local_id,
                "source_scope": source_scope,
                "resource_id_used": resource_id_used,
                "written_locally": bool(source_scope == "portal"),
                "reused_ref": True,
                "updated_at": updated_at,
            }
        )
    out.sort(key=lambda item: (-int(item.get("updated_at") or 0), str(item.get("canonical_ref") or "")))
    return out


def _readback_for_field(field_id: str, *, resource_id_used: str, mutation_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    contracts = default_profile_field_contracts()
    contract = contracts.get(str(field_id or "").strip())
    if contract is None:
        return {
            "items": [],
            "summary": {"created_count": 0, "reused_count": 0, "warnings": ["unknown field contract"], "count": 0},
            "empty_reason": "unknown_field_contract",
        }
    config = _load_active_config_for_write()
    raw = get_path(config, contract.target_path)
    refs = _split_refs(raw)
    items = _build_readback_items(canonical_refs=refs, resource_id_used=resource_id_used, source_scope_hint="inherited")
    summary = mutation_summary if isinstance(mutation_summary, dict) else {}
    created_count = int(summary.get("created_count") or 0)
    reused_count = int(summary.get("reused_count") or 0)
    warnings = [str(item).strip() for item in list(summary.get("warnings") or []) if str(item).strip()]
    return {
        "items": items,
        "summary": {
            "created_count": created_count,
            "reused_count": reused_count,
            "warnings": warnings,
            "count": len(items),
        },
        "empty_reason": "" if items else "no_entries",
    }


def _no_materialization_invariants(*, expected_max_created: int = 0) -> dict[str, Any]:
    anthology_payload = _read_json_object(_data_dir() / "anthology.json")
    has_txa_tree = any(str(key).startswith("4-1-") for key in anthology_payload.keys())
    return {
        "no_txa_tree_materialized": not has_txa_tree,
        "sandbox_source_of_truth_assumed": True,
        "expected_max_created": int(expected_max_created),
    }

def _capability_payload() -> dict[str, Any]:
    payload = _read_json_object(_CAPABILITIES_PATH)
    if not payload:
        return {"schema": "mycite.agro_erp.capabilities.v1", "tool_id": TOOL_ID, "accepted_public_resource_families": [], "templates": []}
    payload.setdefault("schema", "mycite.agro_erp.capabilities.v1")
    payload.setdefault("tool_id", TOOL_ID)
    payload["accepted_public_resource_families"] = [
        str(item).strip() for item in list(payload.get("accepted_public_resource_families") or []) if str(item).strip()
    ]
    templates = payload.get("templates")
    payload["templates"] = [dict(item) for item in templates if isinstance(item, dict)] if isinstance(templates, list) else []
    return payload


def _validate_capability_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if str(payload.get("schema") or "").strip() != "mycite.agro_erp.capabilities.v1":
        errors.append("invalid schema")
    if str(payload.get("tool_id") or "").strip() != TOOL_ID:
        errors.append("invalid tool_id")
    templates = payload.get("templates")
    if not isinstance(templates, list) or not templates:
        errors.append("templates[] is required")
        return False, errors
    for item in templates:
        if not isinstance(item, dict):
            errors.append("template entry must be object")
            continue
        if not str(item.get("template_id") or "").strip():
            errors.append("template_id is required")
        if not isinstance(item.get("fields"), list):
            errors.append(f"template {item.get('template_id')}: fields[] is required")
        storage = item.get("storage")
        if not isinstance(storage, dict):
            errors.append(f"template {item.get('template_id')}: storage object is required")
        else:
            if storage.get("layer") is None or storage.get("value_group") is None:
                errors.append(f"template {item.get('template_id')}: storage.layer and storage.value_group are required")
    return len(errors) == 0, errors


def _template_by_id(template_id: str) -> dict[str, Any] | None:
    token = str(template_id or "").strip()
    if not token:
        return None
    for item in _capability_payload().get("templates") or []:
        if str(item.get("template_id") or "").strip() == token:
            return dict(item)
    return None


def _call_data_api(method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    client = current_app.test_client()
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    response = client.open(path, method=method.upper(), json=payload, headers=headers)
    body = response.get_json(silent=True)
    return int(response.status_code), body if isinstance(body, dict) else {}


def _canonical_target_ref(local_id: str, *, local_msn_id: str) -> str:
    token = str(local_id or "").strip()
    if "." in token:
        return token
    if local_msn_id:
        return f"{local_msn_id}.{token}"
    return token


def _required_refs_for_template(template: dict[str, Any], fields: dict[str, Any], *, local_msn_id: str) -> list[str]:
    refs: list[str] = []
    taxonomy_ref = str(fields.get("taxonomy_ref") or fields.get("txa_id") or "").strip()
    if taxonomy_ref:
        try:
            refs.append(
                normalize_datum_ref(
                    taxonomy_ref,
                    local_msn_id=local_msn_id,
                    require_qualified=True,
                    write_format="dot",
                    field_name="taxonomy_ref",
                )
            )
        except Exception:
            refs.append(taxonomy_ref)
    explicit = template.get("required_refs")
    if isinstance(explicit, list):
        refs.extend([str(item).strip() for item in explicit if str(item).strip()])
    for key in ("boundary_ref", "parcel_ref", "field_ref", "plot_ref"):
        token = str(fields.get(key) or "").strip()
        if token:
            refs.append(token)
    dedupe: list[str] = []
    seen: set[str] = set()
    for item in refs:
        if item and item not in seen:
            seen.add(item)
            dedupe.append(item)
    return dedupe


def _template_payload(template: dict[str, Any], fields: dict[str, Any], *, local_msn_id: str) -> dict[str, Any]:
    taxonomy_ref = str(fields.get("taxonomy_ref") or fields.get("txa_id") or "").strip()
    taxonomy_canonical = ""
    if taxonomy_ref:
        try:
            taxonomy_canonical = normalize_datum_ref(
                taxonomy_ref,
                local_msn_id=local_msn_id,
                require_qualified=True,
                write_format="dot",
                field_name="taxonomy_ref",
            )
        except Exception:
            taxonomy_canonical = taxonomy_ref
    return {
        "template_id": str(template.get("template_id") or "").strip(),
        "schema": str(template.get("schema") or "").strip() or "mycite.agro.template_record.v1",
        "title": str(fields.get("title") or "").strip(),
        "local_id": str(fields.get("local_id") or "").strip(),
        "taxonomy_ref": taxonomy_canonical,
        "duration_days": str(fields.get("duration_days") or "").strip(),
        "notes": str(fields.get("notes") or "").strip(),
    }


def _plan_preview_for_request(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    template_id = str(body.get("template_id") or "").strip()
    source_msn_id = str(body.get("source_msn_id") or "").strip()
    resource_id = str(body.get("resource_id") or "").strip()
    fields = body.get("fields") if isinstance(body.get("fields"), dict) else {}
    if not source_msn_id:
        taxonomy_hint = str(fields.get("taxonomy_ref") or fields.get("txa_id") or "").strip()
        if "." in taxonomy_hint:
            source_msn_id = taxonomy_hint.split(".", 1)[0].strip()
    template = _template_by_id(template_id)
    if template is None:
        return 404, {"ok": False, "error": f"Unknown template_id: {template_id}"}
    resource_family = str(template.get("resource_family") or "").strip()
    requires_external = resource_family.startswith("taxonomy.")
    if requires_external and not source_msn_id:
        return 400, {"ok": False, "error": "source_msn_id is required for taxonomy-backed templates"}
    local_msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    local_id = str(fields.get("local_id") or "").strip()
    if not local_id:
        return 400, {"ok": False, "error": "fields.local_id is required"}
    target_ref = _canonical_target_ref(local_id, local_msn_id=local_msn_id)
    required_refs = _required_refs_for_template(template, fields, local_msn_id=local_msn_id)
    intent = {
        "intent_type": "agro_template",
        "template_id": template_id,
        "field_id": "agro_template",
        "write_mode": "create_new_local_datum",
        "local_msn_id": local_msn_id,
        "source_msn_id": source_msn_id,
        "resource_id": resource_id,
        "required_refs": required_refs,
        "allow_auto_create": bool(template.get("auto_create_missing_prerequisites", False)),
        "fields": {
            **fields,
            "local_id": local_id,
        },
    }
    write_status, write_payload = _call_data_api(
        "POST",
        "/portal/api/data/write/preview",
        {"intent": intent},
    )
    ok = write_status == 200 and bool(write_payload.get("ok"))
    return (200 if ok else 400), {
        "ok": ok,
        "template_id": template_id,
        "source_msn_id": source_msn_id,
        "resource_id": resource_id,
        "target_ref": target_ref,
        "required_refs": required_refs,
        "template_payload": _template_payload(template, fields, local_msn_id=local_msn_id),
        "write_preview": write_payload,
        "plan": write_payload.get("plan") if isinstance(write_payload, dict) else {},
        "errors": [
            str(item)
            for item in [
                write_payload.get("error") if isinstance(write_payload, dict) else "",
            ]
            if str(item or "").strip()
        ],
    }


def _apply_materialization(preview_payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(preview_payload, dict):
        return 400, {"ok": False, "error": "preview payload is required"}
    intent = {
        "intent_type": "agro_template",
        "template_id": str(preview_payload.get("template_id") or "").strip(),
        "field_id": "agro_template",
        "write_mode": "create_new_local_datum",
        "local_msn_id": str(current_app.config.get("MYCITE_MSN_ID") or "").strip(),
        "source_msn_id": str(preview_payload.get("source_msn_id") or "").strip(),
        "resource_id": str(preview_payload.get("resource_id") or "").strip(),
        "required_refs": list(preview_payload.get("required_refs") or []),
        "allow_auto_create": True,
        "fields": {
            **(preview_payload.get("template_payload") if isinstance(preview_payload.get("template_payload"), dict) else {}),
            "local_id": str((preview_payload.get("template_payload") or {}).get("local_id") or "").strip(),
        },
    }
    status, payload = _call_data_api("POST", "/portal/api/data/write/apply", {"intent": intent, "preview": preview_payload.get("write_preview")})
    return status, payload


def _tool_spec() -> ToolDataSpec | None:
    private_dir = _private_dir()
    return load_tool_spec_for_id(private_dir, TOOL_ID)


def _contract_payloads() -> list[dict[str, Any]]:
    private_dir = _private_dir()
    out: list[dict[str, Any]] = []
    for item in list_contracts(private_dir):
        contract_id = str(item.get("contract_id") or "").strip()
        if not contract_id:
            continue
        try:
            out.append(get_contract(private_dir, contract_id))
        except Exception:
            continue
    return out


def _active_config() -> tuple[dict[str, Any], str]:
    payload = _as_dict(current_app.config.get("MYCITE_ACTIVE_PRIVATE_CONFIG"))
    msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    resolved_path = resolve_active_private_config_path(_private_dir(), msn_id or None)
    if payload:
        return payload, str(resolved_path) if resolved_path is not None else ""

    fallback = _read_json_object(resolved_path)
    return fallback, str(resolved_path) if resolved_path is not None else ""


def _anthology_payload() -> tuple[dict[str, Any], str]:
    path = _data_dir() / "anthology.json"
    return _read_json_object(path), str(path)


def _pairs_from_datum(datum: Any) -> tuple[list[dict[str, str]], str]:
    pairs: list[dict[str, str]] = []
    label = ""

    if isinstance(datum, list):
        header = datum[0] if datum and isinstance(datum[0], list) else []
        if isinstance(header, list):
            tokens = [str(item or "").strip() for item in header[1:]]
            for index in range(0, len(tokens) - 1, 2):
                reference = tokens[index]
                magnitude = tokens[index + 1]
                if reference or magnitude:
                    pairs.append({"reference": reference, "magnitude": magnitude})
            if len(tokens) % 2 == 1:
                tail = tokens[-1]
                if tail:
                    pairs.append({"reference": tail, "magnitude": ""})

        label_block = datum[1] if len(datum) > 1 and isinstance(datum[1], list) else []
        if isinstance(label_block, list) and label_block:
            label = str(label_block[0] or "").strip()

        return pairs, label

    if isinstance(datum, dict):
        row_pairs = datum.get("pairs")
        if isinstance(row_pairs, list):
            for item in row_pairs:
                if not isinstance(item, dict):
                    continue
                reference = str(item.get("reference") or "").strip()
                magnitude = str(item.get("magnitude") or "").strip()
                if reference or magnitude:
                    pairs.append({"reference": reference, "magnitude": magnitude})
        else:
            reference = str(datum.get("reference") or "").strip()
            magnitude = str(datum.get("magnitude") or "").strip()
            if reference or magnitude:
                pairs.append({"reference": reference, "magnitude": magnitude})
        label = str(datum.get("label") or "").strip()
        return pairs, label

    magnitude = str(datum or "").strip()
    if magnitude:
        pairs.append({"reference": "", "magnitude": magnitude})
    return pairs, ""


def _signed_axis_value(token: str, *, bits: int) -> int:
    raw_value = int(token, 16)
    sign = 1 << (bits - 1)
    if raw_value & sign:
        raw_value -= 1 << bits
    return raw_value


def _decode_coordinate_token(raw_value: Any) -> dict[str, Any] | None:
    token = str(raw_value or "").strip()
    if token.lower().startswith("0x"):
        token = token[2:]
    token = token.replace("_", "")
    if not token or len(token) % 2 != 0 or not _HEX_RE.fullmatch(token):
        return None

    half = len(token) // 2
    if half < 1:
        return None

    upper = token[:half].upper()
    lower = token[half:].upper()
    axis_bits = half * 4
    longitude_axis = _signed_axis_value(upper, bits=axis_bits)
    latitude_axis = _signed_axis_value(lower, bits=axis_bits)
    longitude = longitude_axis / _COORD_SCALE
    latitude = latitude_axis / _COORD_SCALE
    longitude_text = f"{longitude:.13f}"
    latitude_text = f"{latitude:.13f}"

    return {
        "normalized_hex": f"0x{token.upper()}",
        "axis_bits": axis_bits,
        "longitude_axis": {"hex": f"0x{upper}", "signed_value": longitude_axis},
        "latitude_axis": {"hex": f"0x{lower}", "signed_value": latitude_axis},
        "longitude": longitude,
        "latitude": latitude,
        "pair_text": [longitude_text, latitude_text],
    }


def _resolve_token(token: str, anthology: dict[str, Any]) -> dict[str, Any]:
    raw_token = str(token or "").strip()
    datum_payload = anthology.get(raw_token) if _DATUM_ID_RE.fullmatch(raw_token or "") else None
    pairs, label = _pairs_from_datum(datum_payload) if datum_payload is not None else ([], "")
    first_pair = pairs[0] if pairs else {"reference": "", "magnitude": ""}
    resolved_hex = str(first_pair.get("magnitude") or raw_token).strip()

    decoded = _decode_coordinate_token(resolved_hex)
    source = "anthology_datum" if datum_payload is not None else "raw_token"

    return {
        "token": raw_token,
        "source": source,
        "datum_label": label,
        "pair_reference": str(first_pair.get("reference") or "").strip(),
        "resolved_hex": resolved_hex,
        "decoded": decoded,
        "resolved_pair": decoded.get("pair_text") if isinstance(decoded, dict) else None,
    }


def _resolve_path_tokens(config: dict[str, Any], path: str) -> list[str]:
    node: Any = config
    for segment in path.split("."):
        if not isinstance(node, dict):
            return []
        node = node.get(segment)

    if not isinstance(node, list):
        return []
    return [str(item).strip() for item in node if str(item or "").strip()]


def _polygon_svg(resolved_rows: list[dict[str, Any]]) -> dict[str, Any]:
    decoded_rows = [row.get("decoded") for row in resolved_rows if isinstance(row.get("decoded"), dict)]
    if not decoded_rows:
        return {"available": False, "viewbox": "0 0 420 240", "points": ""}

    width = 420.0
    height = 240.0
    padding = 16.0

    def _coerce_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            token = value.strip()
            if not token:
                return None
            try:
                return float(token)
            except Exception:
                return None
        if isinstance(value, dict):
            # Handle engine-backed decoded variants that may wrap coordinates.
            for key in ("value", "lon", "lat", "longitude", "latitude", "signed_value"):
                nested = value.get(key)
                coerced = _coerce_float(nested)
                if coerced is not None:
                    return coerced
        return None

    coordinates: list[tuple[float, float]] = []
    for row in decoded_rows:
        lon = _coerce_float(row.get("longitude"))
        lat = _coerce_float(row.get("latitude"))
        if lon is None or lat is None:
            continue
        coordinates.append((lon, lat))
    if not coordinates:
        return {"available": False, "viewbox": "0 0 420 240", "points": ""}

    longitudes = [item[0] for item in coordinates]
    latitudes = [item[1] for item in coordinates]
    min_lon = min(longitudes)
    max_lon = max(longitudes)
    min_lat = min(latitudes)
    max_lat = max(latitudes)
    span_lon = max(max_lon - min_lon, 0.0000001)
    span_lat = max(max_lat - min_lat, 0.0000001)
    scale = min((width - (2 * padding)) / span_lon, (height - (2 * padding)) / span_lat)

    points: list[str] = []
    for longitude, latitude in coordinates:
        x = padding + ((longitude - min_lon) * scale)
        y = height - padding - ((latitude - min_lat) * scale)
        points.append(f"{x:.2f},{y:.2f}")

    return {
        "available": len(points) >= 3,
        "viewbox": "0 0 420 240",
        "points": " ".join(points),
        "bounds": {
            "longitude_min": min_lon,
            "longitude_max": max_lon,
            "latitude_min": min_lat,
            "latitude_max": max_lat,
        },
    }


def _product_type_archetype() -> dict[str, Any]:
    """
    Describe the archetype for product-type datums AGRO ERP will create.

    Fields are expressed in logical terms here; mapping to anthology identifiers
    and reference/magnitude pairs is handled by the data engine/directives.
    """
    spec = _tool_spec()
    if spec is not None:
        for entry in spec.outputs:
            if entry.get("id") == "product_type":
                fields = entry.get("fields") if isinstance(entry.get("fields"), list) else []
                return {
                    "schema": str(entry.get("schema") or "mycite.agro.product_type.v1").strip()
                    or "mycite.agro.product_type.v1",
                    "fields": [dict(field) for field in fields if isinstance(field, dict)],
                }

    return {
        "schema": "mycite.agro.product_type.v1",
        "fields": [
            {
                "id": "txa_id",
                "title": "Taxonomy Node",
                "description": "Canonical dot-qualified taxonomy datum reference used to classify the product.",
                "type": "datum_ref",
                "required": True,
            },
            {
                "id": "title",
                "title": "Product Title",
                "description": "Human-readable name for the product type.",
                "type": "string",
                "required": True,
            },
            {
                "id": "gestation_time",
                "title": "Gestation Time",
                "description": "Time from planting/creation to harvest/readiness, expressed in canonical time units.",
                "type": "duration",
                "required": False,
            },
        ],
    }


def _daemon_specs() -> list[dict[str, Any]]:
    return [
        {
            "daemon_id": "property_geometry",
            "title": "Resolve Property Geometry",
            "config_path": "property.geometry.coordinates",
            "description": (
                "Reads property geometry tokens, resolves through anthology when tokens are datum IDs, "
                "then decodes fixed-width signed hex to longitude/latitude."
            ),
            "directive": {
                "script": "inv;(med;property.geometry.coordinates;resolve_coordinate_sequence);1",
                "action": "inv",
                "method": "resolve_coordinate_sequence",
                "subject": "property.geometry.coordinates",
                "aitas_context": {
                    "attention": "property_geometry",
                    "intention": "resolve",
                    "temporal": "present",
                    "archetype": "polygon",
                    "spatial": "geographic",
                    "spacial": "geographic",
                },
            },
        },
        {
            "daemon_id": "property_bbox",
            "title": "Resolve Property Bounding Box",
            "config_path": "property.bbox",
            "description": (
                "Reads property bbox tokens, resolves through anthology when tokens are datum IDs, "
                "then decodes fixed-width signed hex to longitude/latitude."
            ),
            "directive": {
                "script": "inv;(med;property.bbox;resolve_coordinate_sequence);1",
                "action": "inv",
                "method": "resolve_coordinate_sequence",
                "subject": "property.bbox",
                "aitas_context": {
                    "attention": "property_bbox",
                    "intention": "resolve",
                    "temporal": "present",
                    "archetype": "bbox",
                    "spatial": "geographic",
                    "spacial": "geographic",
                },
            },
        },
    ]


def _run_daemon(spec: dict[str, Any], config: dict[str, Any], anthology: dict[str, Any]) -> dict[str, Any]:
    config_path = str(spec.get("config_path") or "").strip()
    tokens = _resolve_path_tokens(config, config_path)
    resolved: list[dict[str, Any]] = []
    coordinate_pairs: list[list[str]] = []
    warnings: list[str] = []
    errors: list[str] = []

    workspace = _workspace()
    if workspace is not None and hasattr(workspace, "daemon_resolve_tokens"):
        engine_result = workspace.daemon_resolve_tokens(
            tokens=tokens,
            standard_id="coordinate_fixed_hex",
            context={"allow_trailing_null": True},
        )
        warnings.extend([str(item) for item in list(engine_result.get("warnings") or [])])
        errors.extend([str(item) for item in list(engine_result.get("errors") or [])])
        for item in list(engine_result.get("resolved") or []):
            if not isinstance(item, dict):
                continue
            mediation = item.get("mediation") if isinstance(item.get("mediation"), dict) else {}
            value = mediation.get("value") if isinstance(mediation, dict) else {}
            decoded = value.get("decoded") if isinstance(value, dict) and isinstance(value.get("decoded"), dict) else None
            lon = value.get("lon") if isinstance(value, dict) else None
            lat = value.get("lat") if isinstance(value, dict) else None
            pair = None
            if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                pair = [f"{float(lon):.13f}", f"{float(lat):.13f}"]
            resolved.append(
                {
                    "token": str(item.get("token") or "").strip(),
                    "source": str(item.get("source") or "engine").strip() or "engine",
                    "datum_label": "",
                    "pair_reference": str(item.get("resolved_reference") or "").strip(),
                    "resolved_hex": str(item.get("resolved_magnitude") or "").strip(),
                    "decoded": decoded,
                    "resolved_pair": pair,
                    "mediation": mediation,
                }
            )
            if isinstance(pair, list):
                coordinate_pairs.append(pair)
    else:
        resolved = [_resolve_token(token, anthology) for token in tokens]
        coordinate_pairs = [row.get("resolved_pair") for row in resolved if isinstance(row.get("resolved_pair"), list)]

    return {
        "daemon_id": str(spec.get("daemon_id") or ""),
        "title": str(spec.get("title") or ""),
        "config_path": config_path,
        "token_count": len(tokens),
        "tokens": tokens,
        "resolved": resolved,
        "resolved_coordinate_pairs": coordinate_pairs,
        "directive": _as_dict(spec.get("directive")),
        "warnings": warnings,
        "errors": errors,
        "policy": {
            "engine_backed": bool(workspace is not None and hasattr(workspace, "daemon_resolve_tokens")),
            "resolution_mode": "constrained_daemon_execution",
        },
    }


def _build_model_payload() -> dict[str, Any]:
    config, config_path = _active_config()
    anthology, anthology_path = _anthology_payload()
    parcel_workspace = _parcel_workspace_payload()
    parcels = [dict(item) for item in list(parcel_workspace.get("parcels") or []) if isinstance(item, dict)]
    active_parcel = next((item for item in parcels if bool(item.get("valid"))), parcels[0] if parcels else {})

    daemon_specs = _daemon_specs()
    daemon_runs = [_run_daemon(spec, config, anthology) for spec in daemon_specs]
    geometry_daemon = next((item for item in daemon_runs if item.get("daemon_id") == "property_geometry"), None)
    bbox_daemon = next((item for item in daemon_runs if item.get("daemon_id") == "property_bbox"), None)

    msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    spec = _tool_spec()
    taxonomy_ref = _DEFAULT_TAXONOMY_REF
    if spec is not None:
        for entry in spec.inherited_inputs:
            if entry.get("id") == "taxonomy_collection":
                token = str(entry.get("datum_ref") or "").strip()
                if token:
                    taxonomy_ref = token
                break
    taxonomy_context = {}
    if msn_id and taxonomy_ref:
        try:
            taxonomy_context = load_inherited_taxonomy(
                datum_ref=taxonomy_ref,
                local_msn_id=msn_id,
                # For foreign taxonomy references, the anthology payload is only
                # used for local resolution; contract MSS decoding is primary.
                anthology_payload=anthology,
                contract_payloads=_contract_payloads(),
            )
        except Exception:
            taxonomy_context = {
                "ok": False,
                "taxonomy_ref": taxonomy_ref,
                "scope": "contract_mss",
                "reason": "Exception while loading inherited taxonomy context",
            }
    capabilities = _capability_payload()
    capabilities_ok, capability_errors = _validate_capability_payload(capabilities)

    return {
        "tool_id": TOOL_ID,
        "portal_instance_id": str(current_app.config.get("MYCITE_PORTAL_INSTANCE_ID") or ""),
        "msn_id": str(current_app.config.get("MYCITE_MSN_ID") or ""),
        "active_config_path": config_path,
        "anthology_path": anthology_path,
        "tabs": ["plan", "inventory", "products", "taxonomy"],
        "parcel_workspace": parcel_workspace,
        "active_parcel_id": str(active_parcel.get("parcel_id") or ""),
        "active_parcel_polygon_svg": _polygon_svg_for_parcel(active_parcel if isinstance(active_parcel, dict) else {}),
        "property_title": str(active_parcel.get("title") or "property").strip(),
        "property_geometry_type": str(active_parcel.get("geometry_type") or "Polygon").strip() or "Polygon",
        "raw_property_bbox": list(active_parcel.get("bbox_refs") or []),
        "raw_property_geometry_coordinates": list(active_parcel.get("geometry_refs") or []),
        "daemons": daemon_runs,
        "geometry_daemon": geometry_daemon or {},
        "bbox_daemon": bbox_daemon or {},
        "polygon_svg": _polygon_svg(
            geometry_daemon.get("resolved", []) if isinstance(geometry_daemon, dict) else []
        ),
        "taxonomy": {
            "ok": bool(taxonomy_context.get("ok")) if isinstance(taxonomy_context, dict) else False,
            "ref": str(taxonomy_context.get("taxonomy_ref") or taxonomy_ref) if isinstance(taxonomy_context, dict) else taxonomy_ref,
            "scope": str(taxonomy_context.get("scope") or "") if isinstance(taxonomy_context, dict) else "",
            "root_identifier": str(taxonomy_context.get("root_identifier") or "") if isinstance(taxonomy_context, dict) else "",
            "tree": taxonomy_context.get("tree") if isinstance(taxonomy_context, dict) else {},
        },
        "product_type_archetype": _product_type_archetype(),
        "capabilities": capabilities,
        "capabilities_ok": capabilities_ok,
        "capability_errors": capability_errors,
        "agro_routes": {
            "capabilities": "/portal/tools/agro_erp/capabilities.json",
            "resources": "/portal/api/data/external/resources",
            "plan_preview": "/portal/tools/agro_erp/plan_preview",
            "apply": "/portal/tools/agro_erp/apply",
            "mvp_live_state_gate": "/portal/tools/agro_erp/mvp/live_state_gate",
            "mvp_resource_select": "/portal/tools/agro_erp/mvp/resource/select_or_load",
            "mvp_product_preview": "/portal/tools/agro_erp/mvp/product/preview",
            "mvp_product_apply": "/portal/tools/agro_erp/mvp/product/apply",
            "mvp_invoice_preview": "/portal/tools/agro_erp/mvp/invoice/preview",
            "mvp_invoice_apply": "/portal/tools/agro_erp/mvp/invoice/apply",
            "mvp_readback": "/portal/tools/agro_erp/mvp/workflow/readback",
            "plan_grid_preview": "/portal/tools/agro_erp/plan/grid_preview",
            "plot_plan_draft_save": "/portal/tools/agro_erp/plan/draft/save",
            "plot_plan_draft_load": "/portal/tools/agro_erp/plan/draft/load",
        },
    }


def _live_state_gate_payload() -> dict[str, Any]:
    data_root = _data_dir()
    anthology_path = data_root / "anthology.json"
    anthology_payload = _read_json_object(anthology_path)
    sandbox_resources = data_root / "sandbox" / "resources"
    resource_files = sorted([item.name for item in sandbox_resources.glob("*.json")]) if sandbox_resources.exists() else []
    txa_resource_ids: list[str] = []
    msn_resource_ids: list[str] = []
    for filename in resource_files:
        path = sandbox_resources / filename
        payload = _read_json_object(path)
        rid = str(payload.get("resource_id") or filename.rsplit(".", 1)[0]).strip()
        kind = str(payload.get("resource_kind") or payload.get("kind") or "").strip().lower()
        if kind == "txa":
            txa_resource_ids.append(rid)
        if kind == "msn":
            msn_resource_ids.append(rid)
    txa_resource_ids = sorted(set(txa_resource_ids))
    msn_resource_ids = sorted(set(msn_resource_ids))

    has_layer4_tree = any(str(key).startswith("4-1-") for key in anthology_payload.keys())
    has_selector_rows = any(str(key) in {"5-0-1", "5-0-2"} for key in anthology_payload.keys())
    config = _load_active_config_for_write()
    product_ref = str(get_path(config, "agro.inherited.product_profile_ref") or "").strip()
    invoice_ref = str(get_path(config, "agro.inherited.supply_log_ref") or "").strip()
    refs_ok = True
    refs_errors: list[str] = []
    for field_name, token in (("product_profile_ref", product_ref), ("supply_log_ref", invoice_ref)):
        if token and "." not in token:
            refs_ok = False
            refs_errors.append(f"{field_name} is not canonical ref: {token}")
    hidden_dependency = False
    hidden_details: list[str] = []
    for token in [product_ref, invoice_ref]:
        if ".4-1-" in token:
            hidden_dependency = True
            hidden_details.append(token)
    for key, value in anthology_payload.items():
        row_text = json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list)) else str(value)
        if "4-1-" in row_text and str(key).startswith(("8-4-", "8-5-")):
            hidden_dependency = True
            hidden_details.append(str(key))

    checks = [
        {
            "check_id": "isolated_resource_files_exist",
            "status": "PASS" if bool(txa_resource_ids) else "FAIL",
            "detail": {"resource_files": resource_files, "txa_resource_ids": txa_resource_ids, "msn_resource_ids": msn_resource_ids},
            "remediation": "Run sandbox migration/compile so txa resource JSON files exist." if not txa_resource_ids else "",
        },
        {
            "check_id": "anthology_owns_no_full_txa_tree",
            "status": "PASS" if not has_layer4_tree and not has_selector_rows else "FAIL",
            "detail": {"has_layer4_1_rows": has_layer4_tree, "has_5_0_selectors": has_selector_rows},
            "remediation": "Re-run extraction migration to remove txa/msn trees from anthology." if has_layer4_tree or has_selector_rows else "",
        },
        {
            "check_id": "txa_resource_ids_known",
            "status": "PASS" if bool(txa_resource_ids) else "FAIL",
            "detail": {"txa_resource_ids": txa_resource_ids},
            "remediation": "Pin one txa resource_id for MVP workflow fixtures." if not txa_resource_ids else "",
        },
        {
            "check_id": "product_invoice_reads_ok_after_migration",
            "status": "PASS" if refs_ok else "FAIL",
            "detail": {"product_profile_ref": product_ref, "supply_log_ref": invoice_ref, "errors": refs_errors},
            "remediation": "Normalize config refs to canonical msn_id.datum_id format." if not refs_ok else "",
        },
        {
            "check_id": "no_hidden_local_txa_subtree_dependency",
            "status": "PASS" if not hidden_dependency else "FAIL",
            "detail": {"hits": hidden_details},
            "remediation": "Remove direct 4-1-* dependencies from profile/invoice paths and use inherited refs only." if hidden_dependency else "",
        },
    ]
    overall_ok = all(item.get("status") == "PASS" for item in checks)
    return {
        "ok": overall_ok,
        "checks": checks,
        "committed_resource_ids": {"txa_resource_ids": txa_resource_ids, "msn_resource_ids": msn_resource_ids},
        "anthology_path": str(anthology_path),
        "sandbox_resource_dir": str(sandbox_resources),
    }


def _compile_and_adapt_resource_context(*, resource_ref: str) -> dict[str, Any]:
    local_msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    resolver = _external_resolver()
    sandbox = _sandbox_engine()
    canonical_context = _canonical_anthology_context()
    token = str(resource_ref or "").strip()
    if token.startswith("sandbox:") or "." not in token:
        rid = token.split(":", 1)[1] if token.startswith("sandbox:") else token
        sandbox.compile_isolated_mss_resource(resource_id=rid)
        token = f"sandbox:{rid}"
    inherited = sandbox.compile_txa_inherited_context(
        resource_ref=token,
        local_msn_id=local_msn_id,
        external_resolver=resolver,
        merged_rows_by_id=canonical_context.rows_by_id,
    )
    resolved = sandbox.resolve_inherited_resource_context(
        resource_ref=token,
        local_msn_id=local_msn_id,
        external_resolver=resolver,
    )
    adapted = sandbox.adapt_published_txa_context(
        published_resource_value=resolved.resource_value if resolved.ok and isinstance(resolved.resource_value, dict) else {},
        context_source="agro_erp.mvp.resource_select",
    )
    return {
        "resource_ref": token,
        "inherited_context": inherited,
        "resolved_context": resolved.to_dict(),
        "adapted_context": adapted,
    }


def _preview_inherited_write(*, field_id: str, resource_ref: str, inherited_ref_override: str = "") -> dict[str, Any]:
    built = _compile_and_adapt_resource_context(resource_ref=resource_ref)
    inherited = built.get("inherited_context") if isinstance(built.get("inherited_context"), dict) else {}
    selection: dict[str, Any]
    if str(inherited_ref_override or "").strip():
        selection = {"selected_ref": str(inherited_ref_override).strip(), "selection_source": "explicit_input", "warnings": []}
    else:
        selection = select_inherited_binding_for_field(
            field_id=field_id,
            field_ref_bindings=(inherited.get("field_ref_bindings") if isinstance(inherited.get("field_ref_bindings"), dict) else {}),
        )
    local_msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    intent = {
        "intent_type": "profile_field",
        "field_id": field_id,
        "write_mode": "stage_inherited_ref",
        "resource_ref": resource_ref,
        "local_msn_id": local_msn_id,
        "fields": {"inherited_ref": str(selection.get("selected_ref") or "").strip()},
        "inherited_context": inherited,
    }
    preview = preview_write_intent(
        intent=intent,
        current_config=_load_active_config_for_write(),
        local_anthology_payload=_canonical_anthology_context().rows_payload,
        external_plan_fn=_no_external_plan,
    )
    return {
        "ok": preview.ok,
        "preview": preview.to_dict(),
        "selection": selection,
        "resource_context": built,
        "errors": list(preview.errors),
        "warnings": list(preview.warnings) + [str(item).strip() for item in list(selection.get("warnings") or []) if str(item).strip()],
    }

@agro_erp_bp.get("/portal/tools/agro_erp/home")
def agro_erp_home():
    model = _build_model_payload()
    return render_template(
        "tools/agro_erp_home.html",
        model=model,
        model_json=json.dumps(model, indent=2, sort_keys=True),
    )


@agro_erp_bp.get("/portal/tools/agro_erp/model.json")
def agro_erp_model_json():
    return jsonify(_build_model_payload())


@agro_erp_bp.get("/portal/tools/agro_erp/capabilities.json")
def agro_erp_capabilities_json():
    payload = _capability_payload()
    ok, errors = _validate_capability_payload(payload)
    return jsonify({"ok": ok, "errors": errors, "capabilities": payload}), (200 if ok else 500)


@agro_erp_bp.get("/portal/tools/agro_erp/resources")
def agro_erp_public_resources():
    source_msn_id = str(request.args.get("source_msn_id") or "").strip()
    if not source_msn_id:
        abort(400, description="source_msn_id is required")
    status, payload = _call_data_api("GET", f"/portal/api/data/external/resources?source_msn_id={source_msn_id}")
    return jsonify(payload), status


@agro_erp_bp.post("/portal/tools/agro_erp/plan_preview")
def agro_erp_plan_preview():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    status, payload = _plan_preview_for_request(body)
    return jsonify(payload), status


@agro_erp_bp.post("/portal/tools/agro_erp/apply")
def agro_erp_apply():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    preview = body.get("preview") if isinstance(body.get("preview"), dict) else None
    if preview is None:
        status, preview_payload = _plan_preview_for_request(body)
        if status != 200:
            return jsonify(preview_payload), status
        preview = preview_payload
    status, payload = _apply_materialization(preview)
    if status == 200:
        try:
            append_audit_event(
                _private_dir(),
                {
                    "type": "agro.template.materialized",
                    "template_id": str(preview.get("template_id") or ""),
                    "resource_id": str(preview.get("resource_id") or ""),
                    "source_msn_id": str(preview.get("source_msn_id") or ""),
                    "target_ref": str(preview.get("target_ref") or ""),
                    "ordered_writes": list(((preview.get("plan") or {}).get("ordered_writes") or [])),
                },
            )
        except Exception:
            pass
    return jsonify(payload), status


@agro_erp_bp.post("/portal/tools/agro_erp/plan/grid_preview")
def agro_erp_plan_grid_preview():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    parcel_id = str(body.get("parcel_id") or "").strip()
    if not parcel_id:
        abort(400, description="parcel_id is required")
    workspace = _parcel_workspace_payload()
    parcel = _parcel_by_id(workspace, parcel_id)
    if parcel is None:
        abort(404, description=f"Unknown parcel_id: {parcel_id}")
    grid_spec = body.get("grid_spec") if isinstance(body.get("grid_spec"), dict) else {}
    overlay = _plot_overlay_for_parcel(parcel, grid_spec)
    ok = bool(overlay.get("ok"))
    return jsonify({"ok": ok, "selected_parcel": parcel, "overlay": overlay}), (200 if ok else 400)


@agro_erp_bp.post("/portal/tools/agro_erp/plan/draft/save")
def agro_erp_plan_draft_save():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    parcel_id = str(body.get("parcel_id") or "").strip()
    if not parcel_id:
        abort(400, description="parcel_id is required")
    workspace = _parcel_workspace_payload()
    parcel = _parcel_by_id(workspace, parcel_id)
    if parcel is None:
        abort(404, description=f"Unknown parcel_id: {parcel_id}")
    grid_spec = body.get("grid_spec") if isinstance(body.get("grid_spec"), dict) else {}
    overlay = _plot_overlay_for_parcel(parcel, grid_spec)
    if not bool(overlay.get("ok")):
        return jsonify({"ok": False, "error": str(overlay.get("error") or "grid preview failed"), "overlay": overlay}), 400
    resource_id = str(body.get("resource_id") or "").strip() or f"plot_plan.{parcel_id}.{uuid4().hex[:8]}"
    draft_payload = {
        "schema": "mycite.sandbox.plot_plan.v1",
        "resource_id": resource_id,
        "resource_kind": "plot_plan",
        "origin_kind": "agro_erp.plan",
        "selected_parcel_id": parcel_id,
        "parcel_geometry_snapshot": {
            "parcel_id": parcel_id,
            "title": str(parcel.get("title") or ""),
            "bbox_summary": dict(parcel.get("bbox_summary") if isinstance(parcel.get("bbox_summary"), dict) else {}),
            "polygon": [dict(item) for item in list(parcel.get("polygon") or []) if isinstance(item, dict)],
            "geometry_refs": list(parcel.get("geometry_refs") or []),
            "bbox_refs": list(parcel.get("bbox_refs") or []),
        },
        "grid_spec": dict(overlay.get("grid_spec") if isinstance(overlay.get("grid_spec"), dict) else {}),
        "plot_overlay": {
            "plot_count": int(overlay.get("plot_count") or 0),
            "plots": [dict(item) for item in list(overlay.get("plots") or []) if isinstance(item, dict)],
        },
        "compile_metadata": {
            "draft_only": True,
            "writes_anthology": False,
            "phase": "agro_plan_grid_mvp",
        },
        "updated_at": int(time.time()),
    }
    result = _sandbox_engine().save_resource(resource_id, draft_payload)
    out = result.to_dict()
    out["draft"] = draft_payload
    out["ok"] = bool(result.ok)
    return jsonify(out), (200 if result.ok else 400)


@agro_erp_bp.get("/portal/tools/agro_erp/plan/draft/load")
def agro_erp_plan_draft_load():
    resource_id = str(request.args.get("resource_id") or "").strip()
    if not resource_id:
        abort(400, description="resource_id is required")
    payload = _sandbox_engine().get_resource(resource_id)
    if bool(payload.get("missing")):
        return jsonify({"ok": False, "error": f"resource not found: {resource_id}"}), 404
    return jsonify({"ok": True, "draft": payload})


@agro_erp_bp.post("/portal/tools/agro_erp/daemon/resolve")
def agro_erp_daemon_resolve():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    payload = request.get_json(silent=True)
    body = payload if isinstance(payload, dict) else {}

    config, _ = _active_config()
    anthology, _ = _anthology_payload()
    daemon_specs = {str(item.get("daemon_id") or ""): item for item in _daemon_specs()}

    daemon_id = str(body.get("daemon_id") or "").strip()
    if daemon_id:
        spec = daemon_specs.get(daemon_id)
        if spec is None:
            abort(404, description=f"Unknown daemon_id: {daemon_id}")
        return jsonify({"ok": True, "result": _run_daemon(spec, config, anthology)})

    raw_tokens = body.get("tokens")
    if not isinstance(raw_tokens, list):
        abort(400, description="Provide daemon_id or tokens[]")

    tokens = [str(token).strip() for token in raw_tokens if str(token or "").strip()]
    workspace = _workspace()
    resolved: list[dict[str, Any]]
    warnings: list[str] = []
    errors: list[str] = []
    if workspace is not None and hasattr(workspace, "daemon_resolve_tokens"):
        engine_result = workspace.daemon_resolve_tokens(
            tokens=tokens,
            standard_id="coordinate_fixed_hex",
            context={"allow_trailing_null": True},
        )
        warnings.extend([str(item) for item in list(engine_result.get("warnings") or [])])
        errors.extend([str(item) for item in list(engine_result.get("errors") or [])])
        resolved = []
        for item in list(engine_result.get("resolved") or []):
            if not isinstance(item, dict):
                continue
            mediation = item.get("mediation") if isinstance(item.get("mediation"), dict) else {}
            value = mediation.get("value") if isinstance(mediation, dict) else {}
            decoded = value.get("decoded") if isinstance(value, dict) and isinstance(value.get("decoded"), dict) else None
            lon = value.get("lon") if isinstance(value, dict) else None
            lat = value.get("lat") if isinstance(value, dict) else None
            pair = None
            if isinstance(lon, (int, float)) and isinstance(lat, (int, float)):
                pair = [f"{float(lon):.13f}", f"{float(lat):.13f}"]
            resolved.append(
                {
                    "token": str(item.get("token") or "").strip(),
                    "source": str(item.get("source") or "engine").strip() or "engine",
                    "datum_label": "",
                    "pair_reference": str(item.get("resolved_reference") or "").strip(),
                    "resolved_hex": str(item.get("resolved_magnitude") or "").strip(),
                    "decoded": decoded,
                    "resolved_pair": pair,
                    "mediation": mediation,
                }
            )
    else:
        resolved = [_resolve_token(token, anthology) for token in tokens]
    return jsonify(
        {
            "ok": True,
            "result": {
                "daemon_id": "adhoc_tokens",
                "token_count": len(tokens),
                "tokens": tokens,
                "resolved": resolved,
                "resolved_coordinate_pairs": [
                    row.get("resolved_pair") for row in resolved if isinstance(row.get("resolved_pair"), list)
                ],
                "warnings": warnings,
                "errors": errors,
                "policy": {
                    "engine_backed": bool(workspace is not None and hasattr(workspace, "daemon_resolve_tokens")),
                    "resolution_mode": "constrained_daemon_execution",
                },
            },
        }
    )


@agro_erp_bp.post("/portal/tools/agro_erp/product_types")
def agro_erp_product_types_save():
    """Compatibility route that delegates to planner-driven template apply flow."""
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    fields = {
        "local_id": str(body.get("local_id") or "20-1-1").strip() or "20-1-1",
        "taxonomy_ref": str(body.get("txa_id") or body.get("taxonomy_ref") or "").strip(),
        "title": str(body.get("title") or "").strip(),
        "duration_days": str(body.get("gestation_time") or "").strip(),
        "notes": str(body.get("notes") or "").strip(),
    }
    source_msn_id = str(body.get("source_msn_id") or "").strip()
    resource_id = str(body.get("resource_id") or "farm_metrics").strip() or "farm_metrics"
    status, preview = _plan_preview_for_request(
        {
            "template_id": "livestock.product_type",
            "source_msn_id": source_msn_id,
            "resource_id": resource_id,
            "fields": fields,
        }
    )
    if status != 200:
        return jsonify(preview), status
    apply_status, apply_payload = _apply_materialization(preview)
    return jsonify(apply_payload), apply_status


@agro_erp_bp.get("/portal/tools/agro_erp/mvp/live_state_gate")
def agro_erp_mvp_live_state_gate():
    payload = _live_state_gate_payload()
    return jsonify(payload), (200 if bool(payload.get("ok")) else 409)


@agro_erp_bp.post("/portal/tools/agro_erp/mvp/resource/select_or_load")
def agro_erp_mvp_resource_select_or_load():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    resource_ref = str(body.get("resource_ref") or "").strip()
    if not resource_ref:
        source_msn_id = str(body.get("source_msn_id") or "").strip()
        resource_id = str(body.get("resource_id") or "").strip()
        local_resource_id = str(body.get("local_resource_id") or "").strip()
        if source_msn_id and resource_id:
            resource_ref = f"{source_msn_id}.{resource_id}"
        elif local_resource_id:
            resource_ref = f"sandbox:{local_resource_id}"
    if not resource_ref:
        abort(400, description="resource_ref or source_msn_id/resource_id is required")
    payload = _compile_and_adapt_resource_context(resource_ref=resource_ref)
    adapted = payload.get("adapted_context") if isinstance(payload.get("adapted_context"), dict) else {}
    ok = bool((payload.get("inherited_context") or {}).get("ok")) and bool(adapted.get("ok"))
    return jsonify({"ok": ok, **payload}), (200 if ok else 400)


@agro_erp_bp.post("/portal/tools/agro_erp/mvp/product/preview")
def agro_erp_mvp_product_preview():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    resource_ref = str(body.get("resource_ref") or "").strip()
    if not resource_ref:
        abort(400, description="resource_ref is required")
    payload = _preview_inherited_write(
        field_id="inherited_product_profile_ref",
        resource_ref=resource_ref,
        inherited_ref_override=str(body.get("inherited_ref") or "").strip(),
    )
    return jsonify(payload), (200 if bool(payload.get("ok")) else 400)


@agro_erp_bp.post("/portal/tools/agro_erp/mvp/product/apply")
def agro_erp_mvp_product_apply():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    resource_ref = str(body.get("resource_ref") or "").strip()
    if not resource_ref:
        abort(400, description="resource_ref is required")
    preview_payload = _preview_inherited_write(
        field_id="inherited_product_profile_ref",
        resource_ref=resource_ref,
        inherited_ref_override=str(body.get("inherited_ref") or "").strip(),
    )
    if not bool(preview_payload.get("ok")):
        return jsonify(preview_payload), 400
    preview = preview_payload.get("preview") if isinstance(preview_payload.get("preview"), dict) else {}
    from _shared.portal.data_engine.write_pipeline import WritePreviewResult

    obj = WritePreviewResult(
        ok=bool(preview.get("ok")),
        intent=dict(preview.get("intent") or {}),
        validation=dict(preview.get("validation") or {}),
        plan=dict(preview.get("plan") or {}),
        config_updates=[dict(item) for item in list(preview.get("config_updates") or []) if isinstance(item, dict)],
        write_actions=[dict(item) for item in list(preview.get("write_actions") or []) if isinstance(item, dict)],
        warnings=[str(item) for item in list(preview.get("warnings") or [])],
        errors=[str(item) for item in list(preview.get("errors") or [])],
    )
    result = apply_write_preview(
        preview=obj,
        workspace=_workspace(),
        load_config_fn=_load_active_config_for_write,
        save_config_fn=_save_active_config_for_write,
    )
    readback = _readback_for_field(
        "inherited_product_profile_ref",
        resource_id_used=str((preview_payload.get("resource_context") or {}).get("resource_ref") or resource_ref),
        mutation_summary=result.to_dict().get("mutation_summary") if isinstance(result.to_dict(), dict) else {},
    )
    out = result.to_dict()
    out["readback"] = readback
    out["preview"] = preview_payload
    out["invariants"] = _no_materialization_invariants(expected_max_created=0)
    out["invariants"]["minimal_local_rows_bound_ok"] = int((out.get("mutation_summary") or {}).get("created_count") or 0) <= 0
    return jsonify(out), (200 if result.ok else 400)


@agro_erp_bp.post("/portal/tools/agro_erp/mvp/invoice/preview")
def agro_erp_mvp_invoice_preview():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    resource_ref = str(body.get("resource_ref") or "").strip()
    if not resource_ref:
        abort(400, description="resource_ref is required")
    payload = _preview_inherited_write(
        field_id="inherited_supply_log_ref",
        resource_ref=resource_ref,
        inherited_ref_override=str(body.get("inherited_ref") or "").strip(),
    )
    return jsonify(payload), (200 if bool(payload.get("ok")) else 400)


@agro_erp_bp.post("/portal/tools/agro_erp/mvp/invoice/apply")
def agro_erp_mvp_invoice_apply():
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")
    resource_ref = str(body.get("resource_ref") or "").strip()
    if not resource_ref:
        abort(400, description="resource_ref is required")
    preview_payload = _preview_inherited_write(
        field_id="inherited_supply_log_ref",
        resource_ref=resource_ref,
        inherited_ref_override=str(body.get("inherited_ref") or "").strip(),
    )
    if not bool(preview_payload.get("ok")):
        return jsonify(preview_payload), 400
    preview = preview_payload.get("preview") if isinstance(preview_payload.get("preview"), dict) else {}
    from _shared.portal.data_engine.write_pipeline import WritePreviewResult

    obj = WritePreviewResult(
        ok=bool(preview.get("ok")),
        intent=dict(preview.get("intent") or {}),
        validation=dict(preview.get("validation") or {}),
        plan=dict(preview.get("plan") or {}),
        config_updates=[dict(item) for item in list(preview.get("config_updates") or []) if isinstance(item, dict)],
        write_actions=[dict(item) for item in list(preview.get("write_actions") or []) if isinstance(item, dict)],
        warnings=[str(item) for item in list(preview.get("warnings") or [])],
        errors=[str(item) for item in list(preview.get("errors") or [])],
    )
    result = apply_write_preview(
        preview=obj,
        workspace=_workspace(),
        load_config_fn=_load_active_config_for_write,
        save_config_fn=_save_active_config_for_write,
    )
    readback = _readback_for_field(
        "inherited_supply_log_ref",
        resource_id_used=str((preview_payload.get("resource_context") or {}).get("resource_ref") or resource_ref),
        mutation_summary=result.to_dict().get("mutation_summary") if isinstance(result.to_dict(), dict) else {},
    )
    out = result.to_dict()
    out["readback"] = readback
    out["preview"] = preview_payload
    out["invariants"] = _no_materialization_invariants(expected_max_created=0)
    out["invariants"]["minimal_local_rows_bound_ok"] = int((out.get("mutation_summary") or {}).get("created_count") or 0) <= 0
    return jsonify(out), (200 if result.ok else 400)


@agro_erp_bp.get("/portal/tools/agro_erp/mvp/workflow/readback")
def agro_erp_mvp_workflow_readback():
    resource_ref = str(request.args.get("resource_ref") or "").strip()
    product = _readback_for_field("inherited_product_profile_ref", resource_id_used=resource_ref, mutation_summary={})
    invoice = _readback_for_field("inherited_supply_log_ref", resource_id_used=resource_ref, mutation_summary={})
    return jsonify(
        {
            "ok": True,
            "resource_ref": resource_ref,
            "product_types": product,
            "invoice_log": invoice,
        }
    )


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
