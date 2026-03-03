from __future__ import annotations

from flask import Blueprint, render_template

operations_bp = Blueprint("operations", __name__)

TOOL_ID = "operations"
TOOL_TITLE = "Operations"
TOOL_HOME_PATH = "/portal/tools/operations/home"
TOOL_BLUEPRINT = operations_bp


@operations_bp.get("/portal/tools/operations/home")
def operations_home():
    return render_template("tools/operations_home.html")

