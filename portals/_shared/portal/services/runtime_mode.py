from __future__ import annotations

import os
from typing import Any

from flask import abort, jsonify, request


_SAFE_DATA_POST_EXACT = {
    "/portal/api/data/system/selection_context",
    "/portal/api/data/mss/compile",
    "/portal/api/data/rules/reference_filter",
    "/portal/api/data/rules/validate_create",
    "/portal/api/data/rules/lens",
}

_SAFE_DATA_POST_MARKERS = (
    "/preview",
    "/compile",
    "/decode",
    "/inspect",
    "/trace",
    "/resolve",
    "/resolve_tokens",
    "/fetch",
    "/plan_materialization",
    "/view_model",
)


def env_flag(name: str, default: bool = False) -> bool:
    token = str(os.environ.get(name) or "").strip().lower()
    if not token:
        return default
    return token in {"1", "true", "yes", "on"}


def build_session_presentation(*, auth_mode: str, active_portal_username: str, read_only: bool) -> dict[str, Any]:
    mode = str(auth_mode or "").strip().lower()
    username = str(active_portal_username or "").strip()
    session_actions_enabled = mode not in {"none", "off", "local", "local_demo"}

    if not username and not session_actions_enabled:
        username = "local-demo"

    status_parts: list[str] = []
    if not session_actions_enabled:
        status_parts.append("local-only demo session")
    if read_only:
        status_parts.append("read-only")

    return {
        "active_portal_username": username,
        "session_actions_enabled": session_actions_enabled,
        "session_status_label": " | ".join(status_parts),
        "portal_read_only": bool(read_only),
    }


def _data_post_is_safe(path: str) -> bool:
    if path in _SAFE_DATA_POST_EXACT:
        return True
    return any(marker in path for marker in _SAFE_DATA_POST_MARKERS)


def _should_block_read_only_request(path: str, method: str) -> bool:
    token = str(path or "").strip()
    verb = str(method or "").strip().upper()
    if verb in {"GET", "HEAD", "OPTIONS"}:
        return False
    if verb in {"PUT", "PATCH", "DELETE"}:
        return True
    if verb != "POST":
        return True

    if token == "/portal/api/contracts/mss/preview":
        return False

    if token.startswith("/portal/api/data/"):
        return not _data_post_is_safe(token)

    if token.startswith("/portal/api/") or token.startswith("/api/") or token.startswith("/portal/"):
        return True
    return False


def install_read_only_guard(app, *, enabled: bool, label: str = "local-only demo") -> None:
    if not enabled:
        return

    @app.before_request
    def _runtime_read_only_guard():
        if not _should_block_read_only_request(request.path, request.method):
            return None
        message = f"This portal is running in {label} read-only mode."
        if request.path.startswith("/portal/api/") or request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": message, "mode": "read_only_demo"}), 403
        abort(403, description=message)
