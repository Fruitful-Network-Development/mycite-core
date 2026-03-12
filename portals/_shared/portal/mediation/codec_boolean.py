from __future__ import annotations

from typing import Any

from .types import MediationResult, result

_FALSEY = {"", "0", "false", "no", "off", "n"}
_TRUTHY = {"1", "true", "yes", "on", "y"}


def _bool_from_text(token: str) -> bool:
    lowered = str(token or "").strip().lower()
    if lowered in _FALSEY:
        return False
    if lowered in _TRUTHY:
        return True
    try:
        return int(lowered) != 0
    except Exception:
        return bool(lowered)


def decode(*, standard_id: str, reference: str, magnitude: str, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    value = _bool_from_text(magnitude)
    return result(
        standard_id=standard_id,
        reference=reference,
        magnitude=("1" if value else "0"),
        value=value,
        display=("true" if value else "false"),
    )


def encode(*, standard_id: str, value: Any, context: dict[str, Any] | None = None) -> MediationResult:
    _ = context
    bool_value = value if isinstance(value, bool) else _bool_from_text(str(value or ""))
    token = "1" if bool_value else "0"
    return result(
        standard_id=standard_id,
        reference="",
        magnitude=token,
        value=bool_value,
        display=("true" if bool_value else "false"),
    )
