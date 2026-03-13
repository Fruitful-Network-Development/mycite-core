from __future__ import annotations

from flask import Blueprint, render_template

aws_platform_admin_bp = Blueprint("aws_platform_admin", __name__)

TOOL_ID = "aws_platform_admin"
TOOL_TITLE = "AWS Platform/Admin"
TOOL_HOME_PATH = "/portal/tools/aws_platform_admin/home"
TOOL_BLUEPRINT = aws_platform_admin_bp


@aws_platform_admin_bp.get("/portal/tools/aws_platform_admin/home")
def aws_platform_admin_home():
    return render_template("tools/aws_platform_admin_home.html")


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
