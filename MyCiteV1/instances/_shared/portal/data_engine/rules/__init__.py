from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...data_contract import compact_payload_to_rows
from .bacillete_rules import default_bacillete_family_rules
from .base import (
    ORDINAL_SEMANTICS_V1,
    DatumRow,
    DatumUnderstanding,
    RuleContext,
    RuleDefinition,
    as_text,
    datum_sort_key,
    parse_datum_id,
    value_group_as_int,
)
from .collection_rules import default_collection_family_rules, ordered_pairs_from_row
from .lenses import resolve_lens_payload
from .policy import RulePolicy, derive_rule_policy, gate_write_attempt
from .samras_rules import build_samras_rule
from .write_evaluation import (
    build_append_row_dict,
    build_updated_row_dict,
    compute_next_append_datum_id,
    evaluate_probe_write,
    evaluate_resource_payload_write,
    extract_rows_payload_from_resource_body,
    infer_reference_filter_rule_key,
    merge_row_into_rows_payload,
)


def _datum_id_pattern():
    from .base import _DATUM_ID_RE

    return _DATUM_ID_RE


def _extract_rows(payload: dict[str, Any]) -> list[DatumRow]:
    rows_obj = payload.get("rows") if isinstance(payload, dict) else []
    out: list[DatumRow] = []
    if isinstance(rows_obj, dict):
        is_compact = all(isinstance(value, list) for value in rows_obj.values()) if rows_obj else False
        if is_compact:
            raw_rows = compact_payload_to_rows(rows_obj, strict=False)
        else:
            raw_rows = [dict(value) for value in rows_obj.values() if isinstance(value, dict)]
    elif isinstance(rows_obj, list):
        raw_rows = [dict(item) for item in rows_obj if isinstance(item, dict)]
    elif isinstance(payload, dict) and all(isinstance(value, list) for value in payload.values()):
        raw_rows = compact_payload_to_rows(payload, strict=False)
    else:
        raw_rows = []
    for item in raw_rows:
        datum_id = as_text(item.get("identifier") or item.get("row_id"))
        layer, value_group, iteration = parse_datum_id(datum_id)
        item_dict = dict(item)
        pairs_list = item_dict.get("pairs") if isinstance(item_dict.get("pairs"), list) else []
        reference = as_text(item_dict.get("reference"))
        magnitude = as_text(item_dict.get("magnitude"))
        if not reference and pairs_list and isinstance(pairs_list[0], dict):
            reference = as_text(pairs_list[0].get("reference"))
        if not magnitude and pairs_list and isinstance(pairs_list[0], dict):
            magnitude = as_text(pairs_list[0].get("magnitude"))
        # VG=0 collections use multi-ref pairs; avoid wiring collection -> first isolate in branch graph.
        if value_group == 0:
            if pairs_list:
                reference = ""
                magnitude = ""
            elif reference and _datum_id_pattern().fullmatch(reference):
                item_dict = dict(item_dict)
                item_dict["pairs"] = [{"reference": reference, "magnitude": magnitude}]
                reference = ""
                magnitude = ""
        out.append(
            DatumRow(
                datum_id=datum_id,
                reference=reference,
                magnitude=magnitude,
                label=as_text(item_dict.get("label")),
                value_group=value_group,
                layer=layer,
                iteration=iteration,
                raw=item_dict,
            )
        )
    out.sort(key=lambda row: datum_sort_key(row.datum_id))
    return out


@dataclass(frozen=True)
class DatumUnderstandingReport:
    ok: bool
    understandings: list[DatumUnderstanding]
    by_id: dict[str, DatumUnderstanding]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "understandings": [item.to_dict() for item in self.understandings],
            "by_id": {key: value.to_dict() for key, value in self.by_id.items()},
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def _default_rules() -> list[RuleDefinition]:
    return (
        [build_samras_rule()]
        + default_collection_family_rules()
        + default_bacillete_family_rules()
    )


def _unknown_understanding(row: DatumRow, *, warnings: list[str] | None = None, errors: list[str] | None = None) -> DatumUnderstanding:
    return DatumUnderstanding(
        datum_id=row.datum_id,
        status="unknown",
        family="none",
        rule_key="none",
        root_ref=as_text(row.reference),
        parent_family="none",
        constraints={},
        lens_key="lens.none.v1",
        ui_hints={"row_state": "ambiguous", "row_shading": "neutral", "family": "none"},
        warnings=list(warnings or []),
        errors=list(errors or []),
    )


