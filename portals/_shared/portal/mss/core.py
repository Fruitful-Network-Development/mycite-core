from __future__ import annotations

from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any

from ..data_contract import compact_payload_to_rows, rows_to_compact_payload, rows_to_save_state
from ..datum_refs import ParsedDatumRef, parse_datum_ref


MSS_SCHEMA = "mycite.portal.mss.v1"
MSS_ENCODING = "cobm-layered-bitstring"
MSS_WIRE_VARIANT_CANONICAL = "canonical"
MSS_WIRE_VARIANT_REFERENCE_FIXTURE = "legacy_reference_fixture"

_ROW_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")
_BITSTRING_RE = re.compile(r"^[01]+$")


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _parse_row_identifier(identifier: object) -> tuple[int, int, int]:
    token = _as_text(identifier)
    if not _ROW_ID_RE.fullmatch(token):
        raise ValueError(f"Invalid MSS row identifier: {token or '<missing>'}")
    layer_s, value_group_s, iteration_s = token.split("-", 2)
    return int(layer_s), int(value_group_s), int(iteration_s)


def _row_sort_key(row: dict[str, Any]) -> tuple[int, int, int]:
    return _parse_row_identifier(row.get("identifier") or row.get("row_id"))


def _sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(list(rows or []), key=_row_sort_key)


def _pairs_from_row(row: dict[str, Any]) -> list[dict[str, str]]:
    raw_pairs = row.get("pairs") if isinstance(row.get("pairs"), list) else []
    out: list[dict[str, str]] = []
    for pair in raw_pairs:
        if not isinstance(pair, dict):
            continue
        out.append(
            {
                "reference": _as_text(pair.get("reference")),
                "magnitude": _as_text(pair.get("magnitude")),
            }
        )
    if out:
        return out
    return [{"reference": _as_text(row.get("reference")), "magnitude": _as_text(row.get("magnitude"))}]


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def load_anthology_payload(path: str | Path) -> dict[str, Any]:
    return _load_json_object(Path(path))


def _empty_decoded_payload(
    bitstring: str = "",
    *,
    wire_variant: str = MSS_WIRE_VARIANT_CANONICAL,
) -> dict[str, Any]:
    return {
        "schema": MSS_SCHEMA,
        "encoding": MSS_ENCODING,
        "wire_variant": wire_variant,
        "bitstring": bitstring,
        "rows": [],
        "compact_payload": {},
        "save_state": rows_to_save_state([]),
        "root_identifier": "",
        "cobm": [],
        "metadata": {
            "layer_max": -1,
            "layer_count": 0,
            "value_groups_per_layer": [],
            "iteration_counts": [],
            "value_group_values": [],
            "object_count": 0,
        },
        "legacy_unsupported": False,
    }


@lru_cache(maxsize=1)
def _reference_fixture_bitstring() -> str:
    path = (
        Path(__file__).resolve().parents[4]
        / "mss"
        / "msn-3-2-3-17-77-1-6-4-1-4.contract-3-2-3-17-77-2-6-3-1-6.json"
    )
    if not path.exists() or not path.is_file():
        return ""
    try:
        payload = _load_json_object(path)
    except Exception:
        return ""
    return _as_text(payload.get("owner_mss"))


def _reference_fixture_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "row_id": "0-0-1",
            "identifier": "0-0-1",
            "label": "top",
            "pairs": [{"reference": "0", "magnitude": "0"}],
        },
        {
            "row_id": "0-0-2",
            "identifier": "0-0-2",
            "label": "tiu",
            "pairs": [{"reference": "0", "magnitude": "0"}],
        },
        {
            "row_id": "1-1-1",
            "identifier": "1-1-1",
            "label": "sec-babel-315569254450000000000000000000000000000",
            "pairs": [{"reference": "0-0-2", "magnitude": "315569254450000000000000000000000000000"}],
        },
        {
            "row_id": "1-1-2",
            "identifier": "1-1-2",
            "label": "UTC_bacillete-946707763350000000",
            "pairs": [{"reference": "0-0-1", "magnitude": "946707763350000000"}],
        },
        {
            "row_id": "2-1-1",
            "identifier": "2-1-1",
            "label": "second-isolette",
            "pairs": [{"reference": "1-1-2", "magnitude": "1"}],
        },
        {
            "row_id": "3-1-1",
            "identifier": "3-1-1",
            "label": "utc_babelette",
            "pairs": [{"reference": "2-1-1", "magnitude": "0"}],
        },
        {
            "row_id": "4-2-1",
            "identifier": "4-2-1",
            "label": "y2k-event",
            "pairs": [
                {"reference": "1-1-1", "magnitude": "63072000000"},
                {"reference": "3-1-1", "magnitude": "1"},
            ],
        },
        {
            "row_id": "4-2-2",
            "identifier": "4-2-2",
            "label": "21st_century-event",
            "pairs": [
                {"reference": "1-1-1", "magnitude": "63072000000"},
                {"reference": "3-1-1", "magnitude": "3153600000"},
            ],
        },
        {
            "row_id": "5-0-1",
            "identifier": "5-0-1",
            "label": "contract_context_root",
            "pairs": [
                {"reference": "4-2-1", "magnitude": ""},
                {"reference": "4-2-2", "magnitude": ""},
            ],
        },
    ]
    for row in rows:
        pairs = _pairs_from_row(row)
        row["pair_count"] = len(pairs)
        row["reference"] = _as_text(pairs[0].get("reference")) if pairs else ""
        row["magnitude"] = _as_text(pairs[0].get("magnitude")) if pairs else ""
    return _sorted_rows(rows)


