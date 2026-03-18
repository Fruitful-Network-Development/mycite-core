from __future__ import annotations

from typing import Any

from .base import as_text


def resolve_lens_payload(*, lens_key: str, understanding: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    token = as_text(lens_key)
    if token == "lens.text.ascii_like.v1":
        constraints = understanding.get("constraints") if isinstance(understanding.get("constraints"), dict) else {}
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
