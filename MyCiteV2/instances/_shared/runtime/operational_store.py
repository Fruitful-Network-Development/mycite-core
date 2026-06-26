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

import copy
import glob
import os
from pathlib import Path
from typing import Any

import yaml

from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (
    _as_list,
    _as_text,
)
from MyCiteV2.packages.adapters.filesystem.atomic_io import KEEP, atomic_write_yaml
from MyCiteV2.packages.core.grantee import load_grantee_profile, save_grantee_profile
from MyCiteV2.packages.core.grantee.schema import GranteeProfile
from MyCiteV2.packages.core.grantee.store import GranteeProfileWriteError

# Grantee profile location (operator-managed JSON, never MOS):
#   {private_dir}/utilities/tools/fnd-csm/grantee.{fnd_msn}.{grantee_msn}.json
#   Schema: mycite.v2.grantee.profile.v1
_GRANTEE_DIR_RELATIVE = ("utilities", "tools", "fnd-csm")
# Prefer the .yaml leaflet (post-cutover); .json is the pre-cutover format, read as a fallback.
_GRANTEE_GLOB_EXTS = ("yaml", "json")

# In-process cache keyed by (resolved private_dir, glob fingerprint). The
# fingerprint is a per-file (name, mtime, size) tuple, so any add/delete/edit
# — including a same-stem .json->.yaml swap or an mtime-preserving restore that
# a (max_mtime, count) fingerprint would miss — invalidates it. Before this
# cache the utilities surface re-globbed + re-parsed every grantee on every load.
_GRANTEE_PROFILES_CACHE: dict[str, tuple[tuple, list[dict[str, Any]]]] = {}


def _grantee_paths(base: Path) -> list[str]:
    """All grantee profile files, preferring the .yaml leaflet over a same-stem .json."""
    base_dir = base.joinpath(*_GRANTEE_DIR_RELATIVE)
    by_stem: dict[str, str] = {}
    for ext in _GRANTEE_GLOB_EXTS:  # yaml first -> wins the stem over a stale .json
        for path in glob.glob(str(base_dir / f"grantee.*.{ext}")):
            by_stem.setdefault(Path(path).stem, path)
    return sorted(by_stem.values())


def _grantee_glob_fingerprint(base: Path) -> tuple:
    """Per-file (name, mtime, size) fingerprint over the resolved grantee paths.

    Discriminates a same-stem ``.json``->``.yaml`` swap and an mtime-preserving
    restore (both invisible to a ``(max_mtime, count)`` fingerprint), so the
    cache can never serve a stale PayPal/SES credential set.
    """
    out: list[tuple[str, float, int]] = []
    for path in _grantee_paths(base):
        try:
            stat = Path(path).stat()
        except OSError:
            continue
        out.append((Path(path).name, stat.st_mtime, stat.st_size))
    return tuple(out)


# ---------------------------------------------------------------------
# Leaflet cutover (split identity / secret). When MYCITE_GRANTEE_LEAFLETS is
# enabled and identity leaflets exist, grantee identity is read from the shared
# site-core tree and PayPal/AWS secrets are merged in from an admin-only dir;
# otherwise the legacy per-instance fnd-csm read below is used unchanged. The
# flag defaults OFF so production stays on the legacy path until the writer side
# lands and the flip is made deliberately.
# ---------------------------------------------------------------------
_SECRET_SUBCONFIGS = ("paypal", "aws_ses")
_GRANTEE_SECRETS_SCHEMA = "mycite.v2.grantee.secrets.v1"


def _grantee_leaflets_enabled() -> bool:
    return os.environ.get("MYCITE_GRANTEE_LEAFLETS", "").strip().lower() in {"1", "true", "yes", "on"}


def _shared_grantee_dirs() -> tuple[Path | None, Path | None]:
    """(identity_dir, secrets_dir) under the shared clients tree, or (None, None).

    Resolved from MYCITE_WEBAPPS_ROOT so tests can point it at a tmp tree.
    """
    root = os.environ.get("MYCITE_WEBAPPS_ROOT")
    if not root:
        return None, None
    base = Path(root) / "clients" / "_shared"
    return base / "site-core" / "grantee", base / "dashboard-admin" / "grantee"


