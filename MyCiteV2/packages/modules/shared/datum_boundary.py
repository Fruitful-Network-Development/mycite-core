from __future__ import annotations

from MyCiteV2.packages.core.datum_refs import normalize_datum_ref


def normalize_focus_subject(value: object, *, field_name: str) -> str:
    """Normalize focus-subject datum refs to canonical qualified-dot form."""
    return normalize_datum_ref(
        value,
        require_qualified=True,
        write_format="dot",
        field_name=field_name,
    )


__all__ = [
    "normalize_focus_subject",
]
