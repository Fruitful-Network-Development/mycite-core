"""Probe merges + write gating driven by ``understand_datums`` (not ``rule_key``)."""

from __future__ import annotations

from typing import Any

from .base import as_text, parse_datum_id
from .policy import derive_rule_policy, gate_write_attempt


def _rows_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    rows_obj = payload.get("rows") if isinstance(payload, dict) else None
    return dict(rows_obj) if isinstance(rows_obj, dict) else {}


def merge_row_into_rows_payload(base: dict[str, Any], row_id: str, row_dict: dict[str, Any]) -> dict[str, Any]:
    rows_obj = base.get("rows") if isinstance(base, dict) else None
    rows = dict(rows_obj) if isinstance(rows_obj, dict) else {}
    out: dict[str, Any] = {k: v for k, v in base.items() if isinstance(base, dict) and k != "rows"}
    out["rows"] = dict(rows)
    out["rows"][as_text(row_id)] = dict(row_dict)
    return out


def compute_next_append_datum_id(payload: dict[str, Any], layer: int, value_group: int) -> str:
    rows = _rows_mapping(payload if isinstance(payload, dict) else {})
    existing = {as_text(rid) for rid in rows.keys()}
    max_iter = 0
    for rid in rows:
        l_g, v_g, it = parse_datum_id(rid)
        if l_g == layer and v_g == value_group and isinstance(it, int):
            max_iter = max(max_iter, it)
    n = max_iter + 1
    cand = f"{layer}-{value_group}-{n}"
    while cand in existing:
        n += 1
        cand = f"{layer}-{value_group}-{n}"
    return cand


def build_append_row_dict(
    *,
    datum_id: str,
    label: str,
    pairs: list[dict[str, str]],
    reference: str = "",
    magnitude: str = "",
) -> dict[str, Any]:
    raw_pairs = [{"reference": as_text(p.get("reference")), "magnitude": as_text(p.get("magnitude"))} for p in pairs if isinstance(p, dict)]
    if not raw_pairs:
        raw_pairs = [{"reference": as_text(reference), "magnitude": as_text(magnitude)}]
    first_ref, first_mag = raw_pairs[0]["reference"], raw_pairs[0]["magnitude"]
    _, vg, _ = parse_datum_id(datum_id)
    row: dict[str, Any] = {
        "row_id": datum_id,
        "identifier": datum_id,
        "label": as_text(label),
        "pairs": raw_pairs,
        "reference": first_ref,
        "magnitude": first_mag,
    }
    if vg == 0:
        row["reference"] = ""
        row["magnitude"] = ""
    return row


def build_updated_row_dict(
    base_row: dict[str, Any],
    *,
    label: str,
    pairs: list[dict[str, str]] | None,
    magnitude_override: str | None = None,
) -> dict[str, Any]:
    row = dict(base_row)
    row["label"] = as_text(label)
    if isinstance(pairs, list):
        raw_pairs = [{"reference": as_text(p.get("reference")), "magnitude": as_text(p.get("magnitude"))} for p in pairs if isinstance(p, dict)]
        row["pairs"] = raw_pairs
        if raw_pairs:
            row["reference"] = as_text(raw_pairs[0].get("reference"))
            row["magnitude"] = as_text(raw_pairs[0].get("magnitude"))
        datum_id = as_text(row.get("identifier") or row.get("row_id"))
        _, vg, _ = parse_datum_id(datum_id)
        if vg == 0:
            row["reference"] = ""
            row["magnitude"] = ""
    elif magnitude_override is not None:
        existing = row.get("pairs")
        np: list[dict[str, str]] = []
        if isinstance(existing, list):
            for item in existing:
                if isinstance(item, dict):
                    np.append(
                        {
                            "reference": as_text(item.get("reference")),
                            "magnitude": as_text(item.get("magnitude")),
                        }
                    )
        if np:
            np[0] = {"reference": np[0]["reference"], "magnitude": as_text(magnitude_override)}
        else:
            np = [
                {
                    "reference": as_text(row.get("reference")),
                    "magnitude": as_text(magnitude_override),
                }
            ]
        row["pairs"] = np
        row["reference"] = as_text(np[0].get("reference"))
        row["magnitude"] = as_text(np[0].get("magnitude"))
        datum_id = as_text(row.get("identifier") or row.get("row_id"))
        _, vg, _ = parse_datum_id(datum_id)
        if vg == 0:
            row["reference"] = ""
            row["magnitude"] = ""
    return row


