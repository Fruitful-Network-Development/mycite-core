from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from _shared.portal.samras import (
    InvalidSamrasStructure,
    SamrasStructure,
    add_child,
    decode_canonical_bitstream,
    decode_legacy_hyphen_payload,
    decode_structure,
    encode_canonical_structure_from_addresses,
    move_branch as move_branch_mutation,
    remove_branch,
    set_child_count,
    validate_structure,
)

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
    """Legacy slot-array descriptor shim kept for compatibility-only metadata paths."""
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
        errors.append("descriptor is not bound to compatibility SAMRAS shape root 0-0-6")
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
    out["structure_payload"] = _as_text(out.get("canonical_magnitude")) or encode_structure_payload(descriptor)
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


def validate_samras_structure(structure: SamrasStructure) -> dict[str, Any]:
    return validate_structure(structure).to_dict()


def compile_canonical_samras_bitstring(structure: SamrasStructure) -> str:
    if not bool(validate_samras_structure(structure).get("ok")):
        raise InvalidSamrasStructure("; ".join(validate_samras_structure(structure).get("errors") or []))
    return encode_canonical_structure_from_addresses(list(structure.addresses), root_ref=structure.root_ref, warnings=structure.warnings).bitstream


def decode_canonical_samras_bitstring(raw: str, *, root_ref: str = "0-0-5") -> SamrasStructure:
    return decode_canonical_bitstream(raw, root_ref=root_ref)


def decode_legacy_samras_value(raw: str, *, root_ref: str = "0-0-5") -> SamrasStructure:
    return decode_legacy_hyphen_payload(raw, root_ref=root_ref)


def decode_samras_structure(raw: str, *, root_ref: str = "0-0-5") -> SamrasStructure:
    return decode_structure(raw, root_ref=root_ref)


def build_samras_structure_from_address_map(
    address_map: dict[str, int],
    *,
    root_ref: str = "0-0-5",
    source_format: str = "canonical",
    canonical_state: str = "canonical",
    warnings: list[str] | None = None,
) -> SamrasStructure:
    addresses = sorted(
        [str(key) for key in dict(address_map or {}).keys() if _NUMERIC_HYPHEN_RE.fullmatch(str(key))],
        key=lambda token: tuple(int(part) for part in token.split("-")),
    )
    structure = encode_canonical_structure_from_addresses(addresses, root_ref=root_ref, warnings=warnings or [])
    if _as_text(source_format):
        structure = SamrasStructure(
            root_ref=structure.root_ref,
            bitstream=structure.bitstream,
            address_width_bits=structure.address_width_bits,
            stop_count_width_bits=structure.stop_count_width_bits,
            stop_count=structure.stop_count,
            stop_addresses=structure.stop_addresses,
            value_tokens=structure.value_tokens,
            values=structure.values,
            addresses=structure.addresses,
            source_format=_as_text(source_format),
            canonical_state=_as_text(canonical_state) or structure.canonical_state,
            warnings=tuple(str(item) for item in list(warnings or structure.warnings)),
        )
    return structure


def inspect_node_by_address(structure: SamrasStructure, address_id: str) -> dict[str, Any]:
    token = _as_text(address_id)
    if token not in structure.address_map:
        return {"ok": False, "address_id": token, "error": "address not found"}
    return {
        "ok": True,
        "address_id": token,
        "value": int(structure.address_map.get(token) or 0),
        "child_count": int(structure.address_map.get(token) or 0),
    }


def set_node_value_by_address(structure: SamrasStructure, *, address_id: str, value: int) -> SamrasStructure:
    mutation = set_child_count(structure, address_id=_as_text(address_id), child_count=int(value))
    return mutation.structure


def create_child_address(structure: SamrasStructure, *, parent_address: str, value: int = 0) -> tuple[SamrasStructure, str]:
    mutation = add_child(structure, parent_address=_as_text(parent_address))
    created = mutation.created_addresses[0] if mutation.created_addresses else ""
    if created and int(value) > 0:
        mutation = set_child_count(mutation.structure, address_id=created, child_count=int(value))
        created = created
    return mutation.structure, created


def delete_address(structure: SamrasStructure, *, address_id: str) -> SamrasStructure:
    return remove_branch(structure, address_id=_as_text(address_id)).structure


def move_branch(structure: SamrasStructure, *, from_address: str, to_parent_address: str) -> SamrasStructure:
    return move_branch_mutation(structure, from_address=_as_text(from_address), to_parent_address=_as_text(to_parent_address)).structure