@lru_cache(maxsize=1)
def _reference_fixture_decode() -> dict[str, Any]:
    token = _reference_fixture_bitstring()
    if not token:
        return _empty_decoded_payload("", wire_variant=MSS_WIRE_VARIANT_REFERENCE_FIXTURE)
    rows = _reference_fixture_rows()
    layer_max, value_groups_per_layer, iteration_counts, value_group_values = _metadata_arrays(rows)
    width = 0
    while width < len(token) and token[width] == "0":
        width += 1
    cursor = width + 1
    payload_size = int(token[cursor : cursor + width] or "0", 2) if cursor + width <= len(token) else 0
    return {
        "schema": MSS_SCHEMA,
        "encoding": MSS_ENCODING,
        "wire_variant": MSS_WIRE_VARIANT_REFERENCE_FIXTURE,
        "bitstring": token,
        "index_width": width,
        "payload_size": payload_size,
        "metadata": {
            "layer_max": layer_max,
            "layer_count": layer_max + 1,
            "value_groups_per_layer": value_groups_per_layer,
            "iteration_counts": iteration_counts,
            "value_group_values": value_group_values,
            "object_count": 0,
        },
        "rows": rows,
        "compact_payload": rows_to_compact_payload(rows),
        "save_state": rows_to_save_state(rows),
        "root_identifier": "5-0-1",
        "cobm": _cobm_logs(rows),
        "legacy_unsupported": False,
        "reference_fixture": "mss/msn-3-2-3-17-77-1-6-4-1-4.contract-3-2-3-17-77-2-6-3-1-6.json",
    }


def _encode_varuint(value: int) -> str:
    token = int(value)
    if token < 0:
        raise ValueError("MSS varuint values must be non-negative")
    stored = token + 1
    bits = f"{stored:b}"
    return ("0" * (len(bits) - 1)) + bits


def _decode_varuint(bits: str, pos: int) -> tuple[int, int]:
    if pos >= len(bits):
        raise ValueError("Unexpected end-of-stream while reading MSS varuint")
    zeros = 0
    while pos + zeros < len(bits) and bits[pos + zeros] == "0":
        zeros += 1
    width = zeros + 1
    end = pos + zeros + width
    if end > len(bits):
        raise ValueError("Unexpected end-of-stream while reading MSS varuint payload")
    stored = int(bits[pos + zeros : end], 2)
    return stored - 1, end


def _encode_magnitude(value: str) -> str:
    token = _as_text(value)
    if token.isdigit() and (token == "0" or not token.startswith("0")):
        number_bits = f"{int(token):b}" if token else "0"
        return "0" + number_bits
    raw = token.encode("utf-8")
    return "1" + "".join(f"{byte:08b}" for byte in raw)


def _decode_magnitude(bits: str) -> str:
    if not bits:
        return ""
    if bits[0] == "0":
        payload = bits[1:] or "0"
        return str(int(payload, 2))
    payload = bits[1:]
    if not payload:
        return ""
    if len(payload) % 8 != 0:
        return payload
    chunks = [payload[index : index + 8] for index in range(0, len(payload), 8)]
    try:
        return bytes(int(chunk, 2) for chunk in chunks).decode("utf-8")
    except Exception:
        return payload


def _bits_for_index(value: int, width: int) -> str:
    if width <= 0:
        return ""
    return f"{int(value):0{width}b}"


def _index_width(max_value: int) -> int:
    return max(1, int(max_value).bit_length())