def _identity_leaflet_paths(identity_dir: Path) -> list[str]:
    return sorted(glob.glob(str(identity_dir / "*.grantee_profile.yaml")))


def _shared_grantee_fingerprint(identity_dir: Path, secrets_dir: Path | None) -> tuple:
    """Per-file (path, mtime, size) fingerprint over both shared dirs."""
    out: list[tuple[str, float, int]] = []
    for directory in (identity_dir, secrets_dir):
        if directory is None or not directory.is_dir():
            continue
        for path in sorted(glob.glob(str(directory / "*.yaml"))):
            try:
                stat = Path(path).stat()
            except OSError:
                continue
            out.append((str(path), stat.st_mtime, stat.st_size))
    return tuple(out)


def _secrets_index(secrets_dir: Path | None) -> tuple[dict[str, dict], dict[str, dict]]:
    """Index secret sidecars by msn_id and by short_name (lowercased)."""
    by_msn: dict[str, dict] = {}
    by_short: dict[str, dict] = {}
    if secrets_dir is None or not secrets_dir.is_dir():
        return by_msn, by_short
    for path in glob.glob(str(secrets_dir / "grantee.*.secrets.yaml")):
        try:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        msn = _as_text(data.get("msn_id"))
        short = _as_text(data.get("short_name")).lower()
        if msn:
            by_msn[msn] = data
        if short:
            by_short[short] = data
    return by_msn, by_short


def _merge_grantee_leaflets(identity_dir: Path, secrets_dir: Path | None) -> list[dict[str, Any]]:
    """Identity leaflets merged with their admin-only secret sidecars.

    The PayPal/AWS sub-configs live only in the secrets dir; everything else is
    in the public-tree identity leaflet. Validation goes through
    ``GranteeProfile`` so the returned dicts match the legacy shape exactly.
    Parse failures are skipped — this is a read surface, not a validator.
    """
    secrets_by_msn, secrets_by_short = _secrets_index(secrets_dir)
    profiles: list[dict[str, Any]] = []
    for path in _identity_leaflet_paths(identity_dir):
        try:
            identity = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(identity, dict):
            continue
        msn = _as_text(identity.get("msn_id"))
        short = _as_text(identity.get("short_name")).lower()
        secrets = secrets_by_msn.get(msn) or secrets_by_short.get(short) or {}
        merged = dict(identity)
        for key in _SECRET_SUBCONFIGS:
            if isinstance(secrets.get(key), dict):
                merged[key] = secrets[key]
        try:
            profile = GranteeProfile.from_dict(merged)
        except (ValueError, TypeError):
            continue
        profiles.append(profile.to_dict())
    return sorted(profiles, key=lambda p: _as_text(p.get("label")).lower())


def load_grantee_leaflets_if_enabled() -> list[dict[str, Any]] | None:
    """Merged grantee leaflets when the cutover is on and leaflets exist, else None.

    Shared by both grantee read paths (this module and ``tolling``) so the merge
    logic and its cache live in one place.
    """
    if not _grantee_leaflets_enabled():
        return None
    identity_dir, secrets_dir = _shared_grantee_dirs()
    if identity_dir is None or not _identity_leaflet_paths(identity_dir):
        return None
    key = f"leaflets::{identity_dir}"
    fingerprint = _shared_grantee_fingerprint(identity_dir, secrets_dir)
    cached = _GRANTEE_PROFILES_CACHE.get(key)
    if cached is not None and cached[0] == fingerprint:
        return copy.deepcopy(cached[1])
    result = _merge_grantee_leaflets(identity_dir, secrets_dir)
    _GRANTEE_PROFILES_CACHE[key] = (fingerprint, result)
    return copy.deepcopy(result)


