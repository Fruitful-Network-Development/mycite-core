"""Helpers shared across the utilities extensions.

The five extension modules (``email``, ``analytics``, ``newsletter``,
``paypal``, ``grantee_profile``) all need:

  * ``_as_text`` / ``_as_dict`` / ``_as_list`` — defensive coercion of
    payload fields that arrive as ``object`` from JSON / TOML / SQL.
  * ``_grantee_edit_link`` — the ``Edit in Grantee Profile`` metadata
    block every operational extension surfaces in its ``configuration``
    section (Phase 10 reflective/operational split).
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


def _grantee_edit_link(focus_field: str) -> dict[str, str]:
    """Build the ``{label, href, focus_field}`` edit-link.

    The href points at the Utilities tool-exposure surface with a query
    parameter telling the client to scroll the grantee form to a
    particular sub-config. Phase 10 emits this as plain metadata; the
    client-side rendering interprets ``focus_field`` to anchor-scroll.
    """
    return {
        "label": "Edit in Grantee Profile",
        "href": f"/portal/utilities/tool-exposure?utilities_extension=ext_grantee_profile&focus_field={focus_field}",
        "focus_field": focus_field,
    }


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
    "_grantee_edit_link",
    "_mask_secret",
]
