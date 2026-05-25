"""FND-CSM legacy preservation routes.

The historical "FND-CSM tool surface" was retired in Phase 7 (dead bundle
code removed in Phase 13a). What survives here is the legacy POST-route shim
(run_portal_fnd_csm / run_portal_fnd_csm_action), which just forwards to the
shell entry. Phase B moved grantee-profile loading out to
``operational_store`` (the operational/datum seam); this module is now a
deletion candidate (Phase C) once the shim routes are confirmed dead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (
    _as_dict,
    _as_text,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_CSM_TOOL_SURFACE_ID,
    PORTAL_SHELL_REQUEST_SCHEMA,
)



# ---------------------------------------------------------------------------
# Tool state normalization
# ---------------------------------------------------------------------------

def _normalize_fnd_csm_tool_state(request_payload: dict[str, Any]) -> dict[str, Any]:
    tool_state = _as_dict(request_payload.get("tool_state"))
    return {
        "selected_grantee_msn": _as_text(tool_state.get("selected_grantee_msn")),
        "selected_domain": _as_text(tool_state.get("selected_domain")),
        "active_tab": _as_text(tool_state.get("active_tab")) or "email",
        "engaged_frame_id": _as_text(tool_state.get("engaged_frame_id")),
    }


# ---------------------------------------------------------------------------
# Action handler
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_portal_fnd_csm(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    portal_instance_id: str,
    portal_domain: str,
    authority_db_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    shell_request = dict(request_payload or {})
    shell_request["schema"] = PORTAL_SHELL_REQUEST_SCHEMA
    shell_request.setdefault("requested_surface_id", FND_CSM_TOOL_SURFACE_ID)
    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        authority_db_file=authority_db_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )


def run_portal_fnd_csm_action(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    portal_instance_id: str,
    portal_domain: str,
    authority_db_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    shell_request = dict(request_payload or {})
    shell_request["schema"] = PORTAL_SHELL_REQUEST_SCHEMA
    shell_request.setdefault("requested_surface_id", FND_CSM_TOOL_SURFACE_ID)
    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        authority_db_file=authority_db_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )




# ---------------------------------------------------------------------------
# Phase 12g — Utilities extension dispatch re-export
# ---------------------------------------------------------------------------
# The dispatch table, the five per-extension renderer wrappers, the grantee
# profile form, and `render_extension` moved to
# `instances/_shared/runtime/utilities_extensions/__init__.py` in Phase 12g.
# No back-compat re-export here: it created a circular import (utilities_extensions
# imports `_build_*_extension_payload` from this module, so we cannot import
# `EXTENSION_RENDERERS` back from utilities_extensions at module load).
# Callers should import EXTENSION_RENDERERS / render_extension from
# `MyCiteV2.instances._shared.runtime.utilities_extensions` directly.
