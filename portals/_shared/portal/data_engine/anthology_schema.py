from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .anthology_normalization import datum_sort_key, parse_datum_identifier
from ..data_contract.anthology_pairs import compact_row_to_record, record_to_compact_row


@dataclass(frozen=True)
class NormalizedPair:
    ref: str
    magnitude: str

    def to_dict(self) -> dict[str, str]:
        return {"ref": self.ref, "magnitude": self.magnitude}


@dataclass(frozen=True)
class NormalizedDatum:
    datum_id: str
    layer: int
    value_group: int
    iteration: int
    title: str
    icon_ref: str | None
    row_kind: str
    definition: dict[str, Any] | None
    tuple_pairs: list[dict[str, str]] | None
    source_scope: str
    row_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "datum_id": self.datum_id,
            "layer": self.layer,
            "value_group": self.value_group,
            "iteration": self.iteration,
            "title": self.title,
            "icon_ref": self.icon_ref,
            "row_kind": self.row_kind,
            "definition": dict(self.definition or {}),
            "tuple_pairs": [dict(item) for item in list(self.tuple_pairs or [])],
            "source_scope": self.source_scope,
            "row_payload": dict(self.row_payload or {}),
        }


def parse_id(datum_id: str) -> tuple[int | None, int | None, int | None]:
    return parse_datum_identifier(datum_id)


def sort_key(datum_id: str, fallback: str = "") -> tuple[int, int, int, str]:
    return datum_sort_key(datum_id, fallback)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _normalize_pairs(row: dict[str, Any]) -> list[NormalizedPair]:
    raw = row.get("pairs") if isinstance(row.get("pairs"), list) else []
    out: list[NormalizedPair] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ref = _as_text(item.get("reference"))
        magnitude = _as_text(item.get("magnitude"))
        if not ref and not magnitude:
            continue
        out.append(NormalizedPair(ref=ref, magnitude=magnitude))
    if out:
        return out
    ref = _as_text(row.get("reference"))
    magnitude = _as_text(row.get("magnitude"))
    if ref or magnitude:
        return [NormalizedPair(ref=ref, magnitude=magnitude)]
    return []


def detect_row_kind(*, value_group: int, pair_count: int, pairs: list[NormalizedPair]) -> str:
    if value_group == 0:
        return "selection"
    if pair_count > 1 and pair_count == value_group:
        return "tuple"
    if pair_count == 1:
        magnitude = _as_text(pairs[0].magnitude if pairs else "")
        if magnitude.startswith("[") and magnitude.endswith("]"):
            return "collection"
    return "definition"


def validate_row(datum: NormalizedDatum, *, strict: bool = False) -> list[str]:
    errors: list[str] = []
    layer, value_group, iteration = parse_datum_identifier(datum.datum_id)
    if layer is None or value_group is None or iteration is None:
        errors.append(f"invalid datum id format: {datum.datum_id}")
        return errors
    if layer != datum.layer or value_group != datum.value_group or iteration != datum.iteration:
        errors.append(
            "datum id / tuple mismatch "
            f"(id={datum.datum_id}, layer={datum.layer}, value_group={datum.value_group}, iteration={datum.iteration})"
        )

    payload = dict(datum.row_payload or {})
    pairs = payload.get("pairs") if isinstance(payload.get("pairs"), list) else []
    if strict and datum.row_kind == "tuple" and len(pairs) != datum.value_group:
        errors.append(
            f"tuple row requires pair_count==value_group (datum={datum.datum_id}, pairs={len(pairs)}, vg={datum.value_group})"
        )
    if strict and datum.row_kind in {"definition", "tuple"} and len(pairs) < 1:
        errors.append(f"row requires at least one pair for kind={datum.row_kind}: {datum.datum_id}")
    return errors


def normalize_row(
    row: dict[str, Any],
    *,
    source_scope: str,
    strict: bool = False,
) -> tuple[NormalizedDatum | None, list[str]]:
    datum_id = _as_text(row.get("identifier") or row.get("row_id"))
    layer, value_group, iteration = parse_datum_identifier(datum_id)
    if layer is None or value_group is None or iteration is None:
        return None, [f"invalid datum identifier: {datum_id or '<missing>'}"]

    pairs = _normalize_pairs(row)
    row_kind = detect_row_kind(value_group=value_group, pair_count=len(pairs), pairs=pairs)
    tuple_pairs = [{"field": pair.ref, "value": pair.magnitude} for pair in pairs] if row_kind == "tuple" else None
    definition = (
        {"ref_pairs": [pair.to_dict() for pair in pairs]}
        if row_kind in {"definition", "selection", "collection"}
        else None
    )
    row_payload = {
        "pairs": [{"reference": pair.ref, "magnitude": pair.magnitude} for pair in pairs],
        "reference": pairs[0].ref if pairs else "",
        "magnitude": pairs[0].magnitude if pairs else "",
    }
    datum = NormalizedDatum(
        datum_id=datum_id,
        layer=layer,
        value_group=value_group,
        iteration=iteration,
        title=_as_text(row.get("label")),
        icon_ref=_as_text(row.get("icon_ref")) or None,
        row_kind=row_kind,
        definition=definition,
        tuple_pairs=tuple_pairs,
        source_scope=_as_text(source_scope) or "portal",
        row_payload=row_payload,
    )
    return datum, validate_row(datum, strict=strict)


def normalize_compact_row(
    row_key: str,
    raw_value: object,
    *,
    source_scope: str,
    strict: bool = False,
) -> tuple[NormalizedDatum | None, list[str]]:
    record, warnings, valid = compact_row_to_record(row_key, raw_value)
    datum, errors = normalize_row(record, source_scope=source_scope, strict=strict)
    out = list(warnings or []) + list(errors or [])
    if not valid:
        out.append(f"invalid compact pair payload: {row_key}")
    return datum, out


def denormalize_row(datum: NormalizedDatum) -> dict[str, Any]:
    pairs = datum.row_payload.get("pairs") if isinstance(datum.row_payload.get("pairs"), list) else []
    first = pairs[0] if pairs else {"reference": "", "magnitude": ""}
    return {
        "row_id": datum.datum_id,
        "identifier": datum.datum_id,
        "label": datum.title,
        "pairs": [dict(item) for item in pairs if isinstance(item, dict)],
        "reference": _as_text(first.get("reference")),
        "magnitude": _as_text(first.get("magnitude")),
    }


def denormalize_compact_row(datum: NormalizedDatum, fallback_index: int = 1) -> tuple[str, list[Any]]:
    row = denormalize_row(datum)
    return record_to_compact_row(row, fallback_index)
