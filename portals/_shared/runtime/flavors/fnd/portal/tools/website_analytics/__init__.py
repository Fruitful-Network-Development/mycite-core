from __future__ import annotations

from flask import Blueprint, render_template

website_analytics_bp = Blueprint("website_analytics", __name__)

TOOL_ID = "website_analytics"
TOOL_TITLE = "Website Analytics"
TOOL_HOME_PATH = "/portal/tools/website_analytics/home"
TOOL_BLUEPRINT = website_analytics_bp


@website_analytics_bp.get("/portal/tools/website_analytics/home")
def website_analytics_home():
    return render_template("tools/website_analytics_home.html")


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