def graph_write_violation_message(report) -> str | None:
    """Block only when the graph contains **invalid** rows (``report.ok`` is false).

    ``ambiguous`` / ``unknown`` rows do not block writes; they are surfaced via
    :func:`graph_evolving_state_warnings` and per-datum ``RulePolicy.guidance_notes``.
    """
    if not report.ok:
        return "datum rule graph contains invalid row(s)"
    return None


def graph_evolving_state_warnings(report) -> list[str]:
    """Non-blocking notices for ambiguous/unknown rows (rules still evolving)."""
    out: list[str] = []
    amb = sorted({as_text(u.datum_id) for u in report.understandings if as_text(u.status) == "ambiguous"})
    unk = sorted({as_text(u.datum_id) for u in report.understandings if as_text(u.status) == "unknown"})
    if amb:
        tail = "…" if len(amb) > 12 else ""
        out.append(
            "ambiguous datum rows (edits allowed; review classification): "
            + ", ".join(amb[:12])
            + tail
        )
    if unk:
        tail = "…" if len(unk) > 12 else ""
        out.append(
            "unknown-rule datum rows (edits allowed; neutral/manual path): " + ", ".join(unk[:12]) + tail
        )
    return out


def evaluate_probe_write(
    base_rows_payload: dict[str, Any],
    *,
    probe_row_id: str,
    probe_row_dict: dict[str, Any],
    rule_key_hint: str = "",
    rule_write_override: bool = False,
    pairs_for_hint: list[dict[str, Any]] | None = None,
    value_group_hint: int | None = None,
) -> dict[str, Any]:
    """Run understanding on merged rows + derive policy for the probe row."""
    from . import understand_datums, validate_rule_create  # noqa: PLC0415

    merged = merge_row_into_rows_payload(base_rows_payload, probe_row_id, probe_row_dict)
    report = understand_datums(merged)
    u = report.by_id.get(as_text(probe_row_id))
    policy = derive_rule_policy(u)
    warnings: list[str] = []
    errors: list[str] = []

    graph_err = graph_write_violation_message(report)
    warnings.extend(graph_evolving_state_warnings(report))
    if graph_err and rule_write_override:
        warnings.append(f"rule_write_override: {graph_err}")
    elif graph_err:
        errors.append(graph_err)

    hint_ok: bool | None = None
    rk = as_text(rule_key_hint)
    if rk:
        plist = pairs_for_hint if isinstance(pairs_for_hint, list) else None
        if plist and all(isinstance(x, dict) for x in plist):
            hint = validate_rule_create(
                base_rows_payload,
                rule_key=rk,
                reference="",
                magnitude="",
                value_group=value_group_hint,
                label=as_text(probe_row_dict.get("label")),
                pairs=[dict(x) for x in plist],
            )
        else:
            hint = validate_rule_create(
                base_rows_payload,
                rule_key=rk,
                reference=as_text(probe_row_dict.get("reference")),
                magnitude=as_text(probe_row_dict.get("magnitude")),
                value_group=value_group_hint,
                label=as_text(probe_row_dict.get("label")),
                pairs=None,
            )
        hint_ok = bool(hint.get("ok"))
        if not hint_ok and not rule_write_override:
            errors.extend([str(x) for x in list(hint.get("errors") or [])])
        elif not hint_ok and rule_write_override:
            warnings.append("rule_write_override: rule_key hint validation failed")
        warnings.extend([str(x) for x in list(hint.get("warnings") or [])])

    policy_ok, gate_notes = gate_write_attempt(
        policy,
        rule_write_override=rule_write_override,
        hint_validation_ok=hint_ok if rk else None,
    )
    warnings.extend(gate_notes)

    permitted = policy_ok and not errors

    return {
        "ok": permitted,
        "permitted": permitted,
        "probe_row_id": as_text(probe_row_id),
        "datum_understanding": u.to_dict() if u else None,
        "rule_policy": policy.to_dict(),
        "merged_understanding": report.to_dict(),
        "warnings": warnings,
        "errors": errors,
        "schema": "mycite.portal.datum_rules.write_evaluation.v1",
    }


