"""Shared helpers for the FND SQL adapters.

The remaining FND-tenant SQL adapters (fnd_paypal, fnd_email_deliverability)
all need the same defensive type coercion + canonical-name token
utilities. Keeping them here prevents drift. The retired analytics
summary adapter used to share these helpers too.

This module has no MyCiteV2-side imports — pure stdlib so any adapter
can pull from it without risking a circular load.
"""

from __future__ import annotations


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _domain_token(domain: str) -> str:
    return _as_text(domain).lower().replace(".", "_").replace("-", "_")


def _rate(numer: int, denom: int) -> float:
    return float(numer) / float(denom) if denom > 0 else 0.0


__all__ = ["_as_text", "_as_int", "_domain_token", "_rate"]
