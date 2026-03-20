from __future__ import annotations

import hashlib
from typing import Any

from .base import (
    ORDINAL_SEMANTICS_V1,
    RuleContext,
    RuleDefinition,
    as_text,
    make_ui_state,
    parse_ordinal_magnitude,
    value_group_as_int,
)


def _datum_id_re():
    from .base import _DATUM_ID_RE

    return _DATUM_ID_RE


def ordered_pairs_from_row(row: Any) -> list[tuple[str, str]]:
    """Return (reference, magnitude) tuples in authoring/list order."""
    raw = row.raw if hasattr(row, "raw") else {}
    if not isinstance(raw, dict):
        return []
    pairs = raw.get("pairs")
    if isinstance(pairs, list) and pairs:
        out: list[tuple[str, str]] = []
        for item in pairs:
            if not isinstance(item, dict):
                continue
            out.append((as_text(item.get("reference")), as_text(item.get("magnitude"))))
        return out
    ref = as_text(row.reference) if hasattr(row, "reference") else ""
    mag = as_text(row.magnitude) if hasattr(row, "magnitude") else ""
    if ref:
        return [(ref, mag)]
    return []


def _parent_datum_id(row: Any, rows_by_id: dict[str, Any]) -> str | None:
    _re = _datum_id_re()
    ref = as_text(row.reference) if hasattr(row, "reference") else ""
    if (not ref or _re.fullmatch(ref) is None) and hasattr(row, "raw"):
        pairs = ordered_pairs_from_row(row)
        ref = pairs[0][0] if pairs else ""
    if not ref or _re.fullmatch(ref) is None:
        return None
    if ref not in rows_by_id:
        return None
    return ref


def _baciloid_datum_id_for_isolate(isolate_id: str, rows_by_id: dict[str, Any]) -> str | None:
    """isolate -> babellette -> baciloid (baciloid's parent row must be a bacillete referencing 0-0-6)."""
    row = rows_by_id.get(as_text(isolate_id))
    if row is None:
        return None
    babel_id = _parent_datum_id(row, rows_by_id)
    if not babel_id:
        return None
    babel = rows_by_id.get(babel_id)
    if babel is None:
        return None
    baciloid_id = _parent_datum_id(babel, rows_by_id)
    if not baciloid_id:
        return None
    baciloid = rows_by_id.get(baciloid_id)
    if baciloid is None:
        return None
    bacillete_row_id = _parent_datum_id(baciloid, rows_by_id)
    if not bacillete_row_id:
        return None
    bacillete = rows_by_id.get(bacillete_row_id)
    if bacillete is None:
        return None
    # 0-0-6 is a structural root and usually not materialized as a row.
    bacillete_ref = as_text(bacillete.reference)
    if not bacillete_ref:
        pairs = ordered_pairs_from_row(bacillete)
        bacillete_ref = pairs[0][0] if pairs else ""
    if bacillete_ref != "0-0-6":
        return None
    return baciloid_id


