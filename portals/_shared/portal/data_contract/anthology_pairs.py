from __future__ import annotations

from typing import Any


def _as_text(value: object) -> str:
    return "" if value is None else str(value)


def normalize_pair_items(raw_pairs: object) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw_pairs, list):
        return out

    for item in raw_pairs:
        if not isinstance(item, dict):
            continue
        reference = _as_text(item.get("reference")).strip()
        magnitude = _as_text(item.get("magnitude")).strip()
        if not reference and not magnitude:
            continue
        out.append({"reference": reference, "magnitude": magnitude})
    return out


def pairs_from_row(row: dict[str, Any]) -> list[dict[str, str]]:
    raw_pairs = normalize_pair_items(row.get("pairs"))
    if raw_pairs:
        return raw_pairs

    reference = _as_text(row.get("reference")).strip()
    magnitude = _as_text(row.get("magnitude")).strip()
    if not reference and not magnitude:
        return []
    return [{"reference": reference, "magnitude": magnitude}]


def compact_row_to_record(row_key: str, raw_value: object) -> tuple[dict[str, Any], list[str], bool]:
    warnings: list[str] = []
    valid = True

    row_values = raw_value if isinstance(raw_value, list) else []
    base = row_values[0] if len(row_values) > 0 and isinstance(row_values[0], list) else []
    labels = row_values[1] if len(row_values) > 1 and isinstance(row_values[1], list) else []

    row_id = _as_text(row_key).strip() or _as_text(row_key)
    identifier = _as_text(base[0] if len(base) > 0 else row_key).strip() or row_id
    label = _as_text(labels[0] if len(labels) > 0 else "").strip()

    pair_tokens = [_as_text(item).strip() for item in base[1:]]
    if len(pair_tokens) % 2 != 0:
        valid = False
        dropped = pair_tokens[-1]
        pair_tokens = pair_tokens[:-1]
        warnings.append(
            f"row {row_id}: odd tail token in compact pair list; dropped trailing token '{dropped}'."
        )

    pairs: list[dict[str, str]] = []
    for index in range(0, len(pair_tokens), 2):
        reference = _as_text(pair_tokens[index]).strip()
        magnitude = _as_text(pair_tokens[index + 1]).strip()
        if not reference and not magnitude:
            continue
        pairs.append({"reference": reference, "magnitude": magnitude})

    first_pair = pairs[0] if pairs else {"reference": "", "magnitude": ""}
    return (
        {
            "row_id": row_id,
            "identifier": identifier,
            "label": label,
            "pairs": pairs,
            "pair_count": len(pairs),
            "reference": _as_text(first_pair.get("reference")).strip(),
            "magnitude": _as_text(first_pair.get("magnitude")).strip(),
        },
        warnings,
        valid,
    )


def record_to_compact_row(row: dict[str, Any], fallback_index: int) -> tuple[str, list[Any]]:
    key = _as_text(row.get("row_id") or row.get("identifier") or f"row-{fallback_index}").strip()
    if not key:
        key = f"row-{fallback_index}"

    identifier = _as_text(row.get("identifier") or key).strip() or key
    label = _as_text(row.get("label")).strip()
    pairs = pairs_from_row(row)

    base: list[str] = [identifier]
    for pair in pairs:
        base.append(_as_text(pair.get("reference")).strip())
        base.append(_as_text(pair.get("magnitude")).strip())

    return key, [base, [label]]

