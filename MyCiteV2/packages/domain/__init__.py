"""Pure domain helpers (no project imports → safe to import anywhere)."""

from .contact_entry import (
    CONTACT_ENTRY_FIELDS,
    blank_contact_entry,
    canonical_contact_entry,
    split_legacy_name,
)

__all__ = [
    "CONTACT_ENTRY_FIELDS",
    "blank_contact_entry",
    "canonical_contact_entry",
    "split_legacy_name",
]
