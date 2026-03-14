from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, render_template, request

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
_DEFAULT_TAXONOMY_REF = "3-2-3-17-77-1-6-4-1-4.4-0-2"
_PRODUCT_LAYER = 20
_PRODUCT_VALUE_GROUP = 1
_PRODUCT_REFERENCE = "0-0-1"


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

    longitudes = [float(row.get("longitude") or 0.0) for row in decoded_rows]
    latitudes = [float(row.get("latitude") or 0.0) for row in decoded_rows]
    min_lon = min(longitudes)
    max_lon = max(longitudes)
    min_lat = min(latitudes)
    max_lat = max(latitudes)
    span_lon = max(max_lon - min_lon, 0.0000001)
    span_lat = max(max_lat - min_lat, 0.0000001)
    scale = min((width - (2 * padding)) / span_lon, (height - (2 * padding)) / span_lat)

    points: list[str] = []
    for row in decoded_rows:
        longitude = float(row.get("longitude") or 0.0)
        latitude = float(row.get("latitude") or 0.0)
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
    property_cfg = _as_dict(config.get("property"))
    geometry_cfg = _as_dict(property_cfg.get("geometry"))

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

    return {
        "tool_id": TOOL_ID,
        "portal_instance_id": str(current_app.config.get("MYCITE_PORTAL_INSTANCE_ID") or ""),
        "msn_id": str(current_app.config.get("MYCITE_MSN_ID") or ""),
        "active_config_path": config_path,
        "anthology_path": anthology_path,
        "property_title": str(property_cfg.get("title") or "property").strip(),
        "property_geometry_type": str(geometry_cfg.get("type") or "Polygon").strip() or "Polygon",
        "raw_property_bbox": _resolve_path_tokens(config, "property.bbox"),
        "raw_property_geometry_coordinates": _resolve_path_tokens(config, "property.geometry.coordinates"),
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
    """
    Create a new product-type datum in the local anthology.

    The payload is a simple JSON object with fields aligned to the
    product_type_archetype (txa_id, title, gestation_time). The record is
    persisted via the shared data engine so that anthology compaction and
    mediation remain consistent with the Data Tool.
    """
    if not request.is_json:
        abort(415, description="Expected application/json body")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Expected JSON object body")

    txa_raw = str(body.get("txa_id") or "").strip()
    title = str(body.get("title") or "").strip()
    gestation_raw = body.get("gestation_time")

    if not txa_raw or not title:
        abort(400, description="txa_id and title are required fields")

    msn_id = str(current_app.config.get("MYCITE_MSN_ID") or "").strip()
    try:
        txa_canonical = normalize_datum_ref(
            txa_raw,
            local_msn_id=msn_id,
            require_qualified=True,
            write_format="dot",
            field_name="txa_id",
        )
    except Exception as exc:
        abort(400, description=f"Invalid txa_id: {exc}")

    if isinstance(gestation_raw, (int, float)):
        gestation_token = str(int(gestation_raw))
    else:
        gestation_token = str(gestation_raw or "").strip()

    magnitude_payload = {
        "txa_id": txa_canonical,
        "title": title,
        "gestation_time": gestation_token,
    }

    workspace = _workspace()
    if workspace is None or not hasattr(workspace, "append_anthology_datum"):
        abort(500, description="Data workspace is not available for anthology writes")

    result = workspace.append_anthology_datum(
        layer=_PRODUCT_LAYER,
        value_group=_PRODUCT_VALUE_GROUP,
        reference=_PRODUCT_REFERENCE,
        magnitude=json.dumps(magnitude_payload, separators=(",", ":")),
        label=title,
    )

    ok = bool(result.get("ok"))
    if not ok:
        errors = [str(item) for item in list(result.get("errors") or [])]
        abort(400, description="; ".join(errors) or "Failed to append product-type datum")

    identifier = str(result.get("identifier") or "")
    row = result.get("row") or {}

    private_dir = _private_dir()
    try:
        append_audit_event(
            private_dir,
            {
                "type": "agro.product_type.created",
                "scope": "local_product_type",
                "identifier": identifier,
                "title": title,
                "gestation_time": gestation_token,
                "txa_id": txa_canonical,
                "msn_id": msn_id or "",
            },
        )
    except Exception:
        # Audit log failures should not block primary persistence.
        pass

    return jsonify(
        {
            "ok": True,
            "identifier": identifier,
            "row": row,
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
