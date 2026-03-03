from __future__ import annotations

from flask import Blueprint, render_template

aws_tenant_actions_bp = Blueprint("aws_tenant_actions", __name__)

TOOL_ID = "aws_tenant_actions"
TOOL_TITLE = "AWS Tenant Actions"
TOOL_HOME_PATH = "/portal/tools/aws_tenant_actions/home"
TOOL_BLUEPRINT = aws_tenant_actions_bp


@aws_tenant_actions_bp.get("/portal/tools/aws_tenant_actions/home")
def aws_tenant_actions_home():
    return render_template("tools/aws_tenant_actions_home.html")
