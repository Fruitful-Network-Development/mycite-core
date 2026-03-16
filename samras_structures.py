# portals/_shared/portal/data_engine/samras_structures.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from typing import Iterable

_NUMERIC_HYPHEN_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")


class SamrasRole(str, Enum):
    DEFINER = "definer"   # row that defines the structure payload under 0-0-6
    SPACE = "space"       # referencable constraint-space / declaration
    FIELD = "field"       # substantive field that may appear in tuple-style rows
    VALUE = "value"       # concrete row value encoded under the field


@dataclass(frozen=True)
class SamrasDescriptor:
    shape_root: str                    # normally "0-0-6"
    role: SamrasRole
    structure_encoding: str           # e.g. "samras.slot_array.v0"
    structure_slots: tuple[int, ...]  # provisional structure payload, zero allowed
    structure_digest: str             # stable digest for reuse / binding
    value_kind: str                   # e.g. "address_id", "msn_id", "txa_id"
    source_ref: str                   # datum that defined the structure payload

    @property
    def active_slot_indexes(self) -> tuple[int, ...]:
        return tuple(i for i, value in enumerate(self.structure_slots) if value > 0)

    def to_constraint_payload(self) -> dict:
        return {
            "constraint_family": "samras",
            "shape_root": self.shape_root,
            "role": self.role.value,
            "structure_encoding": self.structure_encoding,
            "structure_slots": list(self.structure_slots),
            "active_slot_indexes": list(self.active_slot_indexes),
            "structure_digest": self.structure_digest,
            "value_kind": self.value_kind,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class SamrasRow:
    address_id: str
    title: str

    def validate(self) -> None:
        if not self.address_id or not _NUMERIC_HYPHEN_RE.fullmatch(self.address_id):
            raise ValueError("address_id must be numeric-hyphen")
        if not self.title or not str(self.title).strip():
            raise ValueError("title is required")


def _stable_digest(parts: Iterable[int]) -> str:
    raw = ",".join(str(int(x)) for x in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _parse_int_tokens(raw: str) -> tuple[int, ...]:
    token = str(raw or "").strip()
    if not token:
        raise ValueError("empty SAMRAS payload")
    if not _NUMERIC_HYPHEN_RE.fullmatch(token):
        raise ValueError("SAMRAS payload must be numeric-hyphen")
    out = tuple(int(part) for part in token.split("-"))
    if any(value < 0 for value in out):
        raise ValueError("SAMRAS payload may not contain negative integers")
    return out


# --------------------------------------------------------------------
# Structure payload encoding / decoding
# --------------------------------------------------------------------

def decode_structure_payload(
    raw: str,
    *,
    shape_root: str = "0-0-6",
    role: SamrasRole = SamrasRole.DEFINER,
    value_kind: str = "address_id",
    source_ref: str = "",
) -> SamrasDescriptor:
    """
    Decode the provisional SAMRAS structure magnitude.
    This does NOT assume the payload is already a legal anthology-native form.
    It only normalizes the provisional slot-array representation.
    """
    slots = _parse_int_tokens(raw)

    # Provisional hardening:
    # - zeros are allowed as reserved / inactive slots
    # - non-zero integers are preserved as-is
    # - do not interpret these yet as direct address digits or direct radices
    digest = _stable_digest(slots)

    return SamrasDescriptor(
        shape_root=shape_root,
        role=role,
        structure_encoding="samras.slot_array.v0",
        structure_slots=slots,
        structure_digest=digest,
        value_kind=value_kind,
        source_ref=source_ref,
    )


def encode_structure_payload(descriptor: SamrasDescriptor) -> str:
    return "-".join(str(int(x)) for x in descriptor.structure_slots)


# --------------------------------------------------------------------
# Node value encoding / decoding
# --------------------------------------------------------------------

def decode_node_value(raw: str) -> tuple[int, ...]:
    """
    Decode a SAMRAS node value such as:
        3-2-3-17-77-1-6-4-1
    """
    return _parse_int_tokens(raw)


def encode_node_value(parts: Iterable[int]) -> str:
    parts = tuple(int(x) for x in parts)
    if not parts:
        raise ValueError("SAMRAS node value must contain at least one segment")
    if any(value < 0 for value in parts):
        raise ValueError("SAMRAS node value may not contain negative integers")
    return "-".join(str(value) for value in parts)


# --------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------

def validate_node_value(parts: tuple[int, ...], descriptor: SamrasDescriptor) -> dict:
    """
    Provisional validation only.
    Current rule:
      1. value must be numeric-hyphen and non-negative
      2. descriptor must be SAMRAS family
      3. optional role/value_kind gating
      4. future per-segment structure validation hooks live here
    """
    errors: list[str] = []

    if not parts:
        errors.append("empty SAMRAS node value")

    if descriptor.shape_root != "0-0-6":
        errors.append("descriptor is not bound to canonical SAMRAS shape root 0-0-6")

    if descriptor.role not in {SamrasRole.FIELD, SamrasRole.VALUE, SamrasRole.SPACE}:
        errors.append("descriptor role is not usable for node-value validation")

    # Important:
    # The provisional structure slot array is NOT yet treated as direct radix-per-segment.
    # Your example payload contains long zero runs and later non-zero islands, so the engine
    # should first normalize semantics before using it as strict per-depth radix validation.
    #
    # Future hardening hook:
    # errors.extend(_validate_against_normalized_segment_policy(parts, descriptor))

    return {
        "ok": not errors,
        "errors": errors,
        "normalized": encode_node_value(parts) if not errors else "",
        "descriptor_digest": descriptor.structure_digest,
        "value_kind": descriptor.value_kind,
    }


# --------------------------------------------------------------------
# Anthology / SAMRAS row helpers
# --------------------------------------------------------------------

def ensure_samras_row(rows_by_address: dict[str, list[str]], *, address_id: str, title: str) -> dict:
    """
    Enforce SAMRAS row contract from the page spec:
      - address_id required, numeric-hyphen
      - title required
      - idempotent on address_id
    """
    row = SamrasRow(address_id=address_id, title=title)
    row.validate()

    existing = rows_by_address.get(row.address_id)
    if existing is None:
        rows_by_address[row.address_id] = [row.title]
        return {"created": True, "updated": False, "row": {row.address_id: [row.title]}}

    if list(existing) != [row.title]:
        rows_by_address[row.address_id] = [row.title]
        return {"created": False, "updated": True, "row": {row.address_id: [row.title]}}

    return {"created": False, "updated": False, "row": {row.address_id: [row.title]}}


# --------------------------------------------------------------------
# Chain-role derivation
# --------------------------------------------------------------------

def derive_role_from_chain(chain: list[dict]) -> SamrasRole:
    """
    Conservative role derivation.
    Do not overfit to layer numbers alone.
    """
    if not chain:
        raise ValueError("cannot derive SAMRAS role from empty chain")

    top = chain[0]
    magnitude = str(top.get("magnitude") or "").strip()

    # This is intentionally conservative.
    # Replace with explicit role metadata once the SAMRAS compiler is wired in.
    if magnitude == "":
        return SamrasRole.SPACE
    return SamrasRole.VALUE