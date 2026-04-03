from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArchetypeDefinition:
    archetype_key: str
    family: str
    display_name: str
    chain_pattern: list[str]
    constraint_expectation: dict[str, Any]
    lens_key: str
    help_text: str = ""
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype_key": self.archetype_key,
            "family": self.family,
            "display_name": self.display_name,
            "chain_pattern": list(self.chain_pattern),
            "constraint_expectation": dict(self.constraint_expectation),
            "lens_key": self.lens_key,
            "help_text": self.help_text,
            "notes": list(self.notes or []),
        }


_ARCHETYPE_DEFINITIONS: dict[str, ArchetypeDefinition] = {
    "ascii_babel_64": ArchetypeDefinition(
        archetype_key="ascii_babel_64",
        family="ascii",
        display_name="ASCII Babel 64",
        chain_pattern=["ascii", "babel"],
        constraint_expectation={"field_length": 64, "alphabet_cardinality": 256},
        lens_key="ascii.string.babel_64",
        help_text="Recognizes ASCII-babel-style abstractions with 64-length field and 256-cardinality alphabet.",
        notes=[
            "Recognition is derived from abstraction chain + compiled constraints.",
            "MSS/closure data is supporting evidence, not sole matcher.",
        ],
    )
}


def list_archetype_definitions() -> list[ArchetypeDefinition]:
    return [value for _, value in sorted(_ARCHETYPE_DEFINITIONS.items(), key=lambda item: item[0])]


def list_archetype_definition_dicts() -> list[dict[str, Any]]:
    return [item.to_dict() for item in list_archetype_definitions()]


def get_archetype_definition(archetype_key: str) -> ArchetypeDefinition | None:
    token = str(archetype_key or "").strip()
    if not token:
        return None
    return _ARCHETYPE_DEFINITIONS.get(token)
