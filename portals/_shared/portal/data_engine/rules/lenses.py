from __future__ import annotations

from typing import Any

from .base import as_text


def resolve_lens_payload(*, lens_key: str, understanding: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    token = as_text(lens_key)
    constraints = understanding.get("constraints") if isinstance(understanding.get("constraints"), dict) else {}
    if token == "lens.collection.ordered_members.v1":
        members = constraints.get("ordered_member_refs")
        if not isinstance(members, list):
            members = []
        return {
            "lens_key": token,
            "render_mode": "ordered_member_list",
            "renderable": bool(members),
            "ordered_member_refs": list(members),
            "member_count": int(constraints.get("member_count") or len(members)),
            "ordinal_semantics": constraints.get("ordinal_semantics"),
            "warnings": [],
        }
    if token == "lens.selectorate.marker.v1":
        return {
            "lens_key": token,
            "render_mode": "selectorate_transform",
            "renderable": True,
            "parent_collection_id": constraints.get("parent_collection_id"),
            "ordinal_domain_max": constraints.get("ordinal_domain_max"),
            "warnings": [],
        }
    if token == "lens.field.abstraction.v1":
        return {
            "lens_key": token,
            "render_mode": "field_column",
            "renderable": True,
            "parent_selectorate_id": constraints.get("parent_selectorate_id"),
            "ordinal_domain_min": constraints.get("ordinal_domain_min"),
            "ordinal_domain_max": constraints.get("ordinal_domain_max"),
            "collection_member_signature": constraints.get("collection_member_signature"),
            "warnings": [],
        }
    if token == "lens.table_like.row_tuple.v1":
        pairs = constraints.get("per_field_pairs")
        if not isinstance(pairs, list):
            pairs = []
        return {
            "lens_key": token,
            "render_mode": "row_tuple",
            "renderable": bool(pairs),
            "per_field_pairs": list(pairs),
            "field_count": int(constraints.get("field_count") or len(pairs)),
            "resolved_collection_member_signature": constraints.get("resolved_collection_member_signature"),
            "warnings": [],
        }
    if token == "lens.text.ascii_like.v1":
        magnitude = as_text(row.get("magnitude"))
        if not magnitude or any(ch not in {"0", "1"} for ch in magnitude):
            return {
                "lens_key": token,
                "render_mode": "text_ascii_like",
                "renderable": False,
                "warnings": ["isolate magnitude is not canonical binary"],
            }
        try:
            number = int(magnitude, 2)
        except Exception:
            number = 0
        text = ""
        warnings: list[str] = []
        while number > 0:
            byte = number & 0xFF
            text = chr(byte) + text
            number >>= 8
        if not text:
            text = "\x00"
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in text):
            warnings.append("decoded characters include non-printable ascii range")
        return {
            "lens_key": token,
            "render_mode": "text_ascii_like",
            "renderable": True,
            "decoded_text": text,
            "namespace_cardinality": constraints.get("namespace_cardinality"),
            "sequence_length": constraints.get("sequence_length"),
            "warnings": warnings,
        }
    return {
        "lens_key": token or "lens.none.v1",
        "render_mode": "raw",
        "renderable": False,
        "warnings": [],
    }
