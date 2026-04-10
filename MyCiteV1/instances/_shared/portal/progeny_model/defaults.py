from __future__ import annotations

from typing import Any

LEGAL_ENTITY_BASELINE_CONFIG: dict[str, Any] = {
    "schema": "mycite.progeny.config.v1",
    "types": {
        "admin": {
            "required_fields": ["display.name", "contact.email"],
            "inherits_from_alias": ["display.name", "contact.email"],
            "local_fields": ["role_scope"],
        },
        "member": {
            "required_fields": ["display.name"],
            "inherits_from_alias": ["display.name", "contact.email"],
            "local_fields": ["status.state", "participation_flags"],
        },
        "user": {
            "required_fields": ["display.name"],
            "inherits_from_alias": ["display.name", "contact.email"],
            "local_fields": ["preferences"],
        },
    },
}
