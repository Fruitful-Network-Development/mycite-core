"""Utilities-tab extension payload builders.

Phase 12g split every per-extension builder + helper into its own module
under this package. The operator-facing portal extension *surface* (the
``EXTENSION_RENDERERS`` dispatch table + the ``_render_ext_*`` shell
renderers) was dissolved in the portal-tool-overlay-restructure work; the
``_build_*`` payload builders re-exported below survive because the public
``/__fnd/*`` admin + ingest routes (and their tests) still call them.

New callers should import the builder they need from the per-extension file
directly; the re-exports here are kept for the legacy import path.
"""

from __future__ import annotations

from .analytics import _build_analytics_extension_payload
from .connect import _build_connect_extension_payload
from .email import _build_email_extension_payload
from .grantee_profile import _build_grantee_profile_form_fields
from .newsletter import _build_newsletter_extension_payload
from .paypal import _build_paypal_extension_payload

__all__ = [
    "_build_analytics_extension_payload",
    "_build_connect_extension_payload",
    "_build_email_extension_payload",
    "_build_grantee_profile_form_fields",
    "_build_newsletter_extension_payload",
    "_build_paypal_extension_payload",
]
