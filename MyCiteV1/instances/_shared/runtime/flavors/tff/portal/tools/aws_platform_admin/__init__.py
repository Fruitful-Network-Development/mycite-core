from __future__ import annotations

from _shared.portal.application.service_tools import build_service_tool_registration

TOOL_ID = "aws_platform_admin"
TOOL_TITLE = "AWS-CMS"
TOOL_ICON = "/portal/api/tools/icons/aws-csm/aws.svg"


def get_tool() -> dict[str, object]:
    return build_service_tool_registration(TOOL_ID, TOOL_TITLE)