def _apply_branch_ambiguity(
    *,
    understandings_by_id: dict[str, DatumUnderstanding],
    rows_by_id: dict[str, DatumRow],
) -> dict[str, DatumUnderstanding]:
    children_by_id: dict[str, list[str]] = {}
    for row in rows_by_id.values():
        ref = as_text(row.reference)
        if ref in rows_by_id:
            children_by_id.setdefault(ref, []).append(row.datum_id)

    visited: set[str] = set()

    def _walk(node_id: str, contaminated: bool) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        current = understandings_by_id.get(node_id)
        if current is None:
            return
        current_contaminated = contaminated
        if current.status in {"ambiguous", "invalid"}:
            current_contaminated = True
        for child_id in children_by_id.get(node_id, []):
            child = understandings_by_id.get(child_id)
            if child is None:
                continue
            reclaim = child.status in {"standard", "transitional"}
            next_contaminated = current_contaminated
            if current.status in {"standard", "transitional"} and child.status == "unknown":
                child = DatumUnderstanding(
                    datum_id=child.datum_id,
                    status="ambiguous",
                    family=child.family,
                    rule_key=child.rule_key,
                    root_ref=child.root_ref,
                    parent_family=current.family,
                    constraints=dict(child.constraints),
                    lens_key=child.lens_key,
                    ui_hints={"row_state": "ambiguous", "row_shading": "neutral", "family": child.family},
                    warnings=list(child.warnings) + ["branch pattern break from recognized parent"],
                    errors=list(child.errors),
                )
                understandings_by_id[child_id] = child
                next_contaminated = True
            elif current_contaminated and not reclaim:
                child = DatumUnderstanding(
                    datum_id=child.datum_id,
                    status="ambiguous",
                    family=child.family,
                    rule_key=child.rule_key,
                    root_ref=child.root_ref,
                    parent_family=child.parent_family,
                    constraints=dict(child.constraints),
                    lens_key=child.lens_key,
                    ui_hints={"row_state": "ambiguous", "row_shading": "neutral", "family": child.family},
                    warnings=list(child.warnings) + ["descendant remains ambiguous after upstream branch break"],
                    errors=list(child.errors),
                )
                understandings_by_id[child_id] = child
                next_contaminated = True
            elif current_contaminated and reclaim:
                next_contaminated = False
            elif child.status in {"invalid", "ambiguous"}:
                next_contaminated = True
            _walk(child_id, next_contaminated)

    roots = [row.datum_id for row in rows_by_id.values() if as_text(row.reference) not in rows_by_id]
    for rid in sorted(roots, key=datum_sort_key):
        _walk(rid, False)
    return understandings_by_id


def _understanding_snapshot(understandings_by_id: dict[str, DatumUnderstanding]) -> dict[str, tuple[str, str, str]]:
    return {
        k: (v.rule_key, v.status, ",".join(v.errors))
        for k, v in sorted(understandings_by_id.items(), key=lambda item: datum_sort_key(item[0]))
    }


def understand_datums(
    payload: dict[str, Any],
    *,
    rules: list[RuleDefinition] | None = None,
) -> DatumUnderstandingReport:
    active_rules = list(rules or _default_rules())
    rows = _extract_rows(payload if isinstance(payload, dict) else {})
    rows_by_id = {row.datum_id: row for row in rows if row.datum_id}
    understandings_by_id: dict[str, DatumUnderstanding] = {}
    warnings: list[str] = []
    errors: list[str] = []
    branch_break_warnings: set[str] = set()

    max_passes = max(16, len(rows) * 4)
    for _pass in range(max_passes):
        snapshot_before = _understanding_snapshot(understandings_by_id)
        for row in rows:
            context = RuleContext(row=row, rows_by_id=rows_by_id, understandings_by_id=understandings_by_id)
            matched: list[RuleDefinition] = [rule for rule in active_rules if bool(rule.match(context))]
            if not matched:
                parent = context.parent_understanding
                understandings_by_id[row.datum_id] = _unknown_understanding(
                    row,
                    warnings=[f"no rule match for datum {row.datum_id}"],
                    errors=[],
                )
                if parent and parent.status in {"standard", "transitional"}:
                    branch_break_warnings.add(
                        f"branch break at {row.datum_id}: parent {parent.family} had no matching child rule"
                    )
                continue
            if len(matched) > 1:
                understandings_by_id[row.datum_id] = DatumUnderstanding(
                    datum_id=row.datum_id,
                    status="ambiguous",
                    family="none",
                    rule_key="conflict",
                    root_ref=row.reference,
                    parent_family=as_text(context.parent_understanding.family if context.parent_understanding else "none"),
                    constraints={},
                    lens_key="lens.none.v1",
                    ui_hints={"row_state": "ambiguous", "row_shading": "neutral", "family": "none"},
                    warnings=[f"multiple rules matched: {', '.join(rule.key for rule in matched)}"],
                    errors=[],
                )
                continue
            rule = matched[0]
            constraints = dict(rule.derive_constraints(context) or {})
            ok, rule_warnings, rule_errors = rule.validate(context, constraints)
            status = "invalid" if not ok else ("transitional" if rule.transitional else "standard")
            ui_hints = dict(rule.ui_hints(context, constraints) or {})
            ui_hints.setdefault("row_state", status if status != "unknown" else "ambiguous")
            understanding = DatumUnderstanding(
                datum_id=row.datum_id,
                status=status,
                family=rule.family,
                rule_key=rule.key,
                root_ref=row.reference,
                parent_family=as_text(context.parent_understanding.family if context.parent_understanding else "none"),
                constraints=constraints,
                lens_key=rule.lens_key,
                ui_hints=ui_hints,
                warnings=[str(item) for item in list(rule_warnings or [])],
                errors=[str(item) for item in list(rule_errors or [])],
            )
            understandings_by_id[row.datum_id] = understanding
        snapshot_after = _understanding_snapshot(understandings_by_id)
        if snapshot_before == snapshot_after:
            break

    warnings.extend(sorted(branch_break_warnings))
    understandings_by_id = _apply_branch_ambiguity(understandings_by_id=understandings_by_id, rows_by_id=rows_by_id)
    ordered = [understandings_by_id[row.datum_id] for row in rows if row.datum_id in understandings_by_id]
    for item in ordered:
        warnings.extend(list(item.warnings))
        errors.extend(list(item.errors))
    return DatumUnderstandingReport(
        ok=not any(item.status == "invalid" for item in ordered),
        understandings=ordered,
        by_id=dict(understandings_by_id),
        warnings=warnings,
        errors=errors,
    )


