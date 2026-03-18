from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

_NUMERIC_HYPHEN_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")


class SamrasRole(str, Enum):
    DEFINER = "definer"
    SPACE = "space"
    FIELD = "field"
    VALUE = "value"


@dataclass(frozen=True)
class SamrasDescriptor:
    shape_root: str
    role: SamrasRole
    structure_encoding: str
    structure_slots: tuple[int, ...]
    structure_digest: str
    value_kind: str
    source_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape_root": self.shape_root,
            "role": self.role.value,
            "structure_encoding": self.structure_encoding,
            "structure_slots": list(self.structure_slots),
            "structure_digest": self.structure_digest,
            "value_kind": self.value_kind,
            "source_ref": self.source_ref,
        }

    @property
    def active_slot_indexes(self) -> tuple[int, ...]:
        return tuple(index for index, value in enumerate(self.structure_slots) if int(value) > 0)


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _stable_digest(parts: Iterable[int]) -> str:
    raw = ",".join(str(int(x)) for x in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _parse_int_tokens(raw: str) -> tuple[int, ...]:
    token = _as_text(raw)
    if not token:
        raise ValueError("empty SAMRAS payload")
    if not _NUMERIC_HYPHEN_RE.fullmatch(token):
        raise ValueError("SAMRAS payload must be numeric-hyphen")
    out = tuple(int(part) for part in token.split("-"))
    if any(value < 0 for value in out):
        raise ValueError("SAMRAS payload may not contain negative integers")
    return out


def decode_structure_payload(
    raw: str,
    *,
    shape_root: str = "0-0-6",
    role: SamrasRole = SamrasRole.DEFINER,
    value_kind: str = "address_id",
    source_ref: str = "",
) -> SamrasDescriptor:
    slots = _parse_int_tokens(raw)
    return SamrasDescriptor(
        shape_root=shape_root,
        role=role,
        structure_encoding="samras.slot_array.v1",
        structure_slots=slots,
        structure_digest=_stable_digest(slots),
        value_kind=value_kind,
        source_ref=source_ref,
    )


def encode_structure_payload(descriptor: SamrasDescriptor) -> str:
    return "-".join(str(int(item)) for item in descriptor.structure_slots)


def decode_node_value(raw: str) -> tuple[int, ...]:
    return _parse_int_tokens(raw)


def encode_node_value(parts: Iterable[int]) -> str:
    out = tuple(int(item) for item in parts)
    if not out:
        raise ValueError("SAMRAS node value must contain at least one segment")
    if any(value < 0 for value in out):
        raise ValueError("SAMRAS node value may not contain negative integers")
    return "-".join(str(value) for value in out)


def normalize_descriptor(payload: dict[str, Any]) -> SamrasDescriptor:
    if not isinstance(payload, dict):
        raise ValueError("descriptor payload must be an object")
    slots = payload.get("structure_slots")
    if isinstance(slots, list):
        token = "-".join(str(int(item)) for item in slots)
    else:
        token = _as_text(payload.get("structure_payload"))
    role_token = _as_text(payload.get("role")).lower() or SamrasRole.DEFINER.value
    role = SamrasRole(role_token if role_token in {item.value for item in SamrasRole} else SamrasRole.DEFINER.value)
    return decode_structure_payload(
        token,
        shape_root=_as_text(payload.get("shape_root")) or "0-0-6",
        role=role,
        value_kind=_as_text(payload.get("value_kind")) or "address_id",
        source_ref=_as_text(payload.get("source_ref")),
    )


def validate_node_value(parts: tuple[int, ...], descriptor: SamrasDescriptor) -> dict[str, Any]:
    errors: list[str] = []
    if not parts:
        errors.append("empty SAMRAS node value")
    if descriptor.shape_root != "0-0-6":
        errors.append("descriptor is not bound to canonical SAMRAS shape root 0-0-6")
    if descriptor.role not in {SamrasRole.FIELD, SamrasRole.VALUE, SamrasRole.SPACE}:
        errors.append("descriptor role is not usable for node-value validation")
    return {
        "ok": not errors,
        "errors": errors,
        "normalized": encode_node_value(parts) if not errors else "",
        "descriptor_digest": descriptor.structure_digest,
        "value_kind": descriptor.value_kind,
    }


def ensure_resource_row(rows_by_address: dict[str, list[str]], *, address_id: str, title: str) -> dict[str, Any]:
    token = _as_text(address_id)
    name = _as_text(title)
    if not token or _NUMERIC_HYPHEN_RE.fullmatch(token) is None:
        raise ValueError("address_id must be numeric-hyphen")
    if not name:
        raise ValueError("title is required")
    existing = rows_by_address.get(token)
    if existing is None:
        rows_by_address[token] = [name]
        return {"created": True, "updated": False, "row": {token: [name]}}
    if list(existing) != [name]:
        rows_by_address[token] = [name]
        return {"created": False, "updated": True, "row": {token: [name]}}
    return {"created": False, "updated": False, "row": {token: [name]}}


def ensure_resource_object(
    payload: dict[str, Any],
    *,
    resource_id: str,
    descriptor: SamrasDescriptor,
    rows_by_address: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    out = dict(payload if isinstance(payload, dict) else {})
    out["schema"] = "mycite.sandbox.samras_resource.v1"
    out["resource_id"] = _as_text(resource_id)
    out["descriptor"] = descriptor.to_dict()
    out["rows_by_address"] = dict(rows_by_address if isinstance(rows_by_address, dict) else {})
    out["structure_payload"] = encode_structure_payload(descriptor)
    return out


def decode_resource_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_address = payload.get("rows_by_address") if isinstance(payload.get("rows_by_address"), dict) else {}
    out: list[dict[str, Any]] = []
    for key, value in rows_by_address.items():
        token = _as_text(key)
        if not token:
            continue
        names = value if isinstance(value, list) else [value]
        out.append({"address_id": token, "title": _as_text(names[0] if names else "")})
    out.sort(key=lambda item: tuple(int(part) for part in item["address_id"].split("-")))
    return out


def encode_resource_rows(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for row in rows:
        token = _as_text(row.get("address_id"))
        title = _as_text(row.get("title"))
        if not token:
            continue
        out[token] = [title]
    return out


def decode_structure_payload_from_row_magnitude(magnitude: str) -> SamrasDescriptor:
    raw = _as_text(magnitude)
    if raw.startswith("{") and raw.endswith("}"):
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            return normalize_descriptor(payload)
    return decode_structure_payload(raw)


_BIN_RE = re.compile(r"^[01]+$")
_ADDR_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")
_CANONICAL_HEADER_BITS = 8


@dataclass(frozen=True)
class SamrasStructure:
    root_ref: str
    address_width_bits: int
    stop_count_width_bits: int
    stop_count: int
    stop_addresses: list[int]
    node_values: list[int]
    address_map: dict[str, int]
    source_format: str
    canonical_state: str
    warnings: list[str]

    @property
    def decoded_value_count(self) -> int:
        return int(self.stop_count) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_ref": self.root_ref,
            "address_width_bits": int(self.address_width_bits),
            "stop_count_width_bits": int(self.stop_count_width_bits),
            "stop_count": int(self.stop_count),
            "decoded_value_count": int(self.decoded_value_count),
            "stop_addresses": [int(item) for item in list(self.stop_addresses)],
            "node_values": [int(item) for item in list(self.node_values)],
            "address_map": {str(key): int(value) for key, value in dict(self.address_map).items()},
            "source_format": self.source_format,
            "canonical_state": self.canonical_state,
            "warnings": [str(item) for item in list(self.warnings)],
        }


def _bit_width(value: int) -> int:
    token = int(value)
    return 1 if token <= 0 else len(format(token, "b"))


def _address_sort_key(address_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(address_id).split("-"))


def _sorted_addresses(address_map: dict[str, int]) -> list[str]:
    out = [str(key) for key in dict(address_map or {}) if _ADDR_RE.fullmatch(str(key))]
    out.sort(key=_address_sort_key)
    return out


def _compile_value_stream_and_stops(node_values: list[int]) -> tuple[str, list[int]]:
    stream_parts: list[str] = []
    stops: list[int] = []
    cursor = 0
    for index, token in enumerate(list(node_values or [])):
        bits = str(int(token))
        if not bits:
            bits = "0"
        if any(ch not in {"0", "1"} for ch in bits):
            raise ValueError("node_values must be binary-digit tokens (e.g., 1, 10, 100, 0)")
        stream_parts.append(bits)
        cursor += len(bits)
        if index < len(node_values) - 1:
            stops.append(cursor)
    return "".join(stream_parts), stops


def _decode_value_stream(*, value_stream: str, stop_addresses: list[int]) -> list[int]:
    starts = [0] + [int(item) for item in list(stop_addresses or [])]
    ends = [int(item) for item in list(stop_addresses or [])] + [len(value_stream)]
    out: list[int] = []
    for left, right in zip(starts, ends):
        segment = value_stream[left:right]
        if segment == "":
            out.append(0)
            continue
        out.append(int(segment))
    return out


def _default_address_map_for_values(node_values: list[int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for index, value in enumerate(list(node_values or []), start=1):
        address = "-".join("1" for _ in range(index))
        out[address] = int(value)
    return out


def validate_samras_structure(structure: SamrasStructure) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = [str(item) for item in list(structure.warnings or [])]
    if _as_text(structure.root_ref) != "0-0-5":
        errors.append("root_ref must be 0-0-5")
    if int(structure.stop_count) != len(list(structure.stop_addresses or [])):
        errors.append("stop_count must equal the number of stop_addresses")
    if int(structure.stop_count) + 1 != len(list(structure.node_values or [])):
        errors.append("decoded_value_count must equal stop_count + 1")
    stop_addresses = [int(item) for item in list(structure.stop_addresses or [])]
    for index, value in enumerate(stop_addresses):
        if index > 0 and value <= stop_addresses[index - 1]:
            errors.append("stop addresses must be strictly increasing")
            break
    compiled_stream, compiled_stops = _compile_value_stream_and_stops([int(item) for item in list(structure.node_values or [])])
    if compiled_stops != stop_addresses:
        errors.append("stop addresses must be cumulative exclusive bit-end positions into value_stream")
    max_stop = stop_addresses[-1] if stop_addresses else 0
    if max_stop > len(compiled_stream):
        errors.append("stop addresses must not exceed total value_stream length")
    if int(structure.address_width_bits) < _bit_width(max(stop_addresses) if stop_addresses else 0):
        errors.append("address_width_bits is insufficient for stop_addresses")
    if int(structure.stop_count_width_bits) < _bit_width(int(structure.stop_count)):
        errors.append("stop_count_width_bits is insufficient for stop_count")
    addresses = _sorted_addresses(dict(structure.address_map or {}))
    if len(addresses) != len(list(structure.node_values or [])):
        warnings.append("address_map size differs from node_values length")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def compile_canonical_samras_bitstring(structure: SamrasStructure) -> str:
    validation = validate_samras_structure(structure)
    if not bool(validation.get("ok")):
        raise ValueError("; ".join(list(validation.get("errors") or [])) or "invalid SAMRAS structure")
    value_stream, stops = _compile_value_stream_and_stops([int(item) for item in list(structure.node_values or [])])
    address_width_bits = int(structure.address_width_bits)
    stop_count_width_bits = int(structure.stop_count_width_bits)
    stop_count = int(structure.stop_count)
    header_a = format(address_width_bits, f"0{_CANONICAL_HEADER_BITS}b")
    header_b = format(stop_count_width_bits, f"0{_CANONICAL_HEADER_BITS}b")
    stop_count_bits = format(stop_count, f"0{stop_count_width_bits}b")
    stop_bits = "".join(format(int(item), f"0{address_width_bits}b") for item in stops)
    return f"{header_a}{header_b}{stop_count_bits}{stop_bits}{value_stream}"


def decode_canonical_samras_bitstring(raw: str, *, root_ref: str = "0-0-5") -> SamrasStructure:
    token = _as_text(raw)
    if not token or _BIN_RE.fullmatch(token) is None:
        raise ValueError("canonical SAMRAS bitstring must contain only 0/1")
    if len(token) < (_CANONICAL_HEADER_BITS * 2):
        raise ValueError("canonical SAMRAS bitstring is shorter than header")
    cursor = 0
    address_width_bits = int(token[cursor : cursor + _CANONICAL_HEADER_BITS], 2)
    cursor += _CANONICAL_HEADER_BITS
    stop_count_width_bits = int(token[cursor : cursor + _CANONICAL_HEADER_BITS], 2)
    cursor += _CANONICAL_HEADER_BITS
    if address_width_bits <= 0:
        raise ValueError("address_width_bits must be positive")
    if stop_count_width_bits <= 0:
        raise ValueError("stop_count_width_bits must be positive")
    if len(token) < cursor + stop_count_width_bits:
        raise ValueError("bitstring truncated before stop_count")
    stop_count = int(token[cursor : cursor + stop_count_width_bits], 2)
    cursor += stop_count_width_bits
    stop_addresses: list[int] = []
    for _ in range(stop_count):
        if len(token) < cursor + address_width_bits:
            raise ValueError("bitstring truncated before stop address table completed")
        stop_addresses.append(int(token[cursor : cursor + address_width_bits], 2))
        cursor += address_width_bits
    value_stream = token[cursor:]
    node_values = _decode_value_stream(value_stream=value_stream, stop_addresses=stop_addresses)
    structure = SamrasStructure(
        root_ref=_as_text(root_ref) or "0-0-5",
        address_width_bits=address_width_bits,
        stop_count_width_bits=stop_count_width_bits,
        stop_count=stop_count,
        stop_addresses=stop_addresses,
        node_values=node_values,
        address_map=_default_address_map_for_values(node_values),
        source_format="canonical_binary",
        canonical_state="canonical",
        warnings=[],
    )
    validation = validate_samras_structure(structure)
    if not bool(validation.get("ok")):
        raise ValueError("; ".join(list(validation.get("errors") or [])) or "invalid canonical SAMRAS structure")
    return structure


def decode_legacy_samras_value(raw: str, *, root_ref: str = "0-0-5") -> SamrasStructure:
    token = _as_text(raw)
    if not token or _NUMERIC_HYPHEN_RE.fullmatch(token) is None:
        raise ValueError("legacy SAMRAS payload must be numeric-hyphen")
    normalized_warnings: list[str] = []
    node_values: list[int] = []
    for item in token.split("-"):
        part = _as_text(item)
        if not part:
            continue
        if all(ch in {"0", "1"} for ch in part):
            node_values.append(int(part))
            continue
        normalized_warnings.append(f"legacy decimal token normalized to binary-digit token: {part}")
        node_values.append(int(format(int(part), "b")))
    if not node_values:
        raise ValueError("legacy SAMRAS payload must contain at least one segment")
    _value_stream, stops = _compile_value_stream_and_stops(node_values)
    address_width_bits = max(1, _bit_width(max(stops) if stops else 0))
    stop_count_width_bits = max(1, _bit_width(len(stops)))
    return SamrasStructure(
        root_ref=_as_text(root_ref) or "0-0-5",
        address_width_bits=address_width_bits,
        stop_count_width_bits=stop_count_width_bits,
        stop_count=len(stops),
        stop_addresses=stops,
        node_values=node_values,
        address_map=_default_address_map_for_values(node_values),
        source_format="legacy_hyphen",
        canonical_state="provisional",
        warnings=["legacy payload ingested; canonical binary should be written on save"] + normalized_warnings,
    )


def decode_samras_structure(raw: str, *, root_ref: str = "0-0-5") -> SamrasStructure:
    token = _as_text(raw)
    if token and _BIN_RE.fullmatch(token):
        return decode_canonical_samras_bitstring(token, root_ref=root_ref)
    return decode_legacy_samras_value(token, root_ref=root_ref)


def build_samras_structure_from_address_map(
    address_map: dict[str, int],
    *,
    root_ref: str = "0-0-5",
    source_format: str = "canonical_binary",
    canonical_state: str = "canonical",
    warnings: list[str] | None = None,
) -> SamrasStructure:
    ordered_addresses = _sorted_addresses(address_map)
    node_values = [int(dict(address_map or {}).get(address) or 0) for address in ordered_addresses]
    _value_stream, stops = _compile_value_stream_and_stops(node_values)
    structure = SamrasStructure(
        root_ref=_as_text(root_ref) or "0-0-5",
        address_width_bits=max(1, _bit_width(max(stops) if stops else 0)),
        stop_count_width_bits=max(1, _bit_width(len(stops))),
        stop_count=len(stops),
        stop_addresses=stops,
        node_values=node_values,
        address_map={address: int(dict(address_map or {}).get(address) or 0) for address in ordered_addresses},
        source_format=_as_text(source_format) or "canonical_binary",
        canonical_state=_as_text(canonical_state) or "canonical",
        warnings=[str(item) for item in list(warnings or [])],
    )
    return structure


def inspect_node_by_address(structure: SamrasStructure, address_id: str) -> dict[str, Any]:
    token = _as_text(address_id)
    if token not in dict(structure.address_map or {}):
        return {"ok": False, "address_id": token, "error": "address not found"}
    return {"ok": True, "address_id": token, "value": int(dict(structure.address_map).get(token) or 0)}


def set_node_value_by_address(structure: SamrasStructure, *, address_id: str, value: int) -> SamrasStructure:
    token = _as_text(address_id)
    if _ADDR_RE.fullmatch(token) is None:
        raise ValueError("address_id must be numeric-hyphen")
    payload = dict(structure.address_map or {})
    if token not in payload:
        raise ValueError(f"address not found: {token}")
    payload[token] = int(value)
    return build_samras_structure_from_address_map(
        payload,
        root_ref=structure.root_ref,
        source_format=structure.source_format,
        canonical_state="canonical",
        warnings=list(structure.warnings or []),
    )


def create_child_address(structure: SamrasStructure, *, parent_address: str, value: int = 0) -> tuple[SamrasStructure, str]:
    parent = _as_text(parent_address)
    if _ADDR_RE.fullmatch(parent) is None:
        raise ValueError("parent_address must be numeric-hyphen")
    payload = dict(structure.address_map or {})
    if parent not in payload:
        raise ValueError(f"parent address not found: {parent}")
    prefix = f"{parent}-"
    children = [
        int(addr[len(prefix) :])
        for addr in payload
        if addr.startswith(prefix) and "-" not in addr[len(prefix) :] and addr[len(prefix) :].isdigit()
    ]
    next_index = max(children) + 1 if children else 1
    child = f"{parent}-{next_index}"
    payload[child] = int(value)
    return (
        build_samras_structure_from_address_map(
            payload,
            root_ref=structure.root_ref,
            source_format=structure.source_format,
            canonical_state="canonical",
            warnings=list(structure.warnings or []),
        ),
        child,
    )


def delete_address(structure: SamrasStructure, *, address_id: str) -> SamrasStructure:
    token = _as_text(address_id)
    payload = dict(structure.address_map or {})
    if token not in payload:
        raise ValueError(f"address not found: {token}")
    to_remove = [addr for addr in payload if addr == token or addr.startswith(f"{token}-")]
    for key in to_remove:
        payload.pop(key, None)
    if not payload:
        raise ValueError("cannot delete all SAMRAS addresses")
    return build_samras_structure_from_address_map(
        payload,
        root_ref=structure.root_ref,
        source_format=structure.source_format,
        canonical_state="canonical",
        warnings=list(structure.warnings or []),
    )


def move_branch(structure: SamrasStructure, *, from_address: str, to_parent_address: str) -> SamrasStructure:
    src = _as_text(from_address)
    dst_parent = _as_text(to_parent_address)
    payload = dict(structure.address_map or {})
    if src not in payload:
        raise ValueError(f"address not found: {src}")
    if dst_parent not in payload:
        raise ValueError(f"target parent not found: {dst_parent}")
    if dst_parent == src or dst_parent.startswith(f"{src}-"):
        raise ValueError("cannot move a branch into itself")
    branch_keys = [addr for addr in payload if addr == src or addr.startswith(f"{src}-")]
    if not branch_keys:
        return structure
    prefix = f"{dst_parent}-"
    children = [
        int(addr[len(prefix) :])
        for addr in payload
        if addr.startswith(prefix) and "-" not in addr[len(prefix) :] and addr[len(prefix) :].isdigit()
    ]
    next_index = max(children) + 1 if children else 1
    new_root = f"{dst_parent}-{next_index}"
    branch_payload = {key: payload.pop(key) for key in branch_keys}
    remapped: dict[str, int] = {}
    for old_key, value in branch_payload.items():
        suffix = old_key[len(src) :]
        remapped[f"{new_root}{suffix}"] = int(value)
    payload.update(remapped)
    return build_samras_structure_from_address_map(
        payload,
        root_ref=structure.root_ref,
        source_format=structure.source_format,
        canonical_state="canonical",
        warnings=list(structure.warnings or []),
    )
