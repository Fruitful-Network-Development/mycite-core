"""Utilities-tab extension helpers.

Phase 12g split every per-extension builder + helper into its own module
under this package. The operator-facing portal extension *surface* (the
``EXTENSION_RENDERERS`` dispatch table, the ``_render_ext_*`` shell
renderers, and the ``_build_*_extension_payload`` payload builders) was
dissolved in the portal-tool-overlay-restructure work. The live ``/__fnd/*``
admin + ingest route logic moved to the portal host (``portal_host/app.py``)
and the per-extension modules that retain route helpers are imported from
directly.

``_build_grantee_profile_form_fields`` is the one builder re-exported here
because callers still import it from the package root.
"""

from __future__ import annotations

from .grantee_profile import _build_grantee_profile_form_fields

__all__ = [
    "_build_grantee_profile_form_fields",
]