def _collection_signature(ordered_refs: list[str]) -> str:
    raw = "|".join(ordered_refs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_collection_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        if value_group_as_int(context.row) != 0:
            return False
        pairs = ordered_pairs_from_row(context.row)
        roots = {"0-0-5", "0-0-6", "0-0-1"}
        if not pairs:
            return True
        _re = _datum_id_re()
        for ref, _mag in pairs:
            if not ref or _re.fullmatch(ref) is None:
                return False
            if ref in roots:
                return False
        return True

    def _derive(context: RuleContext) -> dict[str, Any]:
        pairs = ordered_pairs_from_row(context.row)
        ordered_refs = [ref for ref, _ in pairs if ref]
        return {
            "ordered_member_refs": list(ordered_refs),
            "member_count": len(ordered_refs),
            "ordinal_semantics": dict(ORDINAL_SEMANTICS_V1),
        }

    def _validate(context: RuleContext, constraints: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []
        ordered_refs = list(constraints.get("ordered_member_refs") or [])
        if not ordered_refs:
            warnings.append(
                "empty collection is transitional: add at least one isolate reference for a standard collection"
            )
            return True, warnings, []
        if len(set(ordered_refs)) != len(ordered_refs):
            errors.append("collection duplicate isolate references are not allowed")
            return False, warnings, errors
        u = context.understandings_by_id
        baciloids: set[str] = set()
        for rid in ordered_refs:
            iso = u.get(rid)
            if iso is None or as_text(iso.family) != "isolate":
                errors.append(f"collection member {rid} is not a recognized standard isolate")
                continue
            if as_text(iso.status) != "standard":
                errors.append(f"collection member {rid} must be a standard isolate")
                continue
            b_id = _baciloid_datum_id_for_isolate(rid, context.rows_by_id)
            if not b_id:
                errors.append(f"could not resolve baciloid chain for isolate {rid}")
                continue
            baciloids.add(b_id)
        if len(baciloids) > 1:
            errors.append(
                "all collection members must share the same baciloid abstraction chain (mixed baciloid families rejected)"
            )
        if errors:
            return False, warnings, errors
        iso0 = u.get(ordered_refs[0])
        c_iso = (iso0.constraints if iso0 else {}) or {}
        n_card = int(c_iso.get("namespace_cardinality") or 0)
        seq_len = int(c_iso.get("sequence_length") or 0)
        b_id = next(iter(baciloids), "")
        constraints["collection_family_baciloid_id"] = b_id
        constraints["collection_namespace_cardinality"] = n_card
        constraints["collection_sequence_length"] = seq_len
        constraints["ordinal_domain_min"] = 1
        constraints["ordinal_domain_max"] = len(ordered_refs)
        constraints["collection_member_signature"] = _collection_signature(ordered_refs)
        warnings.append(
            "collection order defines ordinal indices for downstream field/table_like values; reordering changes semantics"
        )
        return True, warnings, []

    def _ui(context: RuleContext, constraints: dict[str, Any]) -> dict[str, Any]:
        empty = int(constraints.get("member_count") or 0) == 0
        st = "transitional" if empty else "standard"
        hints = make_ui_state(st, family="collection", transitional=empty)
        hints["lens_group"] = "ordered_namespace"
        hints["ordered_member_refs"] = list(constraints.get("ordered_member_refs") or [])
        return hints

    return RuleDefinition(
        key="collection.namespace_order.v1",
        family="collection",
        lens_key="lens.collection.ordered_members.v1",
        allowed_parent_families=("isolate",),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def build_selectorate_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        parent = context.parent_understanding
        return (
            parent is not None
            and as_text(parent.family) == "collection"
            and value_group_as_int(context.row) == 1
            and as_text(context.row.magnitude) == "1"
        )

    def _derive(context: RuleContext) -> dict[str, Any]:
        parent = context.parent_understanding
        pc = dict(parent.constraints if parent else {})
        return {
            "parent_collection_id": as_text(context.row.reference),
            "ordinal_semantics": dict(ORDINAL_SEMANTICS_V1),
            "ordered_member_refs": list(pc.get("ordered_member_refs") or []),
            "ordinal_domain_min": int(pc.get("ordinal_domain_min") or 1),
            "ordinal_domain_max": int(pc.get("ordinal_domain_max") or 0),
            "collection_member_signature": pc.get("collection_member_signature"),
            "collection_family_baciloid_id": pc.get("collection_family_baciloid_id"),
        }

    def _validate(context: RuleContext, constraints: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        errors: list[str] = []
        parent = context.parent_understanding
        if parent is None or as_text(parent.family) != "collection":
            errors.append("selectorate parent must be a collection")
        elif as_text(parent.status) not in {"standard", "transitional"}:
            errors.append("selectorate parent collection must be standard or transitional")
        elif as_text(parent.status) == "standard" and int(constraints.get("ordinal_domain_max") or 0) < 1:
            errors.append("selectorate requires a non-empty collection domain when parent collection is standard")
        return (not errors), [], errors

    def _ui(_context: RuleContext, _constraints: dict[str, Any]) -> dict[str, Any]:
        hints = make_ui_state("standard", family="selectorate", transitional=False)
        hints["lens_group"] = "selector_root"
        return hints

    return RuleDefinition(
        key="selectorate.collection_transform.v1",
        family="selectorate",
        lens_key="lens.selectorate.marker.v1",
        allowed_parent_families=("collection",),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def build_field_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        parent = context.parent_understanding
        return (
            parent is not None
            and as_text(parent.family) == "selectorate"
            and value_group_as_int(context.row) == 1
            and as_text(context.row.magnitude) == "0"
        )

    def _derive(context: RuleContext) -> dict[str, Any]:
        parent = context.parent_understanding
        pc = dict(parent.constraints if parent else {})
        return {
            "parent_selectorate_id": as_text(context.row.reference),
            "parent_collection_id": pc.get("parent_collection_id"),
            "ordinal_semantics": dict(ORDINAL_SEMANTICS_V1),
            "ordered_member_refs": list(pc.get("ordered_member_refs") or []),
            "ordinal_domain_min": int(pc.get("ordinal_domain_min") or 1),
            "ordinal_domain_max": int(pc.get("ordinal_domain_max") or 0),
            "collection_member_signature": pc.get("collection_member_signature"),
        }

    def _validate(context: RuleContext, constraints: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        errors: list[str] = []
        parent = context.parent_understanding
        if parent is None or as_text(parent.family) != "selectorate" or as_text(parent.status) != "standard":
            errors.append("field parent must be a standard selectorate")
        if int(constraints.get("ordinal_domain_max") or 0) < 1:
            errors.append("field requires a non-empty collection ordinal domain")
        return (not errors), [], errors

    def _ui(_context: RuleContext, _constraints: dict[str, Any]) -> dict[str, Any]:
        hints = make_ui_state("standard", family="field", transitional=False)
        hints["lens_group"] = "column_field"
        return hints

    return RuleDefinition(
        key="field.selector_field.v1",
        family="field",
        lens_key="lens.field.abstraction.v1",
        allowed_parent_families=("selectorate",),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def build_table_like_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        vg = value_group_as_int(context.row)
        if vg is None or vg <= 1:
            return False
        pairs = ordered_pairs_from_row(context.row)
        if not pairs:
            return False
        _re = _datum_id_re()
        return all(_re.fullmatch(as_text(ref)) for ref, _ in pairs if ref)

    def _derive(context: RuleContext) -> dict[str, Any]:
        pairs = ordered_pairs_from_row(context.row)
        field_refs = [as_text(ref) for ref, _mag in pairs if ref]
        return {
            "field_refs": field_refs,
            "field_count": len(field_refs),
            "per_field_pairs": [{"field_ref": as_text(ref), "magnitude": as_text(mag)} for ref, mag in pairs],
            "ordinal_semantics": dict(ORDINAL_SEMANTICS_V1),
        }

    def _validate(context: RuleContext, constraints: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
        warnings: list[str] = []
        errors: list[str] = []
        u = context.understandings_by_id
        pairs = ordered_pairs_from_row(context.row)
        signatures: set[str] = set()
        collection_ids: set[str] = set()
        max_ord = 0
        min_ord = 10**18
        for ref, mag in pairs:
            ref = as_text(ref)
            mag = as_text(mag)
            if not ref:
                continue
            fld = u.get(ref)
            if fld is None or as_text(fld.family) != "field":
                errors.append(f"table_like tuple reference {ref} is not a recognized field")
                continue
            if as_text(fld.status) != "standard":
                errors.append(f"field {ref} must be standard for table_like binding")
                continue
            fc = fld.constraints or {}
            sig = as_text(fc.get("collection_member_signature"))
            coll_id = as_text(fc.get("parent_collection_id"))
            if sig:
                signatures.add(sig)
            if coll_id:
                collection_ids.add(coll_id)
            omax = int(fc.get("ordinal_domain_max") or 0)
            omin = int(fc.get("ordinal_domain_min") or 1)
            max_ord = max(max_ord, omax)
            min_ord = min(min_ord, omin)
            ov = parse_ordinal_magnitude(mag)
            if ov is None:
                errors.append(f"magnitude for field {ref} must be a decimal integer ordinal")
                continue
            if omax < 1:
                errors.append(f"field {ref} has empty collection domain")
                continue
            if not (omin <= ov <= omax):
                errors.append(
                    f"ordinal {ov} out of range for field {ref}; "
                    f"allowed {omin}..{omax} (1-based indices into collection order; domain may have changed)"
                )
        if len(signatures) > 1:
            errors.append("table_like rows cannot mix fields from incompatible collections (member signature mismatch)")
        if len(collection_ids) > 1:
            errors.append("table_like rows cannot reference fields tied to different collection datums")
        if errors:
            return False, warnings, errors
        warnings.append(
            "table_like ordinals are 1-based positions into the field's collection; changing collection membership or order invalidates semantics"
        )
        constraints["resolved_collection_member_signature"] = next(iter(signatures), "")
        constraints["resolved_parent_collection_id"] = next(iter(collection_ids), "")
        constraints["effective_ordinal_domain_min"] = min_ord if min_ord < 10**17 else 1
        constraints["effective_ordinal_domain_max"] = max_ord
        return True, warnings, errors

    def _ui(_context: RuleContext, constraints: dict[str, Any]) -> dict[str, Any]:
        hints = make_ui_state("standard", family="table_like", transitional=False)
        hints["lens_group"] = "row_tuple"
        hints["field_count"] = int(constraints.get("field_count") or 0)
        return hints

    return RuleDefinition(
        key="table_like.ordinal_tuple.v1",
        family="table_like",
        lens_key="lens.table_like.row_tuple.v1",
        allowed_parent_families=("field",),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def default_collection_family_rules() -> list[RuleDefinition]:
    return [
        build_collection_rule(),
        build_selectorate_rule(),
        build_field_rule(),
        build_table_like_rule(),
    ]
