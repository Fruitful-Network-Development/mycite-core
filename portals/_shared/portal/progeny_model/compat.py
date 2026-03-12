from __future__ import annotations

LEGACY_TYPE_MAP = {
    "tenant": "member",
    "board_member": "member",
}

LEGAL_ENTITY_BASE_TYPES = ("poc", "member", "user")


def canonical_progeny_type(value: str) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return "unknown"
    return LEGACY_TYPE_MAP.get(token, token)


def is_legacy_progeny_type(value: str) -> bool:
    token = str(value or "").strip().lower()
    return token in LEGACY_TYPE_MAP