def reference_filter_options(
    payload: dict[str, Any],
    *,
    rule_key: str,
    rules: list[RuleDefinition] | None = None,
    filter_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_rules = list(rules or _default_rules())
    report = understand_datums(payload, rules=active_rules)
    selected_rule = next((item for item in active_rules if item.key == as_text(rule_key)), None)
    if selected_rule is None:
        return {
            "ok": False,
            "rule_key": as_text(rule_key),
            "allowed_parent_families": [],
            "references": [],
            "error": f"unknown rule_key: {rule_key}",
        }
    allowed_families = list(selected_rule.allowed_parent_families)
    references: list[dict[str, Any]] = []
    for datum_id, item in report.by_id.items():
        if item.family not in allowed_families:
            continue
        if item.status not in {"standard", "transitional"}:
            continue
        references.append(
            {
                "datum_id": datum_id,
                "family": item.family,
                "status": item.status,
                "ui_hints": dict(item.ui_hints),
            }
        )
    ctx = filter_context if isinstance(filter_context, dict) else {}
    if selected_rule.key == "collection.namespace_order.v1":
        anchor_refs = [as_text(x) for x in list(ctx.get("selected_refs") or []) if as_text(x)]
        anchor_refs = [x for x in anchor_refs if x]
        if anchor_refs:
            first = anchor_refs[0]
            b_anchor = _baciloid_anchor_from_report(report, first, payload)
            if b_anchor:
                filtered: list[dict[str, Any]] = []
                for row in references:
                    did = as_text(row.get("datum_id"))
                    b_id = _baciloid_anchor_from_report(report, did, payload)
                    if b_id == b_anchor:
                        filtered.append(row)
                references = filtered
    references.sort(key=lambda row: datum_sort_key(row.get("datum_id")))
    return {
        "ok": True,
        "rule_key": selected_rule.key,
        "family": selected_rule.family,
        "allowed_parent_families": allowed_families,
        "references": references,
        "filter_context": dict(ctx),
        "schema": "mycite.portal.datum_rules.reference_filter.v1",
    }


def _baciloid_anchor_from_report(report: DatumUnderstandingReport, isolate_id: str, payload: dict[str, Any]) -> str | None:
    from .collection_rules import _baciloid_datum_id_for_isolate

    iso = report.by_id.get(as_text(isolate_id))
    if iso is None or as_text(iso.family) != "isolate":
        return None
    rows_by_id = {r.datum_id: r for r in _extract_rows(payload if isinstance(payload, dict) else {}) if r.datum_id}
    return _baciloid_datum_id_for_isolate(isolate_id, rows_by_id)


def validate_rule_create(
    payload: dict[str, Any],
    *,
    rule_key: str,
    reference: str,
    magnitude: str,
    value_group: int | None = None,
    label: str = "",
    pairs: list[dict[str, Any]] | None = None,
    rules: list[RuleDefinition] | None = None,
) -> dict[str, Any]:
    active_rules = list(rules or _default_rules())
    selected_rule = next((item for item in active_rules if item.key == as_text(rule_key)), None)
    if selected_rule is None:
        return {"ok": False, "error": f"unknown rule_key: {rule_key}"}
    report = understand_datums(payload, rules=active_rules)
    probe_id = "999-999-999"
    raw_probe: dict[str, Any] = {}
    if isinstance(pairs, list) and pairs:
        raw_probe["pairs"] = [dict(item) if isinstance(item, dict) else {} for item in pairs]
    elif isinstance(pairs, list) and not pairs and as_text(rule_key) == "collection.namespace_order.v1":
        raw_probe["pairs"] = []
    if not raw_probe.get("pairs"):
        raw_probe.setdefault("reference", as_text(reference))
        raw_probe.setdefault("magnitude", as_text(magnitude))
    probe_row = DatumRow(
        datum_id=probe_id,
        reference=as_text(reference),
        magnitude=as_text(magnitude),
        label=as_text(label),
        value_group=value_group,
        layer=999,
        iteration=999,
        raw=raw_probe,
    )
    if raw_probe.get("pairs") and value_group_as_int(probe_row) == 0:
        probe_row = DatumRow(
            datum_id=probe_id,
            reference="",
            magnitude="",
            label=probe_row.label,
            value_group=probe_row.value_group,
            layer=probe_row.layer,
            iteration=probe_row.iteration,
            raw=dict(raw_probe),
        )
    elif raw_probe.get("pairs") and (value_group_as_int(probe_row) or 0) > 1:
        probe_row = DatumRow(
            datum_id=probe_id,
            reference="",
            magnitude="",
            label=probe_row.label,
            value_group=probe_row.value_group,
            layer=probe_row.layer,
            iteration=probe_row.iteration,
            raw=dict(raw_probe),
        )
    rows_by_id = {item.datum_id: DatumRow(item.datum_id, "", "", "", None, None, None, {}) for item in []}
    source_rows = _extract_rows(payload if isinstance(payload, dict) else {})
    rows_by_id = {item.datum_id: item for item in source_rows}
    rows_by_id[probe_id] = probe_row
    context = RuleContext(row=probe_row, rows_by_id=rows_by_id, understandings_by_id=dict(report.by_id))
    if not selected_rule.match(context):
        return {
            "ok": False,
            "rule_key": selected_rule.key,
            "status": "invalid",
            "errors": ["probe row does not match selected rule pattern"],
            "warnings": [],
        }
    constraints = dict(selected_rule.derive_constraints(context) or {})
    ok, warnings, errors = selected_rule.validate(context, constraints)
    return {
        "ok": bool(ok),
        "rule_key": selected_rule.key,
        "family": selected_rule.family,
        "status": "standard" if ok else ("transitional" if selected_rule.transitional else "invalid"),
        "constraints": constraints,
        "warnings": warnings,
        "errors": errors,
    }


def resolve_lens_for_datum(
    payload: dict[str, Any],
    *,
    datum_id: str,
    rules: list[RuleDefinition] | None = None,
) -> dict[str, Any]:
    report = understand_datums(payload, rules=rules)
    understanding = report.by_id.get(as_text(datum_id))
    if understanding is None:
        return {"ok": False, "error": f"datum not found: {datum_id}"}
    row = next((item for item in _extract_rows(payload) if item.datum_id == as_text(datum_id)), None)
    if row is None:
        return {"ok": False, "error": f"row not found for datum: {datum_id}"}
    lens_payload = resolve_lens_payload(
        lens_key=understanding.lens_key,
        understanding=understanding.to_dict(),
        row=row.raw,
    )
    policy = derive_rule_policy(understanding)
    return {
        "ok": True,
        "datum_id": as_text(datum_id),
        "understanding": understanding.to_dict(),
        "rule_policy": policy.to_dict(),
        "lens": lens_payload,
        "schema": "mycite.portal.datum_rules.lens_resolution.v1",
    }


__all__ = [
    "ORDINAL_SEMANTICS_V1",
    "value_group_as_int",
    "DatumUnderstanding",
    "DatumUnderstandingReport",
    "RulePolicy",
    "RuleDefinition",
    "RuleContext",
    "DatumRow",
    "ordered_pairs_from_row",
    "understand_datums",
    "derive_rule_policy",
    "gate_write_attempt",
    "reference_filter_options",
    "validate_rule_create",
    "resolve_lens_for_datum",
    "merge_row_into_rows_payload",
    "compute_next_append_datum_id",
    "build_append_row_dict",
    "build_updated_row_dict",
    "evaluate_probe_write",
    "evaluate_resource_payload_write",
    "infer_reference_filter_rule_key",
    "extract_rows_payload_from_resource_body",
]
