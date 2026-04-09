from __future__ import annotations

from dataclasses import dataclass

from MyCiteV2.packages.core.datum_refs import normalize_datum_ref, parse_datum_ref


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_attention(value: object, *, field_name: str = "attention") -> str:
    parsed = parse_datum_ref(value, field_name=field_name)
    if not parsed.qualified:
        raise ValueError(f"{field_name} must be a qualified datum_ref")
    return normalize_datum_ref(parsed.raw, write_format="dot", field_name=field_name)


@dataclass(frozen=True)
class AitasContext:
    attention: str = ""
    intention: str = ""

    def __post_init__(self) -> None:
        normalized_attention = ""
        if self.attention:
            normalized_attention = normalize_attention(self.attention, field_name="aitas.attention")
        object.__setattr__(self, "attention", normalized_attention)
        object.__setattr__(self, "intention", _as_text(self.intention).lower())

    def to_dict(self) -> dict[str, str]:
        return {
            "attention": self.attention,
            "intention": self.intention,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> "AitasContext":
        data = payload if isinstance(payload, dict) else {}
        return cls(
            attention=data.get("attention") or "",
            intention=data.get("intention") or "",
        )
