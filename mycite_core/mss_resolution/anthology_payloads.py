from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SAVE_STATE_SCHEMA = "mycite.anthology.save_state.v1"
SAVE_STATE_ENCODING = "layered-pairs"

_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def _as_text(value: object) -> str:
    return "" if value is None else str(value)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_base_registry_path() -> Path:
    legacy = repo_root() / "anthology-base.json"
    if legacy.exists():
        return legacy
    return repo_root() / "instances" / "convention" / "data" / "system" / "anthology.json"


def parse_datum_identifier(identifier: object) -> tuple[int | None, int | None, int | None]:
    token = _as_text(identifier).strip()
    if not _DATUM_ID_RE.fullmatch(token):
        return (None, None, None)
    try:
        layer_s, value_group_s, iteration_s = token.split("-", 2)
        return (int(layer_s), int(value_group_s), int(iteration_s))
    except Exception:
        return (None, None, None)


def datum_sort_key(identifier: object, fallback: object = "") -> tuple[int, int, int, str]:
    token = _as_text(identifier).strip()
    layer, value_group, iteration = parse_datum_identifier(token)
    if isinstance(layer, int) and isinstance(value_group, int) and isinstance(iteration, int):
        return (layer, value_group, iteration, token)
    return (10**9, 10**9, 10**9, _as_text(fallback).strip() or token)


def pairs_from_row(row: dict[str, Any]) -> list[dict[str, str]]:
    raw_pairs = row.get("pairs")
    out: list[dict[str, str]] = []
    if isinstance(raw_pairs, list):
        for item in raw_pairs:
            if not isinstance(item, dict):
                continue
            reference = _as_text(item.get("reference")).strip()
            magnitude = _as_text(item.get("magnitude")).strip()
            if not reference and not magnitude:
                continue
            out.append({"reference": reference, "magnitude": magnitude})
    if out:
        return out
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
    metadata = row_values[2] if len(row_values) > 2 and isinstance(row_values[2], dict) else {}

    row_id = _as_text(row_key).strip() or _as_text(row_key)
    identifier = _as_text(base[0] if len(base) > 0 else row_key).strip() or row_id
    label = _as_text(labels[0] if len(labels) > 0 else "").strip()
    icon_relpath = _as_text(metadata.get("icon_relpath")).strip()

    pair_tokens = [_as_text(item).strip() for item in base[1:]]
    if len(pair_tokens) % 2 != 0:
        valid = False
        dropped = pair_tokens[-1]
        pair_tokens = pair_tokens[:-1]
        warnings.append(f"row {row_id}: odd tail token in compact pair list; dropped trailing token '{dropped}'.")

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
            "icon_relpath": icon_relpath,
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
    icon_relpath = _as_text(row.get("icon_relpath")).strip()
    pairs = pairs_from_row(row)

    base: list[str] = [identifier]
    for pair in pairs:
        base.append(_as_text(pair.get("reference")).strip())
        base.append(_as_text(pair.get("magnitude")).strip())

    compact: list[Any] = [base, [label]]
    if icon_relpath:
        compact.append({"icon_relpath": icon_relpath})
    return key, compact


def compact_payload_to_rows(payload: dict[str, Any], *, strict: bool = True) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("anthology payload must be a JSON object")

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    valid = True

    for key, value in payload.items():
        record, row_warnings, row_valid = compact_row_to_record(_as_text(key), value)
        rows.append(record)
        warnings.extend(list(row_warnings or []))
        valid = valid and bool(row_valid)

    rows.sort(key=lambda row: datum_sort_key(row.get("identifier") or row.get("row_id"), row.get("row_id")))
    if strict and (not valid or warnings):
        message = "; ".join(warnings) if warnings else "anthology payload could not be normalized"
        raise ValueError(message)
    return rows


def rows_to_compact_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    sorted_rows = sorted(
        list(rows or []),
        key=lambda row: datum_sort_key(row.get("identifier") or row.get("row_id"), row.get("row_id")),
    )
    for index, row in enumerate(sorted_rows, start=1):
        key, value = record_to_compact_row(row, index)
        payload[key] = value
    return payload


