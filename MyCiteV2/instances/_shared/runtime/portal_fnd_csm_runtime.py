"""FND-CSM legacy preservation routes + grantee profile loading.

The historical "FND-CSM tool surface" was retired in Phase 7 (and its
dead bundle code was removed in Phase 13a). What survives in this file
is the live POST-route shim layer for CVCC donations + TFF newsletter
preservation invariants, plus the grantee-profile loader the utilities
surface consumes via Phase 12h's _build_utilities_surface_context.

Grantee profiles are the sole source of domain/user truth:
  {private_dir}/utilities/tools/fnd-csm/grantee.{fnd_msn}.{grantee_msn}.json
  Schema: mycite.v2.grantee.profile.v1
  Fields: msn_id, label, short_name, domains[], users[]
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.utilities_extensions import _hydrate_paypal_from_sidecar
from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (
    _as_dict,
    _as_list,
    _as_text,
)
from MyCiteV2.packages.core.grantee import load_grantee_profile
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_CSM_TOOL_SURFACE_ID,
    PORTAL_SHELL_REQUEST_SCHEMA,
)

# Phase 14c: in-process cache for `_load_grantee_profiles`. Keyed by
# (resolved private_dir path, glob mtime fingerprint). The glob fingerprint
# is the max mtime + the file count, so any file add/delete/modify
# invalidates the cache without a per-file stat-loop overhead. The Phase 12h
# `_build_utilities_surface_context` runs this once per request; before
# this cache it re-globbed + re-parsed every grantee JSON on every page
# load — the single biggest source of the Utilities lag the user reported.
_GRANTEE_PROFILES_CACHE: dict[str, tuple[tuple[float, int], list[dict[str, Any]]]] = {}


def _grantee_glob_fingerprint(base: Path) -> tuple[float, int]:
    pattern = str(base / "utilities" / "tools" / "fnd-csm" / "grantee.*.json")
    paths = glob.glob(pattern)
    if not paths:
        return (0.0, 0)
    max_mtime = 0.0
    for path in paths:
        try:
            stat = Path(path).stat()
            if stat.st_mtime > max_mtime:
                max_mtime = stat.st_mtime
        except OSError:
            continue
    return (max_mtime, len(paths))


def _load_grantee_profiles(private_dir: str | Path | None) -> list[dict[str, Any]]:
    """Glob and parse all grantee profile JSON files from the fnd-csm tool directory.

    Phase 8 (grantee_profile_contract.md): delegates parsing + validation to
    `load_grantee_profile`. When a grantee JSON lacks the inline `paypal`
    sub-config and a legacy sidecar file exists, hydrates the in-memory
    profile from the sidecar so the Utilities extensions see the webhook URL.
    The on-disk grantee JSON is never written back here; the migration is
    one-shot once an operator edits the profile through the Phase 9 form.

    Phase 14c: result is cached in-process keyed by (private_dir, glob
    fingerprint) so repeated requests within the same gunicorn worker skip
    the filesystem walk + JSON parse. Adding/removing/editing any grantee
    JSON file under the directory invalidates the cache automatically.

    Returns dicts (not GranteeProfile instances) so the existing call sites
    in this runtime (which read `grantee.get("domains")`, etc.) keep working
    unchanged. Sub-configs surface as nested dicts when present.
    """
    if private_dir is None:
        return []
    base = Path(private_dir).resolve()
    key = str(base)
    fingerprint = _grantee_glob_fingerprint(base)
    cached = _GRANTEE_PROFILES_CACHE.get(key)
    if cached is not None and cached[0] == fingerprint:
        return list(cached[1])

    pattern = str(base / "utilities" / "tools" / "fnd-csm" / "grantee.*.json")
    profiles: list[dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        try:
            profile = load_grantee_profile(path)
        except (FileNotFoundError, ValueError):
            continue
        if profile.paypal is None:
            sidecar_paypal = _hydrate_paypal_from_sidecar(base, profile.msn_id)
            if sidecar_paypal is not None:
                profile = profile.with_paypal(sidecar_paypal)
        profiles.append(profile.to_dict())
    result = sorted(profiles, key=lambda p: _as_text(p.get("label")).lower())
    _GRANTEE_PROFILES_CACHE[key] = (fingerprint, result)
    return list(result)


def _resolve_selected_grantee(
    grantees: list[dict[str, Any]],
    tool_state: dict[str, Any],
) -> dict[str, Any]:
    selected_msn = _as_text(tool_state.get("selected_grantee_msn"))
    if selected_msn:
        for g in grantees:
            if _as_text(g.get("msn_id")) == selected_msn:
                return g
    return grantees[0] if grantees else {}


def _resolve_selected_domain(
    grantee: dict[str, Any],
    tool_state: dict[str, Any],
) -> str:
    domains = _as_list(grantee.get("domains"))
    selected = _as_text(tool_state.get("selected_domain"))
    if selected and selected in domains:
        return selected
    return domains[0] if domains else ""



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
