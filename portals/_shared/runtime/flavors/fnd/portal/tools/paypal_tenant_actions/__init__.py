from __future__ import annotations

from flask import Blueprint, render_template
from _shared.portal.application.service_tools import build_service_tool_meta

paypal_tenant_actions_bp = Blueprint("paypal_tenant_actions", __name__)

TOOL_ID = "paypal_tenant_actions"
TOOL_TITLE = "PayPal Member Actions"
TOOL_HOME_PATH = "/portal/tools/paypal_tenant_actions/home"
TOOL_BLUEPRINT = paypal_tenant_actions_bp


@paypal_tenant_actions_bp.get("/portal/tools/paypal_tenant_actions/home")
def paypal_tenant_actions_home():
    return render_template("tools/paypal_tenant_actions_home.html")


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
        **build_service_tool_meta(TOOL_ID),
    }
