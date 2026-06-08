"""OperationalStore — the seam between operational files and datum documents.

The portal handles two distinct kinds of state, which earlier iterations
conflated:

* **Datum documents** — the MOS corpus the workbench renders. Canonical
  ``lv.<msn>.<sandbox>.<name>.<hash>`` (and legacy ``system:`` / ``sandbox:``)
  ids, addressed through the datum file-key taxonomy in
  ``packages.state_machine.portal_shell.shell`` and read via
  ``WorkbenchUiReadService.read_surface``.

* **Operational files** — the config that *drives an FND portal instance*:
  grantee profiles and extension settings living as JSON under the instance's
  utility directory (``<private_dir>/utilities/tools/...``). These are NOT
  datum documents and never live in MOS.

This module is the canonical home for reading operational config. It was
extracted from the retired ``portal_fnd_csm_runtime`` so the operational
boundary is explicit and the retired module can be deleted. Datum-document
access does not belong here; operational config access does not belong in the
shell file-key taxonomy.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (
    _as_list,
    _as_text,
)
from MyCiteV2.packages.core.grantee import load_grantee_profile

# Grantee profile location (operator-managed JSON, never MOS):
#   {private_dir}/utilities/tools/fnd-csm/grantee.{fnd_msn}.{grantee_msn}.json
#   Schema: mycite.v2.grantee.profile.v1
_GRANTEE_GLOB_RELATIVE = ("utilities", "tools", "fnd-csm", "grantee.*.json")

# In-process cache keyed by (resolved private_dir, glob fingerprint). The
# fingerprint is (max mtime, file count), so any add/delete/edit invalidates
# it without a per-file stat loop. Before this cache the utilities surface
# re-globbed + re-parsed every grantee JSON on every page load.
_GRANTEE_PROFILES_CACHE: dict[str, tuple[tuple[float, int], list[dict[str, Any]]]] = {}


def _grantee_glob_pattern(base: Path) -> str:
    return str(base.joinpath(*_GRANTEE_GLOB_RELATIVE))


def _grantee_glob_fingerprint(base: Path) -> tuple[float, int]:
    paths = glob.glob(_grantee_glob_pattern(base))
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


def load_grantee_profiles(private_dir: str | Path | None) -> list[dict[str, Any]]:
    """Glob + parse all grantee profile JSON files from the utility directory.

    Delegates parsing/validation to ``load_grantee_profile``. When a grantee
    JSON lacks the inline ``paypal`` sub-config and a legacy sidecar exists,
    hydrates the in-memory profile from the sidecar (the on-disk JSON is never
    written back here). Returns plain dicts (call sites read
    ``grantee.get("domains")`` etc.). Result is cached per (private_dir, glob
    fingerprint).
    """
    if private_dir is None:
        return []
    base = Path(private_dir).resolve()
    key = str(base)
    fingerprint = _grantee_glob_fingerprint(base)
    cached = _GRANTEE_PROFILES_CACHE.get(key)
    if cached is not None and cached[0] == fingerprint:
        return list(cached[1])

    profiles: list[dict[str, Any]] = []
    for path in sorted(glob.glob(_grantee_glob_pattern(base))):
        try:
            profile = load_grantee_profile(path)
        except (FileNotFoundError, ValueError):
            continue
        profiles.append(profile.to_dict())
    result = sorted(profiles, key=lambda p: _as_text(p.get("label")).lower())
    _GRANTEE_PROFILES_CACHE[key] = (fingerprint, result)
    return list(result)


def resolve_selected_grantee(
    grantees: list[dict[str, Any]],
    tool_state: dict[str, Any],
) -> dict[str, Any]:
    selected_msn = _as_text(tool_state.get("selected_grantee_msn"))
    if selected_msn:
        for grantee in grantees:
            if _as_text(grantee.get("msn_id")) == selected_msn:
                return grantee
    return grantees[0] if grantees else {}


def resolve_selected_domain(
    grantee: dict[str, Any],
    tool_state: dict[str, Any],
) -> str:
    domains = _as_list(grantee.get("domains"))
    selected = _as_text(tool_state.get("selected_domain"))
    if selected and selected in domains:
        return selected
    return domains[0] if domains else ""


__all__ = [
    "load_grantee_profiles",
    "resolve_selected_domain",
    "resolve_selected_grantee",
]
