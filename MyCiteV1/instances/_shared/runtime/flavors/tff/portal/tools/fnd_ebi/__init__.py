from __future__ import annotations

from _shared.portal.application.service_tools import build_service_tool_registration

TOOL_ID = "fnd_ebi"
TOOL_TITLE = "FND EBI"
TOOL_ICON = "/portal/static/icons/tools/fnd_ebi.svg"


def get_tool() -> dict[str, object]:
    return build_service_tool_registration(TOOL_ID, TOOL_TITLE)
