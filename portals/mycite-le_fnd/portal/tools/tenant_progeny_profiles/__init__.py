from __future__ import annotations

from flask import Blueprint, render_template

tenant_progeny_profiles_bp = Blueprint("tenant_progeny_profiles", __name__)

TOOL_ID = "tenant_progeny_profiles"
TOOL_TITLE = "Tenant Progeny Profiles"
TOOL_HOME_PATH = "/portal/tools/tenant_progeny_profiles/home"
TOOL_BLUEPRINT = tenant_progeny_profiles_bp


@tenant_progeny_profiles_bp.get("/portal/tools/tenant_progeny_profiles/home")
def tenant_progeny_profiles_home():
    return render_template("tools/tenant_progeny_profiles_home.html")
