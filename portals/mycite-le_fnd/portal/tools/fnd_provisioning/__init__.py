from __future__ import annotations

from flask import Blueprint, render_template

fnd_provisioning_bp = Blueprint("fnd_provisioning", __name__)

TOOL_ID = "fnd_provisioning"
TOOL_TITLE = "FND Provisioning"
TOOL_HOME_PATH = "/portal/tools/fnd_provisioning/home"
TOOL_BLUEPRINT = fnd_provisioning_bp


@fnd_provisioning_bp.get("/portal/tools/fnd_provisioning/home")
def fnd_provisioning_home():
    return render_template("tools/fnd_provisioning_home.html")



def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
