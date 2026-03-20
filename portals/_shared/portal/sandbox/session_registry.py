"""
Shared registration of ``ToolSandboxSessionManager`` on the Flask app.

Flavors and ``register_data_routes`` should use :func:`get_tool_sandbox_session_manager`
instead of duplicating config keys, so tools (e.g. AGRO) and data API routes share one
in-process session registry per app instance.
"""

from __future__ import annotations

from typing import Any

from _shared.portal.sandbox.tool_sandbox_session import ToolSandboxSessionManager

TOOL_SANDBOX_MANAGER_APP_KEY = "MYCITE_TOOL_SANDBOX_SESSION_MANAGER"


def get_tool_sandbox_session_manager(app: Any) -> ToolSandboxSessionManager:
    """
    Return the singleton ``ToolSandboxSessionManager`` stored on ``app.config``.

    ``app`` must be a Flask application (or any object with a ``config`` mapping).
    """
    if app is None:
        raise TypeError("app is required")
    cfg = getattr(app, "config", None)
    if cfg is None:
        raise TypeError("app.config is required")
    existing = cfg.get(TOOL_SANDBOX_MANAGER_APP_KEY)
    if existing is None:
        existing = ToolSandboxSessionManager()
        cfg[TOOL_SANDBOX_MANAGER_APP_KEY] = existing
    return existing  # type: ignore[return-value]


__all__ = ["TOOL_SANDBOX_MANAGER_APP_KEY", "get_tool_sandbox_session_manager"]
