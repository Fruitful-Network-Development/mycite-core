from __future__ import annotations

from flask import Blueprint, render_template

paypal_tenant_actions_bp = Blueprint("paypal_tenant_actions", __name__)

TOOL_ID = "paypal_tenant_actions"
TOOL_TITLE = "PayPal Tenant Actions"
TOOL_HOME_PATH = "/portal/tools/paypal_tenant_actions/home"
TOOL_BLUEPRINT = paypal_tenant_actions_bp


@paypal_tenant_actions_bp.get("/portal/tools/paypal_tenant_actions/home")
def paypal_tenant_actions_home():
    return render_template("tools/paypal_tenant_actions_home.html")
