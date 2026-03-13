from __future__ import annotations

from flask import Blueprint, render_template

paypal_service_agreement_bp = Blueprint("paypal_service_agreement", __name__)

TOOL_ID = "paypal_service_agreement"
TOOL_TITLE = "PayPal Service Agreement"
TOOL_HOME_PATH = "/portal/tools/paypal_service_agreement/home"
TOOL_BLUEPRINT = paypal_service_agreement_bp


@paypal_service_agreement_bp.get("/portal/tools/paypal_service_agreement/home")
def paypal_service_agreement_home():
    return render_template("tools/paypal_service_agreement_home.html")


def get_tool() -> dict[str, object]:
    return {
        "tool_id": TOOL_ID,
        "display_name": TOOL_TITLE,
        "route_prefix": f"/portal/tools/{TOOL_ID}",
        "home_path": TOOL_HOME_PATH,
        "blueprint": TOOL_BLUEPRINT,
    }
