from __future__ import annotations

from flask import Blueprint, redirect


data_tool_bp = Blueprint("data_tool", __name__)

TOOL_ID = "data_tool"
TOOL_TITLE = "Data Tool"
TOOL_HOME_PATH = "/portal/tools/data_tool/home"
TOOL_BLUEPRINT = data_tool_bp


@data_tool_bp.get("/portal/tools/data_tool/home")
def data_tool_home():
    return redirect("/portal/system", code=302)


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
