"""
View-model helpers for the Local Resources / sandbox resource workbench UI.

Builds anthology-esque structured row summaries and SAMRAS hints from the same
resource bodies returned by ``GET /portal/api/data/sandbox/resources/<id>``.
"""

from __future__ import annotations

from typing import Any


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


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
        "understanding": understanding_brief(datum_understanding),
        "rule_policy_keys": sorted(rule_policy_by_id.keys()) if isinstance(rule_policy_by_id, dict) else [],
    }


__all__ = [
    "build_resource_workbench_view_model",
    "build_samras_row_summaries",
    "extract_anthology_rows_payload",
    "is_samras_backed_resource",
    "understanding_brief",
]