def evaluate_resource_payload_write(
    merged_rows_payload: dict[str, Any],
    *,
    rule_write_override: bool = False,
) -> dict[str, Any]:
    """Validate a full sandbox/local resource row payload before persisting."""
    from . import understand_datums  # noqa: PLC0415

    report = understand_datums(merged_rows_payload)
    policies = {datum_id: derive_rule_policy(u).to_dict() for datum_id, u in report.by_id.items()}
    graph_err = graph_write_violation_message(report)
    errors: list[str] = []
    warnings: list[str] = []
    warnings.extend(graph_evolving_state_warnings(report))
    if graph_err and not rule_write_override:
        errors.append(graph_err)
    elif graph_err and rule_write_override:
        warnings.append(f"rule_write_override: {graph_err}")

    ok = not errors
    return {
        "ok": ok,
        "permitted": ok,
        "merged_understanding": report.to_dict(),
        "rule_policy_by_id": policies,
        "warnings": warnings,
        "errors": errors,
        "schema": "mycite.portal.datum_rules.resource_write_evaluation.v1",
    }


def infer_reference_filter_rule_key(
    *,
    value_group: int | None,
    magnitude_hint: str = "",
    parent_datum_id: str = "",
    report,
) -> str | None:
    """Best-effort ``rule_key`` for filtered reference lists when client omits ``rule_key``."""
    vg = value_group
    if vg is None:
        return None
    mag = as_text(magnitude_hint)
    parent = as_text(parent_datum_id)
    parent_u = report.by_id.get(parent) if parent else None
    pf = as_text(parent_u.family) if parent_u is not None else ""

    if vg == 0:
        return "collection.namespace_order.v1"
    if vg == 1 and mag == "1":
        if pf == "collection":
            return "selectorate.collection_transform.v1"
        if pf == "bacillete":
            return "baciloid.sequence_space.v1"
        return None
    if vg == 1 and mag == "0" and pf == "selectorate":
        return "field.selector_field.v1"
    if vg is not None and vg > 1:
        return "table_like.ordinal_tuple.v1"
    return None


def extract_rows_payload_from_resource_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """If ``body`` looks like a sandbox resource with anthology rows, return rows payload."""
    acp = body.get("anthology_compatible_payload")
    if isinstance(acp, dict) and acp:
        if isinstance(acp.get("rows"), dict):
            return {"rows": dict(acp["rows"])}
        if all(isinstance(v, list) for v in acp.values()):
            return acp
    cs = body.get("canonical_state") if isinstance(body.get("canonical_state"), dict) else {}
    compact = cs.get("compact_payload") if isinstance(cs.get("compact_payload"), dict) else {}
    if isinstance(compact, dict) and compact:
        if isinstance(compact.get("rows"), dict):
            return {"rows": dict(compact["rows"])}
        if all(isinstance(v, list) for v in compact.values()):
            return compact
    return None


__all__ = [
    "merge_row_into_rows_payload",
    "compute_next_append_datum_id",
    "build_append_row_dict",
    "build_updated_row_dict",
    "graph_write_violation_message",
    "graph_evolving_state_warnings",
    "evaluate_probe_write",
    "evaluate_resource_payload_write",
    "infer_reference_filter_rule_key",
    "extract_rows_payload_from_resource_body",
]
