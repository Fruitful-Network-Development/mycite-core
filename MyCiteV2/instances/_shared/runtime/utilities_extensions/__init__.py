"""Utilities-tab extension dispatch (Phase 12g — full per-extension split).

Phase 12g (initial) extracted the dispatch table + renderer wrappers
out of the legacy ``portal_fnd_csm_runtime.py``. This commit completes
the split: every per-extension builder + helper now lives in its own
module under this package. ``portal_fnd_csm_runtime.py`` no longer
defines any extension code — it imports the builders back for the
legacy ``build_portal_fnd_csm_surface_bundle`` path under the FND-CSM
preservation invariant.

Public surface:

  * ``EXTENSION_RENDERERS`` — dict keyed by extension tool_id mapping
    to a renderer ``(ctx: dict) -> dict``. Keys must match
    ``is_extension=True`` entries in
    ``build_portal_tool_registry_entries()``; the
    ``test_extension_renderer_parity.py`` postcondition pins the
    bijection.
  * ``render_extension(tool_id, ctx)`` — resilient dispatch wrapper
    that returns ``{}`` on unknown tool_id or renderer exception so the
    Utilities surface payload never crashes on a mis-registered
    extension.

Each renderer is a thin adapter inside its own per-extension file. It
extracts the keys it needs from ``ctx`` (grantee dict, domain string,
private_dir, authority_db_file, portal_instance_id) and delegates to
the corresponding builder.
"""

from __future__ import annotations

from typing import Any

from ._shared import _as_text
from .analytics import _build_analytics_extension_payload, _render_ext_analytics
from .connect import _build_connect_extension_payload, _render_ext_connect
from .email import _build_email_extension_payload, _render_ext_aws_email
from .grantee_profile import (
    _build_grantee_profile_form_fields,
    _render_ext_grantee_profile,
)
from .newsletter import _build_newsletter_extension_payload, _render_ext_newsletter
from .paypal import (
    _build_paypal_extension_payload,
    _hydrate_paypal_from_sidecar,
    _render_ext_paypal,
)

EXTENSION_RENDERERS: dict[str, Any] = {
    "ext_aws_email": _render_ext_aws_email,
    "ext_analytics": _render_ext_analytics,
    "ext_newsletter": _render_ext_newsletter,
    "ext_paypal": _render_ext_paypal,
    "ext_connect": _render_ext_connect,
    "ext_grantee_profile": _render_ext_grantee_profile,
}


def render_extension(tool_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Render an extension by tool_id with the given context dict.

    Returns ``{}`` for unknown tool_ids rather than raising; keeps the
    utilities surface bundle resilient when an extension is mis-
    registered. Required context keys vary by extension; see
    ``_render_ext_*`` for specifics.
    """
    renderer = EXTENSION_RENDERERS.get(_as_text(tool_id))
    if renderer is None:
        return {}
    try:
        return renderer(ctx)
    except Exception:
        return {}


__all__ = [
    "EXTENSION_RENDERERS",
    "render_extension",
    # Builders re-exported for the legacy build_portal_fnd_csm_surface_bundle
    # path in portal_fnd_csm_runtime.py. New callers should import from the
    # per-extension files directly.
    "_build_analytics_extension_payload",
    "_build_connect_extension_payload",
    "_build_email_extension_payload",
    "_build_grantee_profile_form_fields",
    "_build_newsletter_extension_payload",
    "_build_paypal_extension_payload",
    "_hydrate_paypal_from_sidecar",
]