def _pair_matrix_from_row(row: dict[str, Any]) -> list[list[str]]:
    out: list[list[str]] = []
    for pair in pairs_from_row(dict(row or {})):
        reference = _as_text(pair.get("reference")).strip()
        magnitude = _as_text(pair.get("magnitude")).strip()
        if not reference and not magnitude:
            continue
        out.append([reference, magnitude])
    return out


def _validate_pair_arity(identifier: str, value_group: int, pairs: list[list[str]]) -> None:
    pair_count = len(pairs)
    if value_group == 0:
        if pair_count <= 0:
            raise ValueError(f"{identifier}: VG0 rows must include at least one reference/magnitude pair")
        return
    if pair_count != value_group:
        raise ValueError(f"{identifier}: value_group {value_group} expects {value_group} pair(s), found {pair_count}")


def _require_identifier(row: dict[str, Any]) -> tuple[str, int, int, int]:
    identifier = _as_text(row.get("identifier") or row.get("row_id")).strip()
    layer, value_group, iteration = parse_datum_identifier(identifier)
    if not (isinstance(layer, int) and isinstance(value_group, int) and isinstance(iteration, int) and iteration > 0):
        raise ValueError(f"Invalid anthology datum identifier: {identifier or '<missing>'}")
    return identifier, layer, value_group, iteration


def rows_to_save_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[int, dict[int, list[dict[str, Any]]]] = {}
    row_count = 0
    pair_count = 0

    sorted_rows = sorted(
        list(rows or []),
        key=lambda row: datum_sort_key(row.get("identifier") or row.get("row_id"), row.get("row_id")),
    )
    for row in sorted_rows:
        identifier, layer, value_group, iteration = _require_identifier(row)
        pairs = _pair_matrix_from_row(row)
        _validate_pair_arity(identifier, value_group, pairs)
        grouped.setdefault(layer, {}).setdefault(value_group, []).append(
            {
                "identifier": identifier,
                "iteration": iteration,
                "label": _as_text(row.get("label")).strip(),
                "pairs": pairs,
            }
        )
        row_count += 1
        pair_count += len(pairs)

    layers_payload: list[dict[str, Any]] = []
    value_groups_per_layer: list[dict[str, int]] = []
    iterations_per_group: list[dict[str, int]] = []

    for layer in sorted(grouped):
        layer_groups = grouped[layer]
        value_groups_payload: list[dict[str, Any]] = []
        for value_group in sorted(layer_groups):
            rows_payload = list(layer_groups[value_group])
            rows_payload.sort(key=lambda item: int(item.get("iteration") or 0))
            iterations_per_group.append({"layer": layer, "value_group": value_group, "count": len(rows_payload)})
            value_groups_payload.append(
                {
                    "value_group": value_group,
                    "iteration_count": len(rows_payload),
                    "rows": rows_payload,
                }
            )
        value_groups_per_layer.append({"layer": layer, "count": len(value_groups_payload)})
        layers_payload.append(
            {
                "layer": layer,
                "value_group_count": len(value_groups_payload),
                "value_groups": value_groups_payload,
            }
        )

    return {
        "schema": SAVE_STATE_SCHEMA,
        "encoding": SAVE_STATE_ENCODING,
        "summary": {
            "layer_count": len(layers_payload),
            "row_count": row_count,
            "pair_count": pair_count,
            "value_groups_per_layer": value_groups_per_layer,
            "iterations_per_group": iterations_per_group,
        },
        "layers": layers_payload,
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_anthology_payload(path: str | Path) -> dict[str, Any]:
    from .datum_space import anchor_datum_path, load_datum_file, load_datum_space

    path_obj = Path(path)
    try:
        if anchor_datum_path(path_obj.parent).resolve() == path_obj.resolve():
            loaded = load_datum_space(path_obj.parent, sort_key=datum_sort_key)
            return dict(loaded.merged_payload)
    except Exception:
        pass
    return load_datum_file(path_obj)
