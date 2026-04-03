from __future__ import annotations

from typing import Any, TypedDict


class MediationResult(TypedDict):
    ok: bool
    standard_id: str
    reference: str
    magnitude: str
    value: Any
    display: str
    warnings: list[str]
    errors: list[str]


def result(
    *,
    standard_id: str,
    reference: str,
    magnitude: str,
    value: Any,
    display: str,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> MediationResult:
    warnings_out = list(warnings or [])
    errors_out = list(errors or [])
    return {
        "ok": not errors_out,
        "standard_id": str(standard_id or "").strip().lower(),
        "reference": str(reference or "").strip(),
        "magnitude": str(magnitude or "").strip(),
        "value": value,
        "display": str(display or ""),
        "warnings": warnings_out,
        "errors": errors_out,
    }
