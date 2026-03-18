from __future__ import annotations

from .base import (
    RuleContext,
    RuleDefinition,
    as_text,
    compute_bit_width,
    make_ui_state,
    parse_binary_int,
    parse_positive_int,
)


def build_bacillete_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        return as_text(context.row.reference) == "0-0-6" and int(context.row.value_group or -1) == 1

    def _derive(context: RuleContext) -> dict[str, object]:
        cardinality = parse_positive_int(context.row.magnitude)
        return {
            "namespace_cardinality": cardinality,
            "namespace_kind": "bacillete",
            "root_ref": "0-0-6",
        }

    def _validate(_context: RuleContext, constraints: dict[str, object]) -> tuple[bool, list[str], list[str]]:
        errors: list[str] = []
        if int(constraints.get("namespace_cardinality") or 0) <= 0:
            errors.append("bacillete magnitude must be a positive integer cardinality")
        return (not errors), [], errors

    def _ui(_context: RuleContext, _constraints: dict[str, object]) -> dict[str, object]:
        hints = make_ui_state("standard", family="bacillete", transitional=False)
        hints["lens_group"] = "namespace"
        return hints

    return RuleDefinition(
        key="bacillete.namespace.v1",
        family="bacillete",
        lens_key="lens.namespace.cardinality.v1",
        allowed_parent_families=(),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def build_baciloid_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        parent = context.parent_understanding
        return parent is not None and as_text(parent.family) == "bacillete" and int(context.row.value_group or -1) == 1

    def _derive(context: RuleContext) -> dict[str, object]:
        parent = context.parent_understanding
        return {
            "sequence_length": parse_positive_int(context.row.magnitude),
            "parent_family": as_text(parent.family if parent else ""),
            "namespace_cardinality": int(((parent.constraints if parent else {}) or {}).get("namespace_cardinality") or 0),
        }

    def _validate(context: RuleContext, constraints: dict[str, object]) -> tuple[bool, list[str], list[str]]:
        errors: list[str] = []
        parent = context.parent_understanding
        if parent is None or as_text(parent.family) != "bacillete" or as_text(parent.status) != "standard":
            errors.append("baciloid parent must resolve to a standard bacillete")
        if int(constraints.get("sequence_length") or 0) <= 0:
            errors.append("baciloid magnitude must be a positive integer sequence length")
        return (not errors), [], errors

    def _ui(_context: RuleContext, _constraints: dict[str, object]) -> dict[str, object]:
        hints = make_ui_state("standard", family="baciloid", transitional=False)
        hints["lens_group"] = "space"
        return hints

    return RuleDefinition(
        key="baciloid.sequence_space.v1",
        family="baciloid",
        lens_key="lens.space.sequence.v1",
        allowed_parent_families=("bacillete",),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def build_babellette_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        parent = context.parent_understanding
        return parent is not None and as_text(parent.family) == "baciloid" and int(context.row.value_group or -1) == 1

    def _derive(context: RuleContext) -> dict[str, object]:
        parent = context.parent_understanding
        parent_constraints = parent.constraints if parent else {}
        return {
            "expected_magnitude": "0",
            "parent_family": as_text(parent.family if parent else ""),
            "namespace_cardinality": int(parent_constraints.get("namespace_cardinality") or 0),
            "sequence_length": int(parent_constraints.get("sequence_length") or 0),
        }

    def _validate(context: RuleContext, _constraints: dict[str, object]) -> tuple[bool, list[str], list[str]]:
        errors: list[str] = []
        parent = context.parent_understanding
        if parent is None or as_text(parent.family) != "baciloid" or as_text(parent.status) != "standard":
            errors.append("babellette parent must resolve to a standard baciloid")
        if as_text(context.row.magnitude) != "0":
            errors.append("babellette magnitude must be exactly 0")
        return (not errors), [], errors

    def _ui(_context: RuleContext, _constraints: dict[str, object]) -> dict[str, object]:
        hints = make_ui_state("transitional", family="babellette", transitional=True)
        hints["lens_group"] = "transition"
        return hints

    return RuleDefinition(
        key="babellette.transition.v1",
        family="babellette",
        lens_key="lens.transition.babellette.v1",
        allowed_parent_families=("baciloid",),
        transitional=True,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def build_isolate_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        parent = context.parent_understanding
        return parent is not None and as_text(parent.family) == "babellette"

    def _derive(context: RuleContext) -> dict[str, object]:
        parent = context.parent_understanding
        parent_constraints = parent.constraints if parent else {}
        namespace_cardinality = int(parent_constraints.get("namespace_cardinality") or 0)
        sequence_length = int(parent_constraints.get("sequence_length") or 0)
        domain_size = (namespace_cardinality**sequence_length) if namespace_cardinality > 0 and sequence_length > 0 else 0
        max_value = domain_size - 1 if domain_size > 0 else -1
        parsed = parse_binary_int(context.row.magnitude)
        value_bits = as_text(context.row.magnitude)
        return {
            "namespace_cardinality": namespace_cardinality,
            "sequence_length": sequence_length,
            "domain_size": domain_size,
            "max_value": max_value,
            "bit_width": compute_bit_width(max_value if max_value >= 0 else 0),
            "parsed_binary_value": parsed,
            "is_binary_magnitude": bool(value_bits and all(ch in {"0", "1"} for ch in value_bits)),
            "lens_variant": "ascii_like" if namespace_cardinality == 256 else "numeric_binary",
        }

    def _validate(context: RuleContext, constraints: dict[str, object]) -> tuple[bool, list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        parent = context.parent_understanding
        if parent is None or as_text(parent.family) != "babellette" or as_text(parent.status) not in {"standard", "transitional"}:
            errors.append("isolate parent must resolve to a standard/transitional babellette")
        if not bool(constraints.get("is_binary_magnitude")):
            errors.append("isolate magnitude must be canonical binary")
        value = constraints.get("parsed_binary_value")
        if not isinstance(value, int):
            errors.append("isolate binary magnitude could not be parsed")
        max_value = int(constraints.get("max_value") or -1)
        if isinstance(value, int) and max_value >= 0 and not (0 <= value <= max_value):
            errors.append(f"isolate value out of domain; expected 0 <= value <= {max_value}")
        if int(constraints.get("domain_size") or 0) <= 0:
            errors.append("parent chain domain is invalid (namespace_cardinality and sequence_length are required)")
        if int(constraints.get("namespace_cardinality") or 0) == 256:
            warnings.append("ascii-like namespace detected; text lens is available")
        return (not errors), warnings, errors

    def _ui(_context: RuleContext, constraints: dict[str, object]) -> dict[str, object]:
        hints = make_ui_state("standard", family="isolate", transitional=False)
        hints["lens_group"] = "value"
        hints["text_like"] = bool(int(constraints.get("namespace_cardinality") or 0) == 256)
        return hints

    return RuleDefinition(
        key="isolate.binary_value.v1",
        family="isolate",
        lens_key="lens.text.ascii_like.v1",
        allowed_parent_families=("babellette",),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )


def default_bacillete_family_rules() -> list[RuleDefinition]:
    return [
        build_bacillete_rule(),
        build_baciloid_rule(),
        build_babellette_rule(),
        build_isolate_rule(),
    ]