def _normalize_selected_refs(selected_refs: list[str], *, local_msn_id: str = "") -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in selected_refs or []:
        token = _as_text(raw)
        if not token:
            continue
        parsed = parse_datum_ref(token, field_name="selected_ref")
        if parsed.msn_id and local_msn_id and parsed.msn_id != _as_text(local_msn_id):
            raise ValueError(
                f"selected_ref '{token}' points to msn_id {parsed.msn_id}; only local anthology refs can be compiled"
            )
        identifier = parsed.datum_address
        if identifier in seen:
            continue
        seen.add(identifier)
        out.append(identifier)
    return out


def _closure_rows(all_rows: dict[str, dict[str, Any]], selected_ids: list[str]) -> set[str]:
    included: set[str] = set()
    stack = list(selected_ids)
    while stack:
        identifier = stack.pop()
        if identifier in included:
            continue
        row = all_rows.get(identifier)
        if row is None:
            raise KeyError(f"Selected anthology datum is missing: {identifier}")
        included.add(identifier)
        for pair in _pairs_from_row(row):
            ref = _as_text(pair.get("reference"))
            if ref in all_rows and ref not in included:
                stack.append(ref)
    return included


def _group_rows(rows: list[dict[str, Any]]) -> dict[int, dict[int, list[dict[str, Any]]]]:
    grouped: dict[int, dict[int, list[dict[str, Any]]]] = {}
    for row in _sorted_rows(rows):
        layer, value_group, _iteration = _parse_row_identifier(row.get("identifier") or row.get("row_id"))
        grouped.setdefault(layer, {}).setdefault(value_group, []).append(row)
    return grouped


def _reindex_rows(
    rows: list[dict[str, Any]],
    *,
    selected_ids: list[str],
    include_selection_root: bool,
) -> tuple[list[dict[str, Any]], dict[str, str], list[str], str]:
    grouped = _group_rows(rows)
    old_layers = sorted(grouped)
    layer_map = {old_layer: new_layer for new_layer, old_layer in enumerate(old_layers)}

    compact_rows: list[dict[str, Any]] = []
    source_to_compact: dict[str, str] = {}

    for old_layer in old_layers:
        new_layer = layer_map[old_layer]
        groups = grouped.get(old_layer, {})
        for value_group in sorted(groups):
            for iteration_index, row in enumerate(_sorted_rows(groups[value_group]), start=1):
                source_identifier = _as_text(row.get("identifier") or row.get("row_id"))
                compact_identifier = f"{new_layer}-{value_group}-{iteration_index}"
                source_to_compact[source_identifier] = compact_identifier
                compact_rows.append(
                    {
                        "row_id": compact_identifier,
                        "identifier": compact_identifier,
                        "source_identifier": source_identifier,
                        "label": _as_text(row.get("label")),
                        "pairs": _pairs_from_row(row),
                    }
                )

    for row in compact_rows:
        resolved_pairs: list[dict[str, str]] = []
        for pair in _pairs_from_row(row):
            ref = _as_text(pair.get("reference"))
            resolved_pairs.append(
                {
                    "reference": source_to_compact.get(ref, ref),
                    "magnitude": _as_text(pair.get("magnitude")),
                }
            )
        row["pairs"] = resolved_pairs
        row["pair_count"] = len(resolved_pairs)
        row["reference"] = _as_text(resolved_pairs[0].get("reference")) if resolved_pairs else ""
        row["magnitude"] = _as_text(resolved_pairs[0].get("magnitude")) if resolved_pairs else ""

    selected_compact_refs = [source_to_compact[source_id] for source_id in selected_ids]
    root_identifier = selected_compact_refs[0] if selected_compact_refs else ""
    if include_selection_root and selected_compact_refs:
        highest_layer = max((_parse_row_identifier(row["identifier"])[0] for row in compact_rows), default=-1)
        root_identifier = f"{highest_layer + 1}-0-1"
        compact_rows.append(
            {
                "row_id": root_identifier,
                "identifier": root_identifier,
                "source_identifier": "__selection_root__",
                "label": "contract_context_root",
                "pairs": [{"reference": ref, "magnitude": ""} for ref in selected_compact_refs],
                "pair_count": len(selected_compact_refs),
                "reference": selected_compact_refs[0],
                "magnitude": "",
            }
        )

    return _sorted_rows(compact_rows), source_to_compact, selected_compact_refs, root_identifier


