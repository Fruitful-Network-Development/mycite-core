"""Helpers shared across the utilities extensions.

The extension modules all need:

  * ``_as_text`` / ``_as_dict`` / ``_as_list`` — defensive coercion of
    payload fields that arrive as ``object`` from JSON / TOML / SQL.
  * ``_mask_secret`` — the secret-redaction helper used in the
    configuration mirrors so plaintext client_secret / smtp_password
    never crosses the surface payload.

This module has no MyCiteV2-side imports — it is intentionally pure so
the extension modules can pull from it without risking a circular load.
"""

from __future__ import annotations

from typing import Any


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _mask_secret(value: object) -> str:
    """Return a redacted form of a secret. Empty input → empty output.

    Keeps the last 4 characters visible for operator verification;
    everything else is replaced with bullets. Strings shorter than 8
    characters are fully masked.
    """
    text = _as_text(value)
    if not text:
        return ""
    if len(text) < 8:
        return "•" * len(text)
    return "•" * (len(text) - 4) + text[-4:]


__all__ = [
    "_as_dict",
    "_as_list",
    "_as_text",
    "_mask_secret",
]
