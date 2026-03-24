from __future__ import annotations

from _shared.portal.application.service_tools import build_service_tool_registration

TOOL_ID = "paypal_tenant_actions"
TOOL_TITLE = "PayPal Member Actions"


def get_tool() -> dict[str, object]:
    return build_service_tool_registration(TOOL_ID, TOOL_TITLE)
