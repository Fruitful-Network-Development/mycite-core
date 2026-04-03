from __future__ import annotations

from typing import Any


def resolve_inherited_fields(
    *,
    alias_payload: dict[str, Any] | None,
    progeny_payload: dict[str, Any] | None,
    inheritance_rules: dict[str, Any] | None,
) -> dict[str, Any]:
    alias_payload = dict(alias_payload or {})
    progeny_payload = dict(progeny_payload or {})
    rules = dict(inheritance_rules or {})

    alias_fields = alias_payload.get("fields") if isinstance(alias_payload.get("fields"), dict) else {}
    progeny_fields = progeny_payload.get("fields") if isinstance(progeny_payload.get("fields"), dict) else {}

    resolved = dict(alias_fields)
    alias_overrides = bool(rules.get("alias_profile_overrides", True))
    if alias_overrides:
        merged = dict(progeny_fields)
        merged.update(alias_fields)
        resolved = merged
    else:
        resolved.update(progeny_fields)

    return {
        "resolved_fields": resolved,
        "alias_fields": alias_fields,
        "progeny_fields": progeny_fields,
        "rules": rules,
    }
