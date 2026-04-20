from __future__ import annotations

from typing import Any, Iterable


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def reject_forbidden_keys(
    payload: Any,
    *,
    forbidden_keys: Iterable[str],
    field_name: str,
    violation_suffix: str = "",
) -> None:
    """Recursively reject forbidden keys in nested JSON-like payloads."""
    forbidden = {str(token).lower() for token in forbidden_keys}

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                token = _as_text(key)
                if not token:
                    raise ValueError(f"{path} keys must be non-empty strings")
                if token.lower() in forbidden:
                    suffix = f" {violation_suffix.strip()}" if violation_suffix.strip() else ""
                    raise ValueError(f"{path}.{token} is forbidden{suffix}")
                _walk(item, f"{path}.{token}")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, f"{path}[{index}]")

    _walk(payload, field_name)


__all__ = [
    "reject_forbidden_keys",
]
