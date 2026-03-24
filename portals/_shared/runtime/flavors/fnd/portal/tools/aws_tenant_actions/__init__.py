from __future__ import annotations

from flask import Blueprint, render_template
from _shared.portal.application.service_tools import build_service_tool_meta

aws_tenant_actions_bp = Blueprint("aws_tenant_actions", __name__)

TOOL_ID = "aws_tenant_actions"
TOOL_TITLE = "AWS Member Actions"
TOOL_HOME_PATH = "/portal/tools/aws_tenant_actions/home"
TOOL_BLUEPRINT = aws_tenant_actions_bp


@aws_tenant_actions_bp.get("/portal/tools/aws_tenant_actions/home")
def aws_tenant_actions_home():
    return render_template("tools/aws_tenant_actions_home.html")


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
        **build_service_tool_meta(TOOL_ID),
    }