def load_grantee_profiles(private_dir: str | Path | None) -> list[dict[str, Any]]:
    """Return all grantee profile dicts (identity + merged secrets).

    Prefers the shared leaflet source when the cutover is enabled (identity from
    ``site-core/grantee`` + secrets from ``dashboard-admin/grantee``); otherwise
    falls back to the legacy per-instance ``fnd-csm`` read (``.yaml`` preferred
    over ``.json``). Returns plain dicts (call sites read ``grantee.get(...)``);
    cached per source fingerprint.
    """
    shared = load_grantee_leaflets_if_enabled()
    if shared is not None:
        return shared

    if private_dir is None:
        return []
    base = Path(private_dir).resolve()
    key = str(base)
    fingerprint = _grantee_glob_fingerprint(base)
    cached = _GRANTEE_PROFILES_CACHE.get(key)
    if cached is not None and cached[0] == fingerprint:
        return copy.deepcopy(cached[1])

    profiles: list[dict[str, Any]] = []
    for path in _grantee_paths(base):
        try:
            profile = load_grantee_profile(path)
        except (FileNotFoundError, ValueError):
            continue
        profiles.append(profile.to_dict())
    result = sorted(profiles, key=lambda p: _as_text(p.get("label")).lower())
    _GRANTEE_PROFILES_CACHE[key] = (fingerprint, result)
    return copy.deepcopy(result)


def load_grantee_profile_resolved(msn_id: str, *, legacy_path: str | Path) -> GranteeProfile:
    """Load one grantee as a GranteeProfile for read-then-mutate-then-save.

    Cutover ON: the merged identity+secrets leaflet for ``msn_id``. OFF (or no
    leaflet for that msn): the legacy full-profile file at ``legacy_path``.
    """
    if _grantee_leaflets_enabled():
        for profile in load_grantee_leaflets_if_enabled() or []:
            if _as_text(profile.get("msn_id")) == _as_text(msn_id):
                return GranteeProfile.from_dict(profile)
    return load_grantee_profile(legacy_path)


def persist_grantee_profile(profile: GranteeProfile, *, legacy_path: str | Path) -> None:
    """Persist a mutated GranteeProfile.

    Cutover ON: split — identity (no secrets) to the site-core leaflet (0644)
    and the PayPal/AWS sub-configs to the admin-only secret sidecar (0600).
    OFF: the legacy full-profile write at ``legacy_path`` (``.yaml``). Both go
    through the shared atomic writer so a torn write never lands.
    """
    if _grantee_leaflets_enabled():
        identity_dir, secrets_dir = _shared_grantee_dirs()
        full = profile.to_dict()
        short = _as_text(full.get("short_name")).lower()
        if identity_dir is not None and secrets_dir is not None and short:
            identity = {k: v for k, v in full.items() if k not in _SECRET_SUBCONFIGS}
            secrets: dict[str, Any] = {
                "schema": _GRANTEE_SECRETS_SCHEMA,
                "msn_id": _as_text(full.get("msn_id")),
                "short_name": full.get("short_name"),
            }
            for key in _SECRET_SUBCONFIGS:
                if key in full:
                    secrets[key] = full[key]
            secrets_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(secrets_dir, 0o700)  # admin-only; nginx/other cannot traverse
            try:
                atomic_write_yaml(
                    identity_dir / f"0000-00-00.artifact-grantee-profile.{short}.grantee_profile.yaml",
                    identity,
                    mode=0o644,
                )
                atomic_write_yaml(
                    secrets_dir / f"grantee.{short}.secrets.yaml",
                    secrets,
                    mode=KEEP,  # secrets stay 0600
                )
            except OSError as exc:
                raise GranteeProfileWriteError(
                    f"failed to persist grantee leaflet for {short!r}: {exc}"
                ) from exc
            _GRANTEE_PROFILES_CACHE.clear()
            return
    save_grantee_profile(Path(legacy_path).with_suffix(".yaml"), profile)


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
    "load_grantee_leaflets_if_enabled",
    "load_grantee_profile_resolved",
    "load_grantee_profiles",
    "persist_grantee_profile",
    "resolve_selected_domain",
    "resolve_selected_grantee",
]
