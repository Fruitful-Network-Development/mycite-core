from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any


SAVE_STATE_SCHEMA = "mycite.anthology.save_state.v1"
SAVE_STATE_ENCODING = "layered-pairs"

_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def _load_pairs_contract():
    path = Path(__file__).resolve().with_name("anthology_pairs.py")
    spec = importlib.util.spec_from_file_location("mycite_shared_data_contract_anthology_pairs_save_state", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared anthology pair contract from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PAIRS = _load_pairs_contract()
pairs_from_row = _PAIRS.pairs_from_row
compact_row_to_record = _PAIRS.compact_row_to_record
record_to_compact_row = _PAIRS.record_to_compact_row


def _as_text(value: object) -> str:
    return "" if value is None else str(value)


def parse_datum_identifier(identifier: object) -> tuple[int | None, int | None, int | None]:
    token = _as_text(identifier).strip()
    if not _DATUM_ID_RE.fullmatch(token):
        return (None, None, None)
    try:
        layer_s, value_group_s, iteration_s = token.split("-", 2)
        return (int(layer_s), int(value_group_s), int(iteration_s))
    except Exception:
        return (None, None, None)


def _row_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    identifier = _as_text(row.get("identifier") or row.get("row_id")).strip()
    layer, value_group, iteration = parse_datum_identifier(identifier)
    if isinstance(layer, int) and isinstance(value_group, int) and isinstance(iteration, int):
        return (layer, value_group, iteration, identifier)
    return (10**9, 10**9, 10**9, identifier)


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(list(rows or []), key=_row_sort_key)


def _pair_matrix_from_row(row: dict[str, Any]) -> list[list[str]]:
    out: list[list[str]] = []
    for pair in pairs_from_row(dict(row or {})):
        reference = _as_text(pair.get("reference")).strip()
        magnitude = _as_text(pair.get("magnitude")).strip()
        if not reference and not magnitude:
            continue
        out.append([reference, magnitude])
    return out


def _pair_matrix_from_state_entry(entry: dict[str, Any]) -> list[list[str]]:
    raw_pairs = entry.get("pairs")
    out: list[list[str]] = []

    if isinstance(raw_pairs, list):
        for pair in raw_pairs:
            if isinstance(pair, dict):
                reference = _as_text(pair.get("reference")).strip()
                magnitude = _as_text(pair.get("magnitude")).strip()
            elif isinstance(pair, (list, tuple)):
                reference = _as_text(pair[0] if len(pair) > 0 else "").strip()
                magnitude = _as_text(pair[1] if len(pair) > 1 else "").strip()
            else:
                continue
            if not reference and not magnitude:
                continue
            out.append([reference, magnitude])
        if out:
            return out

    reference = _as_text(entry.get("reference")).strip()
    magnitude = _as_text(entry.get("magnitude")).strip()
    if reference or magnitude:
        return [[reference, magnitude]]
    return []


def _validate_pair_arity(identifier: str, value_group: int, pairs: list[list[str]]) -> None:
    pair_count = len(pairs)
    if value_group == 0:
        if pair_count <= 0:
            raise ValueError(f"{identifier}: VG0 rows must include at least one reference/magnitude pair")
        return
    if pair_count != value_group:
        raise ValueError(
            f"{identifier}: value_group {value_group} expects {value_group} pair(s), found {pair_count}"
        )


def _require_identifier(row: dict[str, Any]) -> tuple[str, int, int, int]:
    identifier = _as_text(row.get("identifier") or row.get("row_id")).strip()
    layer, value_group, iteration = parse_datum_identifier(identifier)
    if not (
        isinstance(layer, int)
        and isinstance(value_group, int)
        and isinstance(iteration, int)
        and iteration > 0
    ):
        raise ValueError(f"Invalid anthology datum identifier: {identifier or '<missing>'}")
    return identifier, layer, value_group, iteration


def rows_to_save_state(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[int, dict[int, list[dict[str, Any]]]] = {}
    row_count = 0
    pair_count = 0

    for row in sort_rows(rows):
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
            iterations_per_group.append(
                {
                    "layer": layer,
                    "value_group": value_group,
                    "count": len(rows_payload),
                }
            )
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


def save_state_to_rows(save_state: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(save_state, dict):
        raise ValueError("save_state must be a JSON object")

    schema = _as_text(save_state.get("schema")).strip()
    if schema and schema != SAVE_STATE_SCHEMA:
        raise ValueError(f"Unsupported anthology save-state schema: {schema}")

    layers = save_state.get("layers")
    if not isinstance(layers, list):
        raise ValueError("save_state.layers must be a list")

    rows: list[dict[str, Any]] = []
    seen_identifiers: set[str] = set()

    for layer_entry in layers:
        if not isinstance(layer_entry, dict):
            raise ValueError("Each layer entry must be an object")
        layer_raw = layer_entry.get("layer")
        try:
            layer = int(layer_raw)
        except Exception as exc:
            raise ValueError(f"Invalid layer value: {layer_raw}") from exc

        value_groups = layer_entry.get("value_groups")
        if not isinstance(value_groups, list):
            raise ValueError(f"Layer {layer}: value_groups must be a list")

        for value_group_entry in value_groups:
            if not isinstance(value_group_entry, dict):
                raise ValueError(f"Layer {layer}: each value group entry must be an object")
            value_group_raw = value_group_entry.get("value_group")
            try:
                value_group = int(value_group_raw)
            except Exception as exc:
                raise ValueError(f"Layer {layer}: invalid value_group {value_group_raw}") from exc

            group_rows = value_group_entry.get("rows")
            if not isinstance(group_rows, list):
                raise ValueError(f"Layer {layer}, value_group {value_group}: rows must be a list")

            for row_index, row_entry in enumerate(group_rows, start=1):
                if not isinstance(row_entry, dict):
                    raise ValueError(
                        f"Layer {layer}, value_group {value_group}: each row entry must be an object"
                    )
                identifier = _as_text(row_entry.get("identifier")).strip() or f"{layer}-{value_group}-{row_index}"
                id_layer, id_value_group, id_iteration = parse_datum_identifier(identifier)
                if not (
                    isinstance(id_layer, int)
                    and isinstance(id_value_group, int)
                    and isinstance(id_iteration, int)
                    and id_iteration > 0
                ):
                    raise ValueError(f"Invalid row identifier in save state: {identifier}")
                if id_layer != layer or id_value_group != value_group:
                    raise ValueError(
                        f"{identifier}: parent layer/value_group does not match row identifier"
                    )
                if identifier in seen_identifiers:
                    raise ValueError(f"Duplicate row identifier in save state: {identifier}")
                seen_identifiers.add(identifier)

                pairs = _pair_matrix_from_state_entry(row_entry)
                _validate_pair_arity(identifier, value_group, pairs)

                pair_payload = [
                    {
                        "reference": _as_text(reference).strip(),
                        "magnitude": _as_text(magnitude).strip(),
                    }
                    for reference, magnitude in pairs
                ]
                first_reference = pair_payload[0]["reference"] if pair_payload else ""
                first_magnitude = pair_payload[0]["magnitude"] if pair_payload else ""
                rows.append(
                    {
                        "row_id": identifier,
                        "identifier": identifier,
                        "label": _as_text(row_entry.get("label")).strip(),
                        "pairs": pair_payload,
                        "pair_count": len(pair_payload),
                        "reference": first_reference,
                        "magnitude": first_magnitude,
                    }
                )

    return sort_rows(rows)


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

    if strict and (not valid or warnings):
        message = "; ".join(warnings) if warnings else "anthology payload could not be normalized"
        raise ValueError(message)

    return sort_rows(rows)


def rows_to_compact_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for index, row in enumerate(sort_rows(rows), start=1):
        key, value = record_to_compact_row(row, index)
        payload[key] = value
    return payload


def compact_payload_to_save_state(payload: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    return rows_to_save_state(compact_payload_to_rows(payload, strict=strict))


def save_state_to_compact_payload(save_state: dict[str, Any]) -> dict[str, Any]:
    return rows_to_compact_payload(save_state_to_rows(save_state))