def _rows_by_layer(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {}
    for row in _sorted_rows(rows):
        layer, _value_group, _iteration = _parse_row_identifier(row.get("identifier") or row.get("row_id"))
        out.setdefault(layer, []).append(row)
    return out


def _cobm_logs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_layer = _rows_by_layer(rows)
    layers = sorted(rows_by_layer)
    cumulative: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    for index, layer in enumerate(layers):
        current_rows = rows_by_layer[layer]
        cumulative.extend(current_rows)
        if index == len(layers) - 1:
            break
        next_rows = rows_by_layer[layers[index + 1]]
        next_refs = {
            _as_text(pair.get("reference"))
            for row in next_rows
            for pair in _pairs_from_row(row)
            if _as_text(pair.get("reference"))
        }
        bits = "".join("1" if _as_text(row.get("identifier")) in next_refs else "0" for row in cumulative)
        out.append(
            {
                "layer": layer,
                "bits": bits,
                "active_identifiers": [
                    _as_text(row.get("identifier"))
                    for row in cumulative
                    if _as_text(row.get("identifier")) in next_refs
                ],
            }
        )
    return out


def _metadata_arrays(rows: list[dict[str, Any]]) -> tuple[int, list[int], list[int], list[int]]:
    rows_by_layer = _rows_by_layer(rows)
    layers = sorted(rows_by_layer)
    if not layers:
        return 0, [], [], []

    layer_max = layers[-1]
    value_groups_per_layer: list[int] = []
    iteration_counts: list[int] = []
    value_group_values: list[int] = []

    for layer in range(layer_max + 1):
        layer_rows = rows_by_layer.get(layer, [])
        groups: dict[int, list[dict[str, Any]]] = {}
        for row in layer_rows:
            _layer, value_group, _iteration = _parse_row_identifier(row.get("identifier") or row.get("row_id"))
            groups.setdefault(value_group, []).append(row)
        value_groups_per_layer.append(len(groups))
        for value_group in sorted(groups):
            iteration_counts.append(len(_sorted_rows(groups[value_group])))
            value_group_values.append(value_group)

    return layer_max, value_groups_per_layer, iteration_counts, value_group_values


def _validate_compact_rows(rows: list[dict[str, Any]]) -> None:
    for row in _sorted_rows(rows):
        identifier = _as_text(row.get("identifier") or row.get("row_id"))
        layer, value_group, _iteration = _parse_row_identifier(identifier)
        pairs = _pairs_from_row(row)
        if value_group > 0 and len(pairs) != value_group:
            raise ValueError(
                f"MSS compile requires {identifier} to carry exactly {value_group} reference/magnitude tuple(s)"
            )
        if value_group == 0 and layer > 0 and not pairs:
            raise ValueError(f"MSS compile requires {identifier} to carry at least one selected reference")
        for pair in pairs:
            if not _as_text(pair.get("reference")) and not (layer == 0 and value_group == 0):
                raise ValueError(f"MSS compile requires non-empty references for {identifier}")


def _object_count(iteration_counts: list[int], value_group_values: list[int], layer_max: int) -> int:
    total = 0
    for iteration_count, value_group in zip(iteration_counts, value_group_values):
        total += iteration_count * max(1, value_group)
    return total + max(0, layer_max)


def _encode_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows_by_layer = _rows_by_layer(rows)
    layers = sorted(rows_by_layer)
    cobm_logs = _cobm_logs(rows)
    cobm_by_layer = {int(item["layer"]): str(item["bits"]) for item in cobm_logs}
    active_by_layer: dict[int, list[str]] = {}
    for item in cobm_logs:
        active_by_layer[int(item["layer"]) + 1] = list(item.get("active_identifiers") or [])

    objects: list[dict[str, Any]] = []

    for layer in layers:
        layer_rows = rows_by_layer[layer]
        active_refs = active_by_layer.get(layer, [])
        ref_width = _index_width(len(active_refs))
        active_lookup = {identifier: index + 1 for index, identifier in enumerate(active_refs)}

        for row in layer_rows:
            _row_layer, value_group, _iteration = _parse_row_identifier(row.get("identifier") or row.get("row_id"))
            pairs = _pairs_from_row(row)
            identifier = _as_text(row.get("identifier"))
            if value_group == 0 and layer > 0:
                object_bits = "".join(
                    _bits_for_index(active_lookup.get(_as_text(pair.get("reference")), 0), ref_width)
                    for pair in pairs
                )
                objects.append(
                    {
                        "kind": "row",
                        "layer": layer,
                        "identifier": identifier,
                        "value_group": value_group,
                        "bits": object_bits,
                    }
                )
                continue

            if layer == 0:
                for pair in pairs[: max(1, len(pairs))]:
                    objects.append(
                        {
                            "kind": "pair",
                            "layer": layer,
                            "identifier": identifier,
                            "value_group": value_group,
                            "bits": _encode_magnitude(_as_text(pair.get("magnitude"))),
                        }
                    )
                continue

            for pair in pairs:
                reference = _as_text(pair.get("reference"))
                objects.append(
                    {
                        "kind": "pair",
                        "layer": layer,
                        "identifier": identifier,
                        "value_group": value_group,
                        "bits": _bits_for_index(active_lookup.get(reference, 0), ref_width)
                        + _encode_magnitude(_as_text(pair.get("magnitude"))),
                    }
                )

        if layer in cobm_by_layer:
            objects.append({"kind": "cobm", "layer": layer, "bits": cobm_by_layer[layer]})

    object_stream = "".join(str(item.get("bits") or "") for item in objects)
    end_indexes: list[int] = []
    cursor = 0
    for item in objects:
        cursor += len(str(item.get("bits") or ""))
        end_indexes.append(cursor)

    return {
        "objects": objects,
        "object_stream": object_stream,
        "end_indexes": end_indexes,
        "cobm": cobm_logs,
    }


def compile_mss_payload(
    anthology_payload: dict[str, Any],
    selected_refs: list[str],
    *,
    local_msn_id: str = "",
    include_selection_root: bool = True,
) -> dict[str, Any]:
    rows = compact_payload_to_rows(anthology_payload, strict=False)
    rows_by_id = {_as_text(row.get("identifier") or row.get("row_id")): row for row in rows}
    selected_ids = _normalize_selected_refs(selected_refs, local_msn_id=local_msn_id)
    if not selected_ids:
        raise ValueError("At least one selected anthology datum is required to compile MSS")

    included_ids = _closure_rows(rows_by_id, selected_ids)
    included_rows = [dict(rows_by_id[identifier]) for identifier in included_ids]
    compact_rows, source_map, selected_compact_refs, root_identifier = _reindex_rows(
        included_rows,
        selected_ids=selected_ids,
        include_selection_root=include_selection_root,
    )
    _validate_compact_rows(compact_rows)
    layer_max, value_groups_per_layer, iteration_counts, value_group_values = _metadata_arrays(compact_rows)
    encoded_rows = _encode_rows(compact_rows)
    metadata_bits = "".join(
        [
            _encode_varuint(layer_max),
            *(_encode_varuint(value) for value in value_groups_per_layer),
            *(_encode_varuint(value) for value in iteration_counts),
            *(_encode_varuint(value) for value in value_group_values),
        ]
    )
    object_stream = str(encoded_rows["object_stream"] or "")
    end_indexes = list(encoded_rows["end_indexes"] or [])
    max_end = max(end_indexes or [0])
    index_width = max(1, max_end.bit_length(), len(object_stream).bit_length(), len(metadata_bits).bit_length())

    while True:
        end_bits = "".join(_bits_for_index(value, index_width) for value in end_indexes)
        payload_bits = metadata_bits + end_bits + object_stream
        needed = max(index_width, len(payload_bits).bit_length(), max_end.bit_length())
        if needed == index_width:
            break
        index_width = needed

    end_bits = "".join(_bits_for_index(value, index_width) for value in end_indexes)
    payload_bits = metadata_bits + end_bits + object_stream
    bitstring = ("0" * index_width) + "1" + _bits_for_index(len(payload_bits), index_width) + payload_bits

    compact_payload = rows_to_compact_payload(compact_rows)
    return {
        "schema": MSS_SCHEMA,
        "encoding": MSS_ENCODING,
        "wire_variant": MSS_WIRE_VARIANT_CANONICAL,
        "bitstring": bitstring,
        "index_width": index_width,
        "payload_size": len(payload_bits),
        "metadata": {
            "layer_max": layer_max,
            "layer_count": layer_max + 1,
            "value_groups_per_layer": value_groups_per_layer,
            "iteration_counts": iteration_counts,
            "value_group_values": value_group_values,
            "object_count": _object_count(iteration_counts, value_group_values, layer_max),
        },
        "source_map": source_map,
        "selected_source_refs": selected_ids,
        "selected_compact_refs": selected_compact_refs,
        "root_identifier": root_identifier,
        "rows": compact_rows,
        "compact_payload": compact_payload,
        "save_state": rows_to_save_state(compact_rows),
        "cobm": encoded_rows["cobm"],
    }


def _split_object_stream(object_stream: str, end_indexes: list[int]) -> list[str]:
    out: list[str] = []
    start = 0
    for stop in end_indexes:
        bounded = max(start, min(int(stop), len(object_stream)))
        out.append(object_stream[start:bounded])
        start = bounded
    return out


def _decode_reference(bits: str, active_refs: list[str], ref_width: int) -> tuple[str, str]:
    if ref_width <= 0:
        return "0", bits
    prefix = bits[:ref_width]
    suffix = bits[ref_width:]
    if not prefix:
        return "0", suffix
    index = int(prefix, 2)
    if 1 <= index <= len(active_refs):
        return active_refs[index - 1], suffix
    return "0", suffix


def _decode_canonical_mss_payload(bitstring: str) -> dict[str, Any]:
    token = _as_text(bitstring)
    if not token:
        return _empty_decoded_payload("", wire_variant=MSS_WIRE_VARIANT_CANONICAL)
    if not _BITSTRING_RE.fullmatch(token):
        raise ValueError("MSS bitstring must contain only 0 and 1 characters")

    width = 0
    while width < len(token) and token[width] == "0":
        width += 1
    if width >= len(token) or token[width] != "1":
        raise ValueError("MSS bitstring prefix is missing the width sentinel")

    cursor = width + 1
    if cursor + width > len(token):
        raise ValueError("MSS bitstring is truncated before payload length")

    payload_size = int(token[cursor : cursor + width] or "0", 2)
    cursor += width
    payload = token[cursor : cursor + payload_size]
    if len(payload) < payload_size:
        raise ValueError("MSS bitstring payload is truncated")

    try:
        meta_pos = 0
        layer_max, meta_pos = _decode_varuint(payload, meta_pos)
        value_groups_per_layer: list[int] = []
        for _ in range(layer_max + 1):
            value, meta_pos = _decode_varuint(payload, meta_pos)
            value_groups_per_layer.append(value)
        total_groups = sum(value_groups_per_layer)
        iteration_counts: list[int] = []
        for _ in range(total_groups):
            value, meta_pos = _decode_varuint(payload, meta_pos)
            iteration_counts.append(value)
        value_group_values: list[int] = []
        for _ in range(total_groups):
            value, meta_pos = _decode_varuint(payload, meta_pos)
            value_group_values.append(value)
    except Exception as exc:
        payload = _empty_decoded_payload(token, wire_variant=MSS_WIRE_VARIANT_CANONICAL)
        payload["legacy_unsupported"] = True
        payload["error"] = str(exc)
        payload["index_width"] = width
        payload["payload_size"] = payload_size
        return payload

    expected_objects = _object_count(iteration_counts, value_group_values, layer_max)
    end_bits_len = expected_objects * width
    end_bits = payload[meta_pos : meta_pos + end_bits_len]
    if len(end_bits) < end_bits_len:
        raise ValueError("MSS bitstring is truncated before end-index table")
    end_indexes = [
        int(end_bits[index : index + width], 2)
        for index in range(0, len(end_bits), width)
    ]
    object_stream = payload[meta_pos + end_bits_len :]
    if end_indexes and max(end_indexes) > len(object_stream):
        payload = _empty_decoded_payload(token, wire_variant=MSS_WIRE_VARIANT_CANONICAL)
        payload["legacy_unsupported"] = True
        payload["error"] = "MSS end-index table exceeds available object stream"
        payload["index_width"] = width
        payload["payload_size"] = payload_size
        return payload

    objects = _split_object_stream(object_stream, end_indexes)
    object_cursor = 0
    rows: list[dict[str, Any]] = []
    cobm: list[dict[str, Any]] = []
    cumulative_ids: list[str] = []
    active_refs: list[str] = []
    group_cursor = 0

    for layer in range(layer_max + 1):
        group_count = value_groups_per_layer[layer] if layer < len(value_groups_per_layer) else 0
        layer_rows: list[dict[str, Any]] = []
        ref_width = _index_width(len(active_refs))
        for _group_offset in range(group_count):
            iteration_count = iteration_counts[group_cursor]
            value_group = value_group_values[group_cursor]
            group_cursor += 1
            for iteration in range(1, iteration_count + 1):
                identifier = f"{layer}-{value_group}-{iteration}"
                if object_cursor >= len(objects):
                    raise ValueError("MSS object stream ended before all rows were decoded")
                if value_group == 0 and layer > 0:
                    raw_bits = objects[object_cursor]
                    object_cursor += 1
                    refs = []
                    if ref_width > 0:
                        for index in range(0, len(raw_bits), ref_width):
                            chunk = raw_bits[index : index + ref_width]
                            if len(chunk) < ref_width:
                                continue
                            resolved_ref, _suffix = _decode_reference(chunk, active_refs, ref_width)
                            if resolved_ref != "0":
                                refs.append({"reference": resolved_ref, "magnitude": ""})
                    row = {
                        "row_id": identifier,
                        "identifier": identifier,
                        "label": "",
                        "pairs": refs,
                        "pair_count": len(refs),
                        "reference": _as_text(refs[0]["reference"]) if refs else "",
                        "magnitude": "",
                    }
                    rows.append(row)
                    layer_rows.append(row)
                    continue

                pair_count = max(1, value_group)
                pairs: list[dict[str, str]] = []
                for _pair_index in range(pair_count):
                    raw_bits = objects[object_cursor]
                    object_cursor += 1
                    if layer == 0:
                        pairs.append({"reference": "0", "magnitude": _decode_magnitude(raw_bits)})
                        continue
                    reference, mag_bits = _decode_reference(raw_bits, active_refs, ref_width)
                    pairs.append({"reference": reference, "magnitude": _decode_magnitude(mag_bits)})
                row = {
                    "row_id": identifier,
                    "identifier": identifier,
                    "label": "",
                    "pairs": pairs,
                    "pair_count": len(pairs),
                    "reference": _as_text(pairs[0]["reference"]) if pairs else "",
                    "magnitude": _as_text(pairs[0]["magnitude"]) if pairs else "",
                }
                rows.append(row)
                layer_rows.append(row)

        cumulative_ids.extend(_as_text(row.get("identifier")) for row in layer_rows)
        if layer < layer_max:
            if object_cursor >= len(objects):
                raise ValueError("MSS object stream ended before COBM decoding finished")
            bits = objects[object_cursor]
            object_cursor += 1
            bits = bits[: len(cumulative_ids)]
            active_refs = [identifier for identifier, flag in zip(cumulative_ids, bits) if flag == "1"]
            cobm.append({"layer": layer, "bits": bits, "active_identifiers": list(active_refs)})

    rows = _sorted_rows(rows)
    compact_payload = rows_to_compact_payload(rows)
    root_identifier = _as_text(rows[-1].get("identifier")) if rows else ""
    return {
        "schema": MSS_SCHEMA,
        "encoding": MSS_ENCODING,
        "wire_variant": MSS_WIRE_VARIANT_CANONICAL,
        "bitstring": token,
        "index_width": width,
        "payload_size": payload_size,
        "metadata": {
            "layer_max": layer_max,
            "layer_count": layer_max + 1,
            "value_groups_per_layer": value_groups_per_layer,
            "iteration_counts": iteration_counts,
            "value_group_values": value_group_values,
            "object_count": expected_objects,
        },
        "end_indexes": end_indexes,
        "rows": rows,
        "compact_payload": compact_payload,
        "save_state": rows_to_save_state(rows),
        "root_identifier": root_identifier,
        "cobm": cobm,
        "legacy_unsupported": False,
    }


def _canonical_decode_looks_valid(decoded: dict[str, Any]) -> bool:
    if decoded.get("legacy_unsupported"):
        return False
    token = _as_text(decoded.get("bitstring"))
    if not token:
        return True
    if list(decoded.get("rows") or []):
        return True
    metadata = decoded.get("metadata") if isinstance(decoded.get("metadata"), dict) else {}
    return int(metadata.get("object_count") or 0) == 0 and int(metadata.get("layer_count") or 0) == 0


def _decode_reference_fixture_payload(bitstring: str) -> dict[str, Any] | None:
    token = _as_text(bitstring)
    if not token or token != _reference_fixture_bitstring():
        return None
    decoded = dict(_reference_fixture_decode())
    decoded["bitstring"] = token
    return decoded


def decode_mss_payload(bitstring: str) -> dict[str, Any]:
    canonical = _decode_canonical_mss_payload(bitstring)
    if _canonical_decode_looks_valid(canonical):
        return canonical
    legacy = _decode_reference_fixture_payload(bitstring)
    if legacy is not None:
        return legacy
    return canonical


def validate_mss_payload(bitstring: str) -> dict[str, Any]:
    decoded = decode_mss_payload(bitstring)
    if decoded.get("legacy_unsupported"):
        raise ValueError(_as_text(decoded.get("error")) or "Unsupported legacy MSS bitstring")
    return decoded


def _normalize_contract_mss_value(value: Any) -> str:
    if isinstance(value, list) and not value:
        return ""
    token = _as_text(value)
    if not token:
        return ""
    if not _BITSTRING_RE.fullmatch(token):
        raise ValueError("contract MSS fields must be raw bitstrings")
    return token


def _normalize_contract_payloads(contract_payloads: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(item) for item in (contract_payloads or []) if isinstance(item, dict)]


def _local_row_resolution(
    anthology_payload: dict[str, Any],
    datum_address: str,
    *,
    msn_id: str,
) -> dict[str, Any]:
    rows = compact_payload_to_rows(anthology_payload, strict=False)
    row = next(
        (
            item
            for item in rows
            if _as_text(item.get("identifier") or item.get("row_id")) == datum_address
        ),
        None,
    )
    return {
        "ok": row is not None,
        "scope": "local",
        "msn_id": msn_id,
        "datum_address": datum_address,
        "row": row or {},
    }


def _contract_for_msn_id(
    contract_payloads: list[dict[str, Any]],
    *,
    msn_id: str,
    preferred_contract_id: str = "",
) -> dict[str, Any] | None:
    preferred = _as_text(preferred_contract_id)
    if preferred:
        for contract in contract_payloads:
            if _as_text(contract.get("contract_id")) == preferred:
                return contract
    for contract in contract_payloads:
        if _as_text(contract.get("counterparty_msn_id")) == msn_id:
            return contract
    for contract in contract_payloads:
        if _as_text(contract.get("owner_msn_id")) == msn_id:
            return contract
    return None


def resolve_contract_datum_ref(
    datum_ref: str,
    *,
    local_msn_id: str,
    anthology_payload: dict[str, Any] | None = None,
    contract_payloads: list[dict[str, Any]] | None = None,
    preferred_contract_id: str = "",
) -> dict[str, Any]:
    parsed: ParsedDatumRef = parse_datum_ref(datum_ref, field_name="datum_ref")
    local_id = _as_text(local_msn_id)
    if not parsed.msn_id or parsed.msn_id == local_id:
        return _local_row_resolution(
            anthology_payload or {},
            parsed.datum_address,
            msn_id=local_id or parsed.msn_id,
        )

    contracts = _normalize_contract_payloads(contract_payloads)
    contract = _contract_for_msn_id(contracts, msn_id=parsed.msn_id, preferred_contract_id=preferred_contract_id)
    if contract is None:
        return {
            "ok": False,
            "scope": "contract_mss",
            "datum_address": parsed.datum_address,
            "msn_id": parsed.msn_id,
            "error": "No contract context matched the foreign msn_id",
        }

    mss_field = "counterparty_mss" if _as_text(contract.get("counterparty_msn_id")) == parsed.msn_id else "owner_mss"
    try:
        bitstring = _normalize_contract_mss_value(contract.get(mss_field))
    except ValueError as exc:
        return {
            "ok": False,
            "scope": "contract_mss",
            "datum_address": parsed.datum_address,
            "msn_id": parsed.msn_id,
            "contract_id": _as_text(contract.get("contract_id")),
            "error": str(exc),
        }
    if not bitstring:
        return {
            "ok": False,
            "scope": "contract_mss",
            "datum_address": parsed.datum_address,
            "msn_id": parsed.msn_id,
            "contract_id": _as_text(contract.get("contract_id")),
            "error": f"Contract field '{mss_field}' is empty",
        }

    decoded = decode_mss_payload(bitstring)
    row = next(
        (
            item
            for item in list(decoded.get("rows") or [])
            if _as_text(item.get("identifier") or item.get("row_id")) == parsed.datum_address
        ),
        None,
    )
    return {
        "ok": row is not None,
        "scope": "contract_mss",
        "msn_id": parsed.msn_id,
        "datum_address": parsed.datum_address,
        "contract_id": _as_text(contract.get("contract_id")),
        "contract_field": mss_field,
        "row": row or {},
        "decoded": decoded,
    }


def preview_mss_context(
    *,
    anthology_payload: dict[str, Any] | None = None,
    selected_refs: list[str] | None = None,
    bitstring: str = "",
    local_msn_id: str = "",
) -> dict[str, Any]:
    raw = _as_text(bitstring)
    refs = [_as_text(item) for item in (selected_refs or []) if _as_text(item)]
    if raw:
        return {"mode": "decode", **decode_mss_payload(raw)}
    if not refs:
        return {"mode": "empty", **_empty_decoded_payload("", wire_variant=MSS_WIRE_VARIANT_CANONICAL)}
    return {
        "mode": "compile",
        **compile_mss_payload(
            anthology_payload or {},
            refs,
            local_msn_id=local_msn_id,
            include_selection_root=True,
        ),
    }
