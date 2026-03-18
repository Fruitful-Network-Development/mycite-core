from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable


_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_positive_int(raw: object) -> int | None:
    token = as_text(raw)
    if not token:
        return None
    try:
        value = int(token)
    except Exception:
        return None
    if value <= 0:
        return None
    return value


def parse_binary_int(raw: object) -> int | None:
    token = as_text(raw)
    if not token:
        return None
    if any(ch not in {"0", "1"} for ch in token):
        return None
    try:
        return int(token, 2)
    except Exception:
        return None


def parse_datum_id(identifier: object) -> tuple[int | None, int | None, int | None]:
    token = as_text(identifier)
    if _DATUM_ID_RE.fullmatch(token) is None:
        return (None, None, None)
    try:
        layer_s, group_s, iter_s = token.split("-", 2)
        return int(layer_s), int(group_s), int(iter_s)
    except Exception:
        return (None, None, None)


def datum_sort_key(identifier: object) -> tuple[int, int, int, str]:
    token = as_text(identifier)
    layer, group, iteration = parse_datum_id(token)
    if isinstance(layer, int) and isinstance(group, int) and isinstance(iteration, int):
        return (layer, group, iteration, token)
    return (10**9, 10**9, 10**9, token)


@dataclass(frozen=True)
class DatumRow:
    datum_id: str
    reference: str
    magnitude: str
    label: str
    value_group: int | None
    layer: int | None
    iteration: int | None
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "datum_id": self.datum_id,
            "reference": self.reference,
            "magnitude": self.magnitude,
            "label": self.label,
            "value_group": self.value_group,
            "layer": self.layer,
            "iteration": self.iteration,
        }


@dataclass(frozen=True)
class DatumUnderstanding:
    datum_id: str
    status: str
    family: str
    rule_key: str
    root_ref: str
    parent_family: str
    constraints: dict[str, Any]
    lens_key: str
    ui_hints: dict[str, Any]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "datum_id": self.datum_id,
            "status": self.status,
            "family": self.family,
            "rule_key": self.rule_key,
            "root_ref": self.root_ref,
            "parent_family": self.parent_family,
            "constraints": dict(self.constraints),
            "lens_key": self.lens_key,
            "ui_hints": dict(self.ui_hints),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class RuleContext:
    row: DatumRow
    rows_by_id: dict[str, DatumRow]
    understandings_by_id: dict[str, DatumUnderstanding]

    @property
    def parent(self) -> DatumRow | None:
        ref = as_text(self.row.reference)
        if _DATUM_ID_RE.fullmatch(ref) is None:
            return None
        return self.rows_by_id.get(ref)

    @property
    def parent_understanding(self) -> DatumUnderstanding | None:
        parent = self.parent
        if parent is None:
            return None
        return self.understandings_by_id.get(parent.datum_id)


@dataclass(frozen=True)
class RuleDefinition:
    key: str
    family: str
    lens_key: str
    allowed_parent_families: tuple[str, ...]
    transitional: bool
    match: Callable[[RuleContext], bool]
    derive_constraints: Callable[[RuleContext], dict[str, Any]]
    validate: Callable[[RuleContext, dict[str, Any]], tuple[bool, list[str], list[str]]]
    ui_hints: Callable[[RuleContext, dict[str, Any]], dict[str, Any]]


def make_ui_state(status: str, *, family: str, transitional: bool) -> dict[str, Any]:
    shading = "neutral"
    if status == "standard":
        shading = "standard"
    elif status == "invalid":
        shading = "error"
    elif status == "transitional":
        shading = "light"
    return {
        "row_state": status,
        "row_shading": shading,
        "family": family,
        "transitional": bool(transitional),
    }


def compute_bit_width(max_value: int) -> int:
    token = int(max_value)
    if token <= 0:
        return 1
    return int(math.ceil(math.log2(token + 1)))
