from __future__ import annotations

from flask import Blueprint, render_template

legacy_admin_bp = Blueprint("legacy_admin", __name__)

TOOL_ID = "legacy_admin"
TOOL_TITLE = "Legacy Admin"
TOOL_HOME_PATH = "/portal/tools/legacy_admin/home"
TOOL_BLUEPRINT = legacy_admin_bp


@legacy_admin_bp.get("/portal/tools/legacy_admin/home")
def legacy_admin_home():
    return render_template("tools/legacy_admin_home.html")



def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
