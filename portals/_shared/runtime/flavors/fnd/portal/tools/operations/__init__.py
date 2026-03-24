from __future__ import annotations

from _shared.portal.application.service_tools import build_service_tool_registration

TOOL_ID = "operations"
TOOL_TITLE = "Operations"


def get_tool() -> dict[str, object]:
    return build_service_tool_registration(TOOL_ID, TOOL_TITLE)
