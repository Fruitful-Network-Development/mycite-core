from __future__ import annotations

from flask import Blueprint, render_template
from _shared.portal.application.service_tools import build_service_tool_meta

operations_bp = Blueprint("operations", __name__)

TOOL_ID = "operations"
TOOL_TITLE = "Operations"
TOOL_HOME_PATH = "/portal/tools/operations/home"
TOOL_BLUEPRINT = operations_bp


@operations_bp.get("/portal/tools/operations/home")
def operations_home():
    return render_template("tools/operations_home.html")



def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
        **build_service_tool_meta(TOOL_ID),
    }
