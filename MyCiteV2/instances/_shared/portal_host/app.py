from __future__ import annotations

import base64
import glob
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

_log = logging.getLogger("mycite.portal_host")

try:
    from flask import Flask, abort, jsonify, make_response, redirect, render_template, request
    _FLASK_IMPORT_ERROR: ModuleNotFoundError | None = None
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in dependency-light test environments
    Flask = Any  # type: ignore[misc,assignment]
    _FLASK_IMPORT_ERROR = exc

    def _raise_flask_import_error(*_args: Any, **_kwargs: Any) -> Any:
        raise ModuleNotFoundError("flask is required to run the portal host") from _FLASK_IMPORT_ERROR

    abort = jsonify = make_response = redirect = render_template = _raise_flask_import_error

    class _MissingRequest:
        def get_json(self, *args: Any, **kwargs: Any) -> Any:
            return _raise_flask_import_error(*args, **kwargs)

    request = _MissingRequest()

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
    run_portal_shell_entry,
    run_system_profile_basics_action,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
    build_tool_exposure_policy,
)
from MyCiteV2.packages.domain import canonical_contact_entry
from MyCiteV2.packages.peripherals.aws.cloud_adapter import AwsPeripheralCloudAdapter
from MyCiteV2.packages.peripherals.aws.contracts import SesSendError
from MyCiteV2.packages.state_machine.portal_shell import (
    AGRO_ERP_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_EXTENSIONS_SURFACE_ID,
    UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
    UTILITIES_PERIPHERALS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOLS_SURFACE_ID,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    PortalScope,
    build_portal_tool_registry_entries,
)

_aws_peripheral = AwsPeripheralCloudAdapter()

V2_PORTAL_HEALTH_SCHEMA = "mycite.v2.portal.health.v1"
V2_PORTAL_ERROR_SCHEMA = "mycite.v2.portal.error.v1"
HOST_SHAPE = "v2_native"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _render_email_health_page(snapshot: dict, routes: list) -> str:
    """Render the operator-facing email-health page as a self-contained
    HTML string (no JS-shell dependency). Used by GET /portal/email-health."""
    from html import escape as _esc

    failed = int(snapshot.get("failed", 0) or 0)
    passed = int(snapshot.get("passed", 0) or 0)
    generated_at = _esc(str(snapshot.get("generated_at", "")))
    overall_ok = failed == 0
    banner_bg = "#1b7f3b" if overall_ok else "#b3261e"
    banner_txt = (
        "All email checks passing"
        if overall_ok
        else f"{failed} email check(s) FAILING — action needed"
    )

    check_rows = []
    for r in snapshot.get("results", []):
        ok = bool(r.get("ok"))
        mark = "✓" if ok else "✗"
        color = "#1b7f3b" if ok else "#b3261e"
        bg = "" if ok else ' style="background:#fdeceb"'
        check_rows.append(
            f"<tr{bg}>"
            f'<td style="text-align:center;color:{color};font-weight:700">{mark}</td>'
            f'<td style="font-family:ui-monospace,monospace;white-space:nowrap">{_esc(str(r.get("name", "")))}</td>'
            f"<td>{_esc(str(r.get('detail', '')))}</td>"
            "</tr>"
        )
    check_rows_html = "\n".join(check_rows) or (
        '<tr><td colspan="3">no checks ran</td></tr>'
    )

    route_rows = []
    for rt in routes:
        route_rows.append(
            f'<tr><td style="font-family:ui-monospace,monospace">{_esc(str(rt.get("address", "")))}</td>'
            "<td>→</td>"
            f'<td style="font-family:ui-monospace,monospace">{_esc(str(rt.get("forwards_to") or "—"))}</td>'
            f"<td>{_esc(str(rt.get('lifecycle') or ''))}</td></tr>"
        )
    route_rows_html = "\n".join(route_rows) or (
        '<tr><td colspan="4">no forwarding routes found</td></tr>'
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>FND Email Health</title>
<style>
  body {{ font-family: system-ui, -apple-system, Arial, sans-serif; color:#1a1a1a;
          margin:0; background:#f5f6f7; line-height:1.45; }}
  .wrap {{ max-width: 60rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 0.2rem; }}
  .banner {{ color:#fff; background:{banner_bg}; padding:0.7rem 1rem; border-radius:8px;
             font-weight:700; margin:1rem 0; }}
  .meta {{ color:#555; font-size:0.85rem; margin-bottom:1rem; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:8px;
           overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.08); margin-bottom:2rem; }}
  th, td {{ text-align:left; padding:0.5rem 0.7rem; border-bottom:1px solid #eee;
            font-size:0.9rem; vertical-align:top; }}
  th {{ background:#fafafa; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; color:#666; }}
  h2 {{ font-size:1.05rem; margin:0 0 0.5rem; }}
  a.btn {{ display:inline-block; background:#1a1a1a; color:#fff; text-decoration:none;
           padding:0.4rem 0.9rem; border-radius:6px; font-size:0.85rem; }}
</style></head>
<body><div class="wrap">
  <h1>FND Email Health</h1>
  <div class="meta">Last checked {generated_at} UTC · {passed} passing, {failed} failing
     · <a class="btn" href="/portal/email-health?refresh=1">Re-run checks now</a></div>
  <div class="banner">{_esc(banner_txt)}</div>

  <h2>Deliverability checks</h2>
  <table>
    <thead><tr><th></th><th>Check</th><th>Detail</th></tr></thead>
    <tbody>
{check_rows_html}
    </tbody>
  </table>

  <h2>Forwarding routes (mailbox &rarr; destination)</h2>
  <table>
    <thead><tr><th>Address</th><th></th><th>Forwards to</th><th>Lifecycle</th></tr></thead>
    <tbody>
{route_rows_html}
    </tbody>
  </table>
</div></body></html>
"""


def _current_git_head_build_id() -> str | None:
    """Return the on-disk git HEAD as ``git-<sha>`` (or None if unavailable).

    Shared by the build-id default and the healthz code-coherence check.
    """
    try:
        import subprocess

        repo_root = Path(__file__).resolve().parents[4]
        sha = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode("ascii").strip()
        return f"git-{sha}" if sha else None
    except Exception:
        # Fail-loud: a missing git tree/binary on the deploy host is unusual,
        # and silently masking it is how a stale build tag went unnoticed.
        _log.warning("portal build-id: git HEAD lookup failed", exc_info=True)
        return None


_FRESHNESS_TOLERANCE_SECONDS = 2.0


def _portal_source_root() -> Path:
    # .../MyCiteV2 (this file is MyCiteV2/instances/_shared/portal_host/app.py).
    return Path(__file__).resolve().parents[3]


def _newest_source_mtime(root: Path | None = None) -> float:
    """Newest ``.py`` mtime under the imported runtime subtrees (``packages/`` +
    ``instances/``). Tests/docs/scripts are excluded so editing them never trips
    the stale-worker signal. Robust to files vanishing mid-walk."""
    base = root if root is not None else _portal_source_root()
    newest = 0.0
    for sub in ("packages", "instances"):
        for path in (base / sub).rglob("*.py"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > newest:
                newest = mtime
    return newest


def _source_freshness(baseline_mtime: float) -> dict[str, Any]:
    """Detect "disk source newer than the running worker" — the ``--preload``
    stale-worker failure mode that ``_code_coherence``'s build-id compare cannot
    see (the build id is a deploy-pinned env frozen at import, not the worker's
    actual code-load point). ``baseline_mtime`` is the newest source mtime captured
    AT IMPORT (i.e. when this worker loaded its code); compare it to the current
    on-disk newest mtime. ``unknown`` (no baseline) is non-gating."""
    disk = _newest_source_mtime()
    if baseline_mtime <= 0.0:
        status = "unknown"
    elif disk - baseline_mtime > _FRESHNESS_TOLERANCE_SECONDS:
        status = "stale"
    else:
        status = "fresh"
    return {"status": status, "loaded_mtime": baseline_mtime, "disk_mtime": disk}


def _default_portal_build_id() -> str:
    """Fall back to the git short SHA when MYCITE_V2_PORTAL_BUILD_ID is unset.

    Phase 14c: operators were seeing healthz report a stale build tag
    (``20260514-000401-visual-verify``) months after the deploy pipeline
    stopped bumping it, which made it impossible to tell which code the
    deployed gunicorn was actually running. Now: if the env var is
    explicitly set, use that (deploy pipelines + CI can override). If
    unset, try ``git rev-parse --short HEAD`` so the build tag reflects
    the actual code. If even that fails (no git tree, no binary), fall
    back to a sentinel so existing tests + tooling don't break.
    """
    explicit = _as_text(os.environ.get("MYCITE_V2_PORTAL_BUILD_ID"))
    if explicit:
        return explicit
    head = _current_git_head_build_id()
    if head:
        return head
    # Fail-loud: don't silently return the sentinel — surface that the deployed
    # code version is unknown so it can be investigated, not masked.
    _log.warning(
        "portal build-id: MYCITE_V2_PORTAL_BUILD_ID unset and git HEAD "
        "unavailable; reporting 'not-set' (deployed code version is unknown)"
    )
    return "not-set"


def _code_coherence(running_build_id: str) -> dict[str, Any]:
    """Compare the running build to the on-disk git HEAD so a stale-in-memory
    worker (old code in memory while disk moved ahead) is *visible* in healthz
    rather than silent — the failure mode behind the 2026-05 contact-form outage.

    status: ``current`` (running == disk HEAD), ``stale`` (running an older git
    build than disk), ``pinned`` (running an explicit non-git build label that
    can't equate to a SHA — operator eyeballs ``disk_head``), or ``unknown``.
    """
    head = _current_git_head_build_id()
    if head is None:
        return {"status": "unknown", "running": running_build_id, "disk_head": None}
    sha = head.removeprefix("git-")
    # "current" if the build id is exactly the HEAD git tag OR a deploy label that
    # embeds the HEAD short-sha (the deploy script stamps ``...-git<sha>``).
    if running_build_id == head or (sha and sha in running_build_id):
        return {"status": "current", "running": running_build_id, "disk_head": head}
    status = "stale" if running_build_id.startswith("git-") else "pinned"
    return {"status": status, "running": running_build_id, "disk_head": head}


PORTAL_BUILD_ID = _default_portal_build_id()
# Captured once in the gunicorn --preload master (pre-fork; inherited COW by every
# worker) so healthz can detect a worker running code older than what's on disk.
PORTAL_SOURCE_MTIME_AT_IMPORT = _newest_source_mtime()
PORTAL_SHELL_ASSET_MANIFEST_SCHEMA = "mycite.v2.portal.shell.asset_manifest.v1"
PORTAL_SHELL_INITIAL_LOAD_BUDGET_GZIP_BYTES = 41000
PORTAL_SHELL_TOTAL_BUDGET_GZIP_BYTES = 65000
PORTAL_SHELL_DEFERRED_BUDGET_GZIP_BYTES = 30000
PORTAL_SHELL_MODULE_CONTRACTS = (
    {
        "module_id": "region_renderers",
        "file": "v2_portal_shell_region_renderers.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shell_chrome",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalShellRegionRenderers",
                "required_callables": ("renderActivityBar", "renderControlPanel"),
            },
        ),
    },
    {
        "module_id": "tool_surface_adapter",
        "file": "v2_portal_tool_surface_adapter.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shared_tool_host",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalToolSurfaceAdapter",
                "required_callables": (
                    "buildDirectSurfaceRequest",
                    "resolveReadiness",
                    "resolveToolId",
                    "resolveSurfaceState",
                    "renderWrappedSurface",
                ),
            },
        ),
    },
    {
        "module_id": "system_workspace",
        "file": "v2_portal_system_workspace.js",
        "load_phase": "deferred",
        "loading_scope": ("system.root",),
        "budget_group": "deferred_tool_renderers",
        "exports": (
            {
                "global": "PortalSystemWorkspaceRenderer",
                "required_callables": ("render",),
            },
        ),
    },
    {
        "module_id": "network_workspace",
        "file": "v2_portal_network_workspace.js",
        "load_phase": "deferred",
        "loading_scope": ("network.root",),
        "budget_group": "deferred_tool_renderers",
        "exports": (
            {
                "global": "PortalNetworkWorkspaceRenderer",
                "required_callables": ("render",),
            },
            {
                "global": "PortalNetworkInterfacePanelRenderer",
                "required_callables": ("render",),
            },
        ),
    },
    {
        "module_id": "workbench_renderers",
        "file": "v2_portal_workbench_renderers.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shared_workbench_host",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalShellWorkbenchRenderer",
                "required_callables": ("render",),
            },
        ),
    },
    {
        "module_id": "portal_component_library",
        "file": "v2_portal_component_library.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shared_component_library",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalComponentLibrary",
                "required_callables": (
                    "renderComponentFrameList",
                    "renderComponentFrame",
                    "rendererRegistry.register",
                ),
            },
        ),
    },
    {
        "module_id": "shell_core",
        "file": "v2_portal_shell_core.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shell_core",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalShellCore",
                "required_callables": ("loadShell", "loadRuntimeView", "dispatchTransition"),
            },
        ),
    },
    {
        # Phase 3 (portal_tool_surface_contract.md). The palette lists tools whose
        # applies_to_archetype/source_kind match the currently-selected datum.
        "module_id": "tool_palette",
        "file": "v2_portal_tool_palette.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shell_core",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalToolPalette",
                "required_callables": ("fetch", "mount", "refresh"),
            },
        ),
    },
    {
        # Phase 5 (docs/wiki/81). The lens panel manages presentation lenses and
        # toggles them on/off (disabled → identity passthrough). Deferred: it only
        # loads on the Utilities surface, never in the critical-shell budget.
        "module_id": "lens_panel",
        "file": "v2_portal_lens_panel.js",
        "load_phase": "deferred",
        "loading_scope": ("utilities.root",),
        "budget_group": "deferred_tool_renderers",
        "exports": (
            {
                "global": "PortalLensPanel",
                "required_callables": ("fetch", "toggle", "mount", "refresh"),
            },
        ),
    },
    {
        "module_id": "shell_watchdog",
        "file": "v2_portal_shell_watchdog.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shell_watchdog",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "__MYCITE_V2_SHELL_WATCHDOG",
                "required_callables": ("start",),
            },
        ),
    },
)
PORTAL_SHELL_MODULE_FILES = tuple(contract["file"] for contract in PORTAL_SHELL_MODULE_CONTRACTS)


def _static_asset_descriptor(filename: str, *, build_id: str, asset_id: str) -> dict[str, str]:
    path = f"/portal/static/{filename}"
    suffix = f"?v={build_id}" if build_id else ""
    return {
        "asset_id": asset_id,
        "file": filename,
        "path": path,
        "url": f"{path}{suffix}",
    }


def _shell_module_descriptor(module_contract: Mapping[str, Any], *, build_id: str) -> dict[str, Any]:
    filename = _as_text(module_contract.get("file"))
    descriptor: dict[str, Any] = _static_asset_descriptor(
        filename,
        build_id=build_id,
        asset_id=filename.rsplit(".", 1)[0],
    )
    descriptor["module_id"] = _as_text(module_contract.get("module_id"))
    descriptor["load_phase"] = _as_text(module_contract.get("load_phase")) or "startup_critical"
    descriptor["loading_scope"] = [
        _as_text(scope)
        for scope in module_contract.get("loading_scope") or []
        if _as_text(scope)
    ]
    descriptor["budget_group"] = _as_text(module_contract.get("budget_group")) or "initial_shell"
    descriptor["exports"] = [
        {
            "global": _as_text(export_contract.get("global")),
            "required_callables": [
                _as_text(callable_name)
                for callable_name in export_contract.get("required_callables") or []
                if _as_text(callable_name)
            ],
        }
        for export_contract in module_contract.get("exports") or []
        if isinstance(export_contract, Mapping)
    ]
    return descriptor


def build_shell_asset_manifest(build_id: str = PORTAL_BUILD_ID) -> dict[str, Any]:
    safe_build_id = _as_text(build_id)
    shell_modules = [
        _shell_module_descriptor(
            module_contract,
            build_id=safe_build_id,
        )
        for module_contract in PORTAL_SHELL_MODULE_CONTRACTS
    ]
    startup_module_ids = [
        module["module_id"]
        for module in shell_modules
        if _as_text(module.get("load_phase")) != "deferred"
    ]
    deferred_module_ids = [
        module["module_id"]
        for module in shell_modules
        if _as_text(module.get("load_phase")) == "deferred"
    ]
    return {
        "schema": PORTAL_SHELL_ASSET_MANIFEST_SCHEMA,
        "build_id": safe_build_id,
        "cache_policy": {
            "version_query_param": "v",
            "build_id": safe_build_id,
            "invalidation_mode": "query_versioned_static_assets",
        },
        "budget_policy": {
            "initial_load_gzip_bytes_max": PORTAL_SHELL_INITIAL_LOAD_BUDGET_GZIP_BYTES,
            "initial_load_gzip_bytes_enforcement": "hard",
            "total_gzip_bytes_max": PORTAL_SHELL_TOTAL_BUDGET_GZIP_BYTES,
            "total_gzip_bytes_enforcement": "hard",
            "deferred_gzip_bytes_max": PORTAL_SHELL_DEFERRED_BUDGET_GZIP_BYTES,
            "deferred_gzip_bytes_enforcement": "advisory",
            "startup_module_ids": startup_module_ids,
            "deferred_module_ids": deferred_module_ids,
        },
        "styles": {
            "portal_css": _static_asset_descriptor(
                "portal.css",
                build_id=safe_build_id,
                asset_id="portal_css",
            ),
        },
        "scripts": {
            "portal_js": _static_asset_descriptor(
                "portal.js",
                build_id=safe_build_id,
                asset_id="portal_js",
            ),
            "shell_entry": _static_asset_descriptor(
                "v2_portal_shell.js",
                build_id=safe_build_id,
                asset_id="shell_entry",
            ),
            "shell_modules": shell_modules,
        },
    }


def _shell_asset_files_from_manifest(manifest: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    styles = manifest.get("styles") if isinstance(manifest, Mapping) else {}
    scripts = manifest.get("scripts") if isinstance(manifest, Mapping) else {}
    for asset in [*list(styles.values()), scripts.get("portal_js"), scripts.get("shell_entry")]:
        if isinstance(asset, Mapping):
            filename = _as_text(asset.get("file"))
            if filename:
                files.append(filename)
    for asset in list(scripts.get("shell_modules") or []):
        if not isinstance(asset, Mapping):
            continue
        filename = _as_text(asset.get("file"))
        if filename:
            files.append(filename)
    return files


def _required_env_text(name: str) -> str:
    value = _as_text(os.environ.get(name))
    if not value:
        raise ValueError(f"{name} is required for the V2 portal host")
    return value


def _validate_existing_dir(path: Path, *, env_name: str) -> Path:
    resolved = Path(path)
    if not resolved.exists():
        raise ValueError(f"{env_name} must point to an existing directory: {resolved}")
    if not resolved.is_dir():
        raise ValueError(f"{env_name} must point to a directory: {resolved}")
    return resolved


def _validate_optional_path(path: Path | None, *, expect_dir: bool = False) -> Path | None:
    if path is None:
        return None
    resolved = Path(path)
    if not resolved.exists():
        return None
    if expect_dir and not resolved.is_dir():
        raise ValueError(f"Expected a directory path: {resolved}")
    if not expect_dir and not resolved.is_file():
        raise ValueError(f"Expected a file path: {resolved}")
    return resolved


def _normalize_optional_file_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    resolved = Path(path)
    if resolved.exists() and resolved.is_dir():
        raise ValueError(f"Expected a file path: {resolved}")
    return resolved


def _load_optional_json_object(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def _default_capabilities(portal_instance_id: str) -> list[str]:
    capabilities = ["datum_recognition", "spatial_projection"]
    if _as_text(portal_instance_id).lower() == "fnd":
        capabilities.extend(["fnd_peripheral_routing", "hosted_site_manifest_visibility", "hosted_site_visibility"])
    return capabilities


def _bootstrap_request(surface_id: str, *, portal_instance_id: str, query_params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    portal_scope = PortalScope(scope_id=portal_instance_id, capabilities=())
    payload: dict[str, Any] = {
        "schema": "mycite.v2.portal.shell.request.v1",
        "requested_surface_id": surface_id,
        "portal_scope": portal_scope.to_dict(),
    }
    # Phase A: every surface is query-native — the bootstrap carries the URL
    # query as surface_query (server-side canonicalization resolves it); the
    # focus-path reducer is retired.
    if query_params:
        payload["surface_query"] = {
            str(key): str(value)
            for key, value in dict(query_params or {}).items()
            if str(key).strip() and str(value).strip()
        }
    return payload


@dataclass(frozen=True)
class V2PortalHostConfig:
    portal_instance_id: str
    public_dir: Path
    private_dir: Path
    data_dir: Path
    portal_domain: str
    webapps_root: Path
    portal_audit_storage_file: Path | None = None
    authority_db_file: Path | None = None
    tool_exposure_policy: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        portal_instance_id = _as_text(self.portal_instance_id).lower()
        if not portal_instance_id:
            raise ValueError("portal_instance_id is required")
        portal_domain = _as_text(self.portal_domain).lower()
        if not portal_domain:
            raise ValueError("portal_domain is required")
        object.__setattr__(self, "portal_instance_id", portal_instance_id)
        object.__setattr__(self, "portal_domain", portal_domain)
        object.__setattr__(self, "public_dir", _validate_existing_dir(Path(self.public_dir), env_name="PUBLIC_DIR"))
        object.__setattr__(self, "private_dir", _validate_existing_dir(Path(self.private_dir), env_name="PRIVATE_DIR"))
        object.__setattr__(self, "data_dir", _validate_existing_dir(Path(self.data_dir), env_name="DATA_DIR"))
        object.__setattr__(self, "webapps_root", _validate_existing_dir(Path(self.webapps_root), env_name="MYCITE_WEBAPPS_ROOT"))
        object.__setattr__(self, "portal_audit_storage_file", _validate_optional_path(self.portal_audit_storage_file))
        object.__setattr__(self, "authority_db_file", _normalize_optional_file_path(self.authority_db_file))
        policy = self.tool_exposure_policy
        if policy is None:
            private_config = _load_optional_json_object(Path(self.private_dir) / "config.json")
            policy = private_config.get("tool_exposure")
        object.__setattr__(
            self,
            "tool_exposure_policy",
            build_tool_exposure_policy(
                policy,
                known_tool_ids=[entry.tool_id for entry in build_portal_tool_registry_entries()],
            ),
        )

    @classmethod
    def from_env(cls) -> V2PortalHostConfig:
        return cls(
            portal_instance_id=_required_env_text("PORTAL_INSTANCE_ID"),
            public_dir=Path(_required_env_text("PUBLIC_DIR")),
            private_dir=Path(_required_env_text("PRIVATE_DIR")),
            data_dir=Path(_required_env_text("DATA_DIR")),
            portal_domain=_required_env_text("MYCITE_ANALYTICS_DOMAIN"),
            webapps_root=Path(_required_env_text("MYCITE_WEBAPPS_ROOT")),
            portal_audit_storage_file=Path(_required_env_text("MYCITE_V2_PORTAL_AUDIT_FILE"))
            if _as_text(os.environ.get("MYCITE_V2_PORTAL_AUDIT_FILE"))
            else None,
            authority_db_file=Path(_required_env_text("MYCITE_V2_PORTAL_AUTHORITY_DB"))
            if _as_text(os.environ.get("MYCITE_V2_PORTAL_AUTHORITY_DB"))
            else None,
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "portal_instance_id": self.portal_instance_id,
            "portal_domain": self.portal_domain,
            "public_dir": str(self.public_dir),
            "private_dir": str(self.private_dir),
            "data_dir": str(self.data_dir),
            "webapps_root": str(self.webapps_root),
            "authority_db_file": str(self.authority_db_file) if self.authority_db_file is not None else "",
        }


TOOL_SLUG_TO_SURFACE_ID = {
    "cts-gis": CTS_GIS_TOOL_SURFACE_ID,
    "workbench-ui": WORKBENCH_UI_TOOL_SURFACE_ID,
    "agro-erp": AGRO_ERP_TOOL_SURFACE_ID,
}


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _runtime_status_code(envelope: dict[str, Any]) -> int:
    error = envelope.get("error")
    if not isinstance(error, dict) or not error:
        return 200
    code = _as_text(error.get("code"))
    if code in {"surface_unknown"}:
        return 404
    if code in {
        "data_dir_not_configured",
        "sql_authority_required",
        "sql_authority_uninitialized",
        "sql_portal_authority_missing",
        "sql_publication_summary_missing",
    }:
        return 503
    return 400


_SERVER_TIMING_TOKEN_RE = re.compile(r"[^A-Za-z0-9!#$%&'*+\-.^_`|~]")


def _phase_timings_to_server_timing(phase_timings_ms: dict[str, float] | None) -> str | None:
    if not phase_timings_ms:
        return None
    parts: list[str] = []
    for raw_name, raw_value in phase_timings_ms.items():
        name = _SERVER_TIMING_TOKEN_RE.sub("_", _as_text(raw_name))
        if not name:
            continue
        try:
            duration = float(raw_value)
        except (TypeError, ValueError):
            continue
        parts.append(f"{name};dur={duration:g}")
    if not parts:
        return None
    return ", ".join(parts)


def _phase_timings_from_envelope(envelope: dict[str, Any]) -> dict[str, float] | None:
    surface_payload = envelope.get("surface_payload")
    if not isinstance(surface_payload, dict):
        return None
    diagnostics = surface_payload.get("runtime_diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    timings = diagnostics.get("phase_timings_ms")
    return timings if isinstance(timings, dict) else None


def _runtime_response(envelope: dict[str, Any]) -> tuple[Any, int]:
    if envelope.get("schema") != PORTAL_RUNTIME_ENVELOPE_SCHEMA:
        return (
            jsonify(
                {
                    "schema": V2_PORTAL_ERROR_SCHEMA,
                    "ok": False,
                    "error": {
                        "code": "invalid_runtime_envelope",
                        "message": "The portal runtime returned an invalid envelope.",
                    },
                }
            ),
            502,
        )
    status = _runtime_status_code(envelope)
    server_timing = _phase_timings_to_server_timing(_phase_timings_from_envelope(envelope))
    if server_timing is None:
        return jsonify(envelope), status
    response = make_response(jsonify(envelope), status)
    response.headers["Server-Timing"] = server_timing
    return response, status


def _error_response(code: str, message: str, *, status_code: int = 400) -> tuple[Any, int]:
    return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": code, "message": message}}), status_code


def _check_legacy_maps_error(exc: Exception) -> tuple[Any, int] | None:
    code = _as_text(getattr(exc, "code", ""))
    if code == "legacy_maps_alias_unsupported":
        return _error_response(code, str(exc), status_code=400)
    return None


def _nimm_target_authority(payload: Mapping[str, Any]) -> str:
    envelope_payload = payload.get("nimm_envelope")
    if isinstance(envelope_payload, Mapping):
        from MyCiteV2.packages.state_machine.nimm import NimmDirectiveEnvelope

        envelope = NimmDirectiveEnvelope.from_dict(dict(envelope_payload))
        return _as_text(envelope.directive.target_authority)
    return _as_text(payload.get("target_authority"))


def _render_surface(surface_id: str, host_config: V2PortalHostConfig) -> str:
    from MyCiteV2.packages.state_machine.portal_shell import (
        SANDBOX_DISPLAY_NAMES,
    )
    shell_asset_manifest = build_shell_asset_manifest(PORTAL_BUILD_ID)
    sandbox_display_names = [
        {
            "token": token,
            "label": label,
            "writable": True,
        }
        for token, label in sorted(SANDBOX_DISPLAY_NAMES.items())
    ]
    return render_template(
        "portal.html",
        portal_instance_id=host_config.portal_instance_id,
        host_shape=HOST_SHAPE,
        portal_domain=host_config.portal_domain,
        portal_build_id=PORTAL_BUILD_ID,
        bootstrap_shell_request=_bootstrap_request(
            surface_id,
            portal_instance_id=host_config.portal_instance_id,
            query_params=request.args,
        ),
        runtime_envelope_schema=PORTAL_RUNTIME_ENVELOPE_SCHEMA,
        shell_endpoint="/portal/api/v2/shell",
        shell_loading_label="Loading portal shell…",
        shell_asset_manifest=shell_asset_manifest,
        logo_href="/portal/system",
        sandbox_display_names=sandbox_display_names,
    )


def _warm_system_workbench_projection(config: V2PortalHostConfig) -> None:
    # Pre-warm the datum projection caches. With gunicorn --preload, this runs
    # once in the master process before workers are forked; all workers inherit
    # the warm cache via copy-on-write and pay no per-worker cold-start cost.
    # Without --preload, the first CTS-GIS request per worker pays the cold cost.
    try:
        from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
            read_system_workbench_projection,
        )

        read_system_workbench_projection(
            portal_scope=PortalScope(scope_id=config.portal_instance_id, capabilities=()),
            data_dir=config.data_dir,
            public_dir=config.public_dir,
            authority_db_file=config.authority_db_file,
            authority_mode="sql_primary",
        )
    except Exception:
        pass

    # Warm the workbench READ path too — the catalog deserialization + the default
    # surface projections are the dominant cold cost for a large sandbox (e.g.
    # agro_erp), and read_system_workbench_projection does not exercise it. Doing it
    # here (once, in the --preload master) means every worker — initial and
    # max-requests-recycled — inherits the warm _GLOBAL_CATALOG_CACHE /
    # _GLOBAL_SURFACE_CACHE via copy-on-write and serves the first real request fast.
    try:
        if config.authority_db_file is not None:
            from MyCiteV2.packages.tools.workbench_ui.service import WorkbenchUiReadService

            reader = WorkbenchUiReadService(config.authority_db_file)
            for warm_query in ({}, {"sandbox_filter": "agro_erp"}):
                reader.read_surface(
                    portal_instance_id=config.portal_instance_id,
                    portal_domain="",
                    surface_query=warm_query,
                )
    except Exception:
        pass

    # Register the compiled-artifact root for the thin CTS-GIS tools (deployment
    # config, set once — the map tool reads {data_dir}/payloads/compiled/...).
    try:
        from MyCiteV2.packages.tools._cts_gis_artifact import configure_data_dir

        configure_data_dir(config.data_dir)
    except Exception:
        pass


def _build_health(config: V2PortalHostConfig) -> dict[str, Any]:
    static_dir = Path(__file__).resolve().parent / "static"
    shell_asset_manifest = build_shell_asset_manifest(PORTAL_BUILD_ID)
    static_files = _shell_asset_files_from_manifest(shell_asset_manifest)
    source_freshness = _source_freshness(PORTAL_SOURCE_MTIME_AT_IMPORT)
    static_ok = all((static_dir / name).is_file() for name in static_files)
    return {
        "schema": V2_PORTAL_HEALTH_SCHEMA,
        # A "stale" worker (disk code newer than this worker loaded) is unhealthy:
        # this is the signal a deploy-without-restart needs (the gate curls healthz).
        # "unknown" is non-gating so dependency-light/test layouts don't false-fail.
        "ok": static_ok and source_freshness["status"] != "stale",
        "host_shape": HOST_SHAPE,
        "portal_build_id": PORTAL_BUILD_ID,
        "code_coherence": _code_coherence(PORTAL_BUILD_ID),
        "source_freshness": source_freshness,
        "portal_instance_id": config.portal_instance_id,
        "shell_asset_manifest": shell_asset_manifest,
        "root_routes": [
            "/portal",
            "/portal/system",
            "/portal/network",
            "/portal/utilities",
        ],
        "tool_routes": [f"/portal/system/tools/{slug}" for slug in TOOL_SLUG_TO_SURFACE_ID],
        "shell_endpoint": "/portal/api/v2/shell",
        "tool_exposure": config.tool_exposure_policy,
        "state_roots": config.to_public_dict(),
        "authority_db": {
            "configured": config.authority_db_file is not None,
            "exists": bool(config.authority_db_file and config.authority_db_file.exists()),
            "path": str(config.authority_db_file) if config.authority_db_file is not None else "",
        },
    }


# ---------------------------------------------------------------------------
# FND newsletter subscribe pipeline — helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Path layout under `host_config.private_dir`. Phase 13d follow-up: both the
# newsletter-admin profile glob and the webapps clients root used to be
# hardcoded to /srv/{webapps,mycite-state}; they now derive from the
# V2PortalHostConfig instance so smoke tests can boot the portal against a
# tempdir without monkey-patching module-level constants.
_NEWSLETTER_ADMIN_PROFILE_SUBPATH = Path("utilities/tools/newsletter-admin")


def _newsletter_known_domains(private_dir: Path) -> list[str]:
    """Load known newsletter domains from the newsletter-admin profile directory.

    Reads ``<private_dir>/utilities/tools/newsletter-admin/newsletter-admin.<domain>.json``
    files and returns the deduplicated, sorted list of <domain> tokens.
    """
    admin_dir = Path(private_dir) / _NEWSLETTER_ADMIN_PROFILE_SUBPATH
    domains: list[str] = []
    for path in glob.glob(str(admin_dir / "newsletter-admin.*.json")):
        basename = os.path.basename(path)
        token = basename.removeprefix("newsletter-admin.").removesuffix(".json").strip().lower()
        if token:
            domains.append(token)
    return sorted(set(domains))


def _normalize_domain(host: str) -> str:
    token = (host or "").lower().split(":")[0].strip()
    if token.startswith("www."):
        token = token[4:]
    return token


def _validate_email(value: object) -> str:
    """Normalize and validate an email address. Returns lowercase email or empty string."""
    token = str(value or "").strip().lower()
    if not token or not _EMAIL_RE.match(token):
        return ""
    return token


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _legacy_deprecation_headers(target_authority: str, operation: str) -> dict[str, str]:
    """Return HTTP headers signaling that the legacy ``/__fnd/*`` route
    is a Phase E.3 shim that internally dispatches to the canonical
    ``/portal/api/v2/mutations/*`` runtime.

    Operators relying on these URLs (notably unsubscribe links baked
    into already-sent newsletter emails) should plan a 90-day cutover
    to the canonical route. After zero traffic is observed for that
    window, the route bodies become ``410 Gone`` per Phase F of the
    unification audit.
    """
    return {
        "X-Deprecation": "1",
        "X-Deprecation-Date": "2026-05-13",
        "X-Deprecation-Sunset": "2026-08-13",
        "X-Deprecation-Successor": (
            f"POST /portal/api/v2/mutations/apply "
            f'(target_authority="{target_authority}", operation="{operation}")'
        ),
        "X-Deprecation-Reason": "Phase E.3 routes through the canonical mutation runtime; legacy URL surface retained for backward compatibility (unsubscribe links in customer email archives).",
    }


def _newsletter_state_adapter(host_config: V2PortalHostConfig):
    """Return the live newsletter-state adapter.

    Newsletter + contact-log state lives in JSON under
    ``<private>/utilities/tools/aws-csm/newsletter/`` per the peripheral
    architecture: extensions read grantee/extension JSON files, no MOS
    authority is consulted. This is the single canonical store that every
    contact writer (subscribe, connect, operator admin) also writes to.
    """
    from MyCiteV2.packages.adapters.filesystem import (
        FilesystemNewsletterStateAdapter,
    )

    # webapps_root is DERIVED from private_dir inside the adapter (live layout
    # is <webapps_root>/mycite/<inst>/private) so every adapter built from the
    # same private_dir — including test verification adapters — resolves the
    # SAME contacts leaflet dir. We deliberately do not pass an explicit root.
    return FilesystemNewsletterStateAdapter(host_config.private_dir)


def _fnd_newsletter_request_field(field: str) -> str:
    """Extract a field from JSON body or form data.

    Uses ``force=True`` so a JSON body still parses when the client (or a proxy)
    omitted or rewrote ``Content-Type: application/json`` — otherwise every field
    read empty and a correctly-filled form 400'd as ``invalid_email``. Falls back
    to form-encoded data when the body genuinely isn't JSON.
    """
    data = request.get_json(silent=True, force=True)
    if isinstance(data, dict):
        return str(data.get(field) or "").strip()
    return str(request.form.get(field) or "").strip()


def _connect_response(
    is_json_request: bool,
    *,
    ok: bool,
    status: int,
    **payload: Any,
):
    """Content-negotiate a Connect-form response.

    JSON path: returns ``jsonify({"ok": …, **payload}), status`` exactly
    as the shared connect.js client expects.

    No-JS / form-encoded path: returns a tiny standalone HTML page with
    the same status code, the success/error language users get from
    connect.js, and a link back to the referring contact page. This is
    what visitors with JavaScript disabled see after submitting the form
    with the ``action="/__fnd/connect/submit" method="post"`` fallback.
    """
    body: dict[str, Any] = {"ok": ok}
    body.update(payload)
    if is_json_request:
        return jsonify(body), status
    referrer = request.referrer or "/"
    if ok:
        heading = "Message received — thank you!"
        forward_status = payload.get("forward_status") or ""
        if forward_status in {"pending", "failed"}:
            sub = (
                "We're still routing your message — we'll respond soon."
            )
        else:
            sub = "We'll be in touch."
    else:
        heading = "Could not send your message"
        error = payload.get("error") or "unknown_error"
        sub = {
            "invalid_email": "Please enter a valid email address and try again.",
            "missing_message": "Please include a message and try again.",
            "missing_domain": "We couldn't determine which site you're contacting. Please try again from a regular page link.",
            "storage_error": "Our contact log couldn't be reached. Please try again in a few minutes.",
        }.get(error, "An unexpected error occurred. Please try again.")
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>" + ("Message sent" if ok else "Message not sent")
        + "</title>"
        "<style>"
        "body{font-family:system-ui,-apple-system,sans-serif;"
        "max-width:38rem;margin:4rem auto;padding:0 1.5rem;line-height:1.5;color:#1a1a1a;}"
        "h1{font-size:1.5rem;margin:0 0 0.5rem;}"
        "p{margin:0 0 1rem;}"
        ".back{display:inline-block;margin-top:1rem;}"
        "</style>"
        "</head><body>"
        f"<h1>{heading}</h1>"
        f"<p>{sub}</p>"
        f"<p class=\"back\"><a href=\"{referrer}\">&larr; Back</a></p>"
        "</body></html>"
    )
    response = make_response(html, status)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


# ---------------------------------------------------------------------------
# PayPal order peripheral helpers (peripheral donation routes only)
# ---------------------------------------------------------------------------


def _load_domain_profile(private_dir: Path, domain: str) -> dict[str, Any] | None:
    tool_dir = private_dir / "utilities" / "tools" / "paypal-csm"
    domain_lower = _as_text(domain).lower()
    for path in sorted(glob.glob(str(tool_dir / "paypal-csm.*.json"))):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, dict) and _as_text(payload.get("domain")).lower() == domain_lower:
                return payload
        except Exception:
            continue
    return None


def _load_tenant_config(private_dir: Path, tenant_ref: str) -> dict[str, Any] | None:
    tenant_path = private_dir / "utilities" / "tools" / "paypal-csm" / "tenants" / f"{tenant_ref}.json"
    if not tenant_path.exists():
        return None
    try:
        payload = json.loads(tenant_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _resolve_paypal_credentials(tenant_config: dict[str, Any]) -> tuple[str, str] | None:
    credentials_ref = _as_text(tenant_config.get("credentials_ref"))
    if not credentials_ref or credentials_ref in {"1", "set-locally-in-state-or-runtime"}:
        client_id = _as_text(os.environ.get("PAYPAL_CLIENT_ID"))
        client_secret = _as_text(os.environ.get("PAYPAL_CLIENT_SECRET"))
    else:
        ref_upper = credentials_ref.upper().replace("-", "_")
        client_id = _as_text(os.environ.get(f"PAYPAL_CLIENT_ID_{ref_upper}"))
        client_secret = _as_text(os.environ.get(f"PAYPAL_CLIENT_SECRET_{ref_upper}"))
    if client_id and client_secret:
        return (client_id, client_secret)
    return None


def _paypal_base_url(environment: str) -> str:
    # PaypalConfig only allows {"sandbox", "live"}; legacy callers may pass
    # "production". Treat both live and production as the live endpoint.
    if _as_text(environment).lower() in {"live", "production"}:
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _load_grantee_for_domain(private_dir: Path, domain: str) -> dict[str, Any] | None:
    """Find the first grantee JSON whose domains list contains ``domain``.

    Returns the parsed grantee dict (legacy shape, not the GranteeProfile
    dataclass) or ``None`` if no grantee matches. Matching is case-insensitive.
    """
    if private_dir is None or not domain:
        return None
    domain_lower = _as_text(domain).lower()
    if not domain_lower:
        return None
    try:
        from MyCiteV2.instances._shared.runtime.operational_store import (
            load_grantee_profiles,
        )

        for grantee in load_grantee_profiles(private_dir):
            domains = [_as_text(d).lower() for d in (grantee.get("domains") or [])]
            if domain_lower in domains:
                return grantee
    except Exception:
        return None
    return None


def _resolve_paypal_credentials_for_domain(
    private_dir: Path,
    domain: str,
    tenant_config: dict[str, Any],
) -> tuple[str, str, str] | None:
    """Return ``(client_id, client_secret, environment)`` resolved for a domain.

    Precedence:
      1. The grantee JSON whose ``domains`` list contains the request
         domain. Wins iff both ``paypal.client_id`` and ``paypal.client_secret``
         are non-empty. ``paypal.environment`` (sandbox|live) is returned alongside.
      2. The env-var fallback resolved by ``_resolve_paypal_credentials``.
         When this path is taken, environment is left empty so callers
         keep falling back to the domain profile's declared environment.

    Returns ``None`` when neither source supplies credentials. Callers map
    that to HTTP 503 ``credentials_not_set``.
    """
    grantee = _load_grantee_for_domain(private_dir, domain)
    if grantee:
        paypal_cfg = grantee.get("paypal") if isinstance(grantee.get("paypal"), dict) else {}
        client_id = _as_text(paypal_cfg.get("client_id"))
        client_secret = _as_text(paypal_cfg.get("client_secret"))
        if client_id and client_secret:
            environment = _as_text(paypal_cfg.get("environment")) or "sandbox"
            return (client_id, client_secret, environment)

    env_credentials = _resolve_paypal_credentials(tenant_config)
    if env_credentials is not None:
        client_id, client_secret = env_credentials
        return (client_id, client_secret, "")
    return None


_RECEIPT_DOCUMENT_PARENT = Path("/srv/webapps/clients/_shared/site-core/document")


def _resolve_receipt_artifact(private_dir: Path, domain: str) -> Path | None:
    """Resolve the receipt PDF for a domain or ``None`` if not configured.

    Reads ``donation_defaults.receipt_artifact_path`` from the domain profile,
    joins it under the fixed shared-document parent, and verifies the
    resolved path stays within that parent and exists on disk. Any traversal
    attempt or missing file collapses to ``None`` so callers can return 404
    without leaking validation signal.
    """
    if private_dir is None or not domain:
        return None
    domain_profile = _load_domain_profile(private_dir, domain)
    if not domain_profile:
        return None
    donation_defaults = domain_profile.get("donation_defaults")
    if not isinstance(donation_defaults, dict):
        return None
    artifact_path = _as_text(donation_defaults.get("receipt_artifact_path"))
    if not artifact_path:
        return None
    try:
        parent = _RECEIPT_DOCUMENT_PARENT.resolve()
        candidate = (parent / artifact_path).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(parent)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _find_create_order_entry(orders_log: Path, order_id: str) -> dict[str, Any] | None:
    """Locate the create_order log entry for a given order_id.

    Scans ``orders.ndjson`` from newest to oldest and returns the first
    matching entry (``event == "create_order"`` and matching ``order_id``).
    Used by the capture handler to recover donor metadata persisted at
    create-time so receipt emails go to the original donor, not whatever
    address an attacker might supply in the capture payload.
    """
    if not order_id:
        return None
    try:
        if not orders_log.exists():
            return None
        lines = orders_log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    target = _as_text(order_id)
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if _as_text(entry.get("event")) != "create_order":
            continue
        if _as_text(entry.get("order_id")) == target:
            return entry
    return None


def _find_completed_capture_entry(orders_log: Path, order_id: str) -> dict[str, Any] | None:
    """Return a prior COMPLETED ``capture_order`` log entry for ``order_id``.

    Lets the capture path be idempotent: a retry / double-click / webhook+browser
    race returns the already-recorded capture instead of re-calling PayPal, which
    would 502 ``ORDER_ALREADY_CAPTURED`` for a donor who actually paid.
    """
    if not order_id:
        return None
    try:
        if not orders_log.exists():
            return None
        lines = orders_log.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    target = _as_text(order_id)
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if _as_text(entry.get("event")) != "capture_order":
            continue
        if _as_text(entry.get("order_id")) != target:
            continue
        if _as_text(entry.get("status")).upper() == "COMPLETED":
            return entry
    return None


def _send_donation_receipt_email(
    *,
    private_dir: Path,
    domain: str,
    donor_email: str,
    donor_name: str,
    amount: str,
    currency_code: str,
    capture_id: str,
    receipt_path: Path | None = None,
) -> str:
    """Email a simple compliant donation acknowledgement to the donor via SES.

    The body is the donor's tax-records receipt: a thank-you with the amount
    and date, the org's legal identity (legal name, tax status + EIN) and
    mailing address when configured on ``grantee.receipt`` (``ReceiptConfig``),
    the standard "no goods or services" acknowledgement statement, and an
    optional authorized-signer sign-off. It is NOT the FND↔grantee
    sales-tax-exempt certificate — that vendor document never goes to donors.

    A PDF attachment is OPTIONAL: when ``receipt_path`` is given and readable it
    is attached, but a missing/unreadable PDF never withholds the receipt.

    Returns:
      - ``"sent"`` on successful SES dispatch
      - ``"skipped"`` when grantee.aws_ses is unconfigured or donor_email empty
      - ``"failed"`` when SES raises (capture response is unaffected)
    """
    if not donor_email:
        return "skipped"
    grantee = _load_grantee_for_domain(private_dir, domain)
    aws_cfg = grantee.get("aws_ses") if grantee and isinstance(grantee.get("aws_ses"), dict) else {}
    ses_identity = _as_text(aws_cfg.get("identity"))
    if not ses_identity:
        return "skipped"
    receipt_cfg = grantee.get("receipt") if grantee and isinstance(grantee.get("receipt"), dict) else {}

    import email.utils
    import time as _time
    from email.message import EmailMessage

    display_amount = f"{amount} {currency_code}".strip()
    org_label = _as_text(grantee.get("label")) if grantee else ""
    legal_name = _as_text(receipt_cfg.get("legal_name"))
    org_for_display = legal_name or org_label or domain
    salutation = f", {donor_name}" if donor_name else ""
    donation_date = _time.strftime("%B %-d, %Y", _time.gmtime())

    # Org legal-identity line, e.g. "<legal_name> is a 501(c)(3) tax-exempt
    # organization (EIN 12-3456789)." — assembled only from configured fields.
    ein = _as_text(receipt_cfg.get("ein"))
    tax_status = _as_text(receipt_cfg.get("tax_status")) or "501(c)(3)"
    mailing_address = _as_text(receipt_cfg.get("mailing_address"))
    statement = (
        _as_text(receipt_cfg.get("acknowledgement_statement"))
        or "No goods or services were provided in exchange for this contribution."
    )
    signer_name = _as_text(receipt_cfg.get("signer_name"))
    signer_title = _as_text(receipt_cfg.get("signer_title"))

    identity_line = ""
    if legal_name:
        ein_suffix = f" (EIN {ein})" if ein else ""
        identity_line = f"{legal_name} is a {tax_status} tax-exempt organization{ein_suffix}."
    signoff = ""
    if signer_name:
        signoff = signer_name + (f", {signer_title}" if signer_title else "")

    # Plain-text body kept verbatim with the HTML alternative below —
    # multipart/alternative divergence detection (Gmail) penalizes
    # parts whose visible content diverges.
    text_lines = [
        f"Thank you{salutation}, for your {display_amount} contribution"
        f" to {org_for_display} on {donation_date}.",
        "",
        statement,
    ]
    if identity_line:
        text_lines += ["", identity_line]
    if mailing_address:
        text_lines += ["", mailing_address]
    text_lines += ["", f"Confirmation / capture ID: {capture_id}"]
    if signoff:
        text_lines += ["", signoff]
    body_text = "\n".join(text_lines) + "\n"

    # A6: HTML alternative. Inline styles only — no <link> / <script> /
    # web fonts. Same wording as the plain-text part.
    import html as _html
    html_parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<title>Donation receipt</title></head>'
        '<body style="font-family:Georgia,serif;max-width:600px;'
        'margin:0 auto;padding:24px;color:#222;line-height:1.5;">',
        f'<p>Thank you{_html.escape(salutation)}, for your '
        f'<strong>{_html.escape(display_amount)}</strong> contribution to '
        f'<strong>{_html.escape(org_for_display)}</strong> on '
        f'{_html.escape(donation_date)}.</p>',
        f'<p>{_html.escape(statement)}</p>',
    ]
    if identity_line:
        html_parts.append(f'<p>{_html.escape(identity_line)}</p>')
    if mailing_address:
        html_parts.append(
            f'<p style="color:#444;">{_html.escape(mailing_address).replace(chr(10), "<br>")}</p>'
        )
    html_parts.append(
        f'<p style="color:#666;font-size:0.9em;">Confirmation / capture ID: '
        f'<code>{_html.escape(capture_id)}</code></p>'
    )
    if signoff:
        html_parts.append(f'<p style="color:#444;">{_html.escape(signoff)}</p>')
    html_parts.append('</body></html>')
    body_html = "".join(html_parts)

    from_address = _as_text(aws_cfg.get("from_address")) or ses_identity
    from_name = _as_text(aws_cfg.get("from_name"))
    from_domain = from_address.rsplit("@", 1)[-1].strip() if "@" in from_address else ""
    msg = EmailMessage()
    msg["Subject"] = f"Donation receipt — {org_for_display}"
    msg["From"] = f'"{from_name}" <{from_address}>' if from_name else from_address
    msg["To"] = donor_email
    # A4: always-on Reply-To. Default to reply-to@<from_domain> when the
    # grantee aws_ses doesn't set one.
    reply_to = _as_text(aws_cfg.get("reply_to"))
    if not reply_to and from_domain:
        reply_to = f"reply-to@{from_domain}"
    if reply_to:
        msg["Reply-To"] = reply_to
    # A5 (donation path bypasses send_email's auto-injection): explicit
    # domain-anchored Message-ID + RFC 2822 GMT Date so spam filters don't
    # see process-hostname Message-IDs.
    msg["Message-ID"] = (
        email.utils.make_msgid(domain=from_domain)
        if from_domain
        else email.utils.make_msgid()
    )
    msg["Date"] = email.utils.formatdate(usegmt=True)
    msg.set_content(body_text)
    # A6: HTML alternative makes the receipt render as multipart/alternative.
    msg.add_alternative(body_html, subtype="html")
    # Optional PDF attachment. A missing or unreadable PDF NEVER withholds the
    # receipt — the acknowledgement above is self-contained.
    if receipt_path is not None:
        try:
            pdf_bytes = receipt_path.read_bytes()
            msg.add_attachment(
                pdf_bytes,
                maintype="application",
                subtype="pdf",
                filename=receipt_path.name,
            )
        except OSError as exc:
            _log.warning(
                "donation_receipt_pdf_unreadable",
                extra={"domain": domain, "capture_id": capture_id, "path": str(receipt_path), "err": str(exc)},
            )
    try:
        _aws_peripheral.send_raw_email(
            aws_ses_profile=aws_cfg,
            destinations=[donor_email],
            raw_message_bytes=msg.as_bytes(),
        )
    except SesSendError as exc:
        _log.error(
            "donation_receipt_ses_failed",
            extra={
                "domain": domain,
                "capture_id": capture_id,
                "aws_error_code": exc.aws_error_code,
                "aws_request_id": exc.aws_request_id,
                "reason": exc.reason,
            },
        )
        return "failed"
    return "sent"


def _get_paypal_access_token(client_id: str, client_secret: str, base_url: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        f"{base_url}/v1/oauth2/token",
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    return _as_text(result.get("access_token"))


def _create_paypal_order(*, access_token: str, base_url: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST a checkout-order create request and return the parsed response.

    Extracted from the route handler so smoke tests can monkey-patch
    ``urllib.request.urlopen`` (or this function) and exercise the flow
    against a tempdir without hitting PayPal. Real prod path is unchanged.
    """
    req = urllib.request.Request(
        f"{base_url}/v2/checkout/orders",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _capture_paypal_order(*, access_token: str, base_url: str, order_id: str) -> dict[str, Any]:
    """POST a checkout-order capture request and return the parsed response.

    Sibling of ``_create_paypal_order``; same testability rationale.
    """
    req = urllib.request.Request(
        f"{base_url}/v2/checkout/orders/{order_id}/capture",
        data=b"{}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _verify_paypal_webhook_signature(
    *,
    access_token: str,
    base_url: str,
    headers: Any,
    webhook_id: str,
    event_body: dict[str, Any],
) -> bool:
    """Verify a PayPal webhook via the verify-webhook-signature API.

    PayPal signs each webhook; we replay the transmission headers + our
    configured ``webhook_id`` + the raw event to PayPal and trust the event
    only when ``verification_status == "SUCCESS"``. Any error → not verified.
    """
    def _h(name: str) -> str:
        return _as_text(headers.get(name))

    payload = {
        "auth_algo": _h("Paypal-Auth-Algo"),
        "cert_url": _h("Paypal-Cert-Url"),
        "transmission_id": _h("Paypal-Transmission-Id"),
        "transmission_sig": _h("Paypal-Transmission-Sig"),
        "transmission_time": _h("Paypal-Transmission-Time"),
        "webhook_id": webhook_id,
        "webhook_event": event_body,
    }
    req = urllib.request.Request(
        f"{base_url}/v1/notifications/verify-webhook-signature",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except Exception:
        return False
    return _as_text(result.get("verification_status")).upper() == "SUCCESS"


# PayPal webhook events the donation reconciler verifies + handles. The
# auto-provisioner subscribes a created webhook to exactly these.
_PAYPAL_WEBHOOK_EVENT_TYPES = ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED")


class _PaypalWebhookError(Exception):
    """A PayPal webhook-create failure carrying PayPal's error ``name``.

    ``name`` lets the caller distinguish a recoverable
    ``WEBHOOK_URL_ALREADY_EXISTS`` from a fatal error.
    """

    def __init__(self, name: str, detail: str = "") -> None:
        super().__init__(name)
        self.name = name
        self.detail = detail


def _list_paypal_webhooks(*, access_token: str, base_url: str) -> list[dict[str, Any]]:
    """Return the REST app's registered webhooks (``[]`` on any error).

    Used to make provisioning idempotent — an existing webhook whose URL
    matches is reused rather than creating a forbidden duplicate.
    """
    req = urllib.request.Request(
        f"{base_url}/v1/notifications/webhooks",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
    except Exception:
        return []
    webhooks = result.get("webhooks")
    return webhooks if isinstance(webhooks, list) else []


def _create_paypal_webhook(
    *, access_token: str, base_url: str, url: str, event_types: tuple[str, ...]
) -> dict[str, Any]:
    """Create a webhook for ``url`` subscribed to ``event_types``.

    PayPal expects ``event_types`` as a list of objects (``[{"name": ...}]``),
    not bare strings. Raises ``_PaypalWebhookError`` (with PayPal's error
    ``name``) on a non-2xx so the caller can recover or surface it.
    """
    body = {"url": url, "event_types": [{"name": name} for name in event_types]}
    req = urllib.request.Request(
        f"{base_url}/v1/notifications/webhooks",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode()
        except Exception:
            detail = ""
        try:
            name = _as_text(json.loads(detail).get("name"))
        except Exception:
            name = ""
        raise _PaypalWebhookError(name or "http_error", detail) from exc


def _webhook_url_matches(candidate: str, target: str) -> bool:
    def _norm(value: str) -> str:
        return _as_text(value).strip().rstrip("/").lower()

    return _norm(candidate) == _norm(target)


def _find_or_create_paypal_webhook(
    *, access_token: str, base_url: str, url: str, event_types: tuple[str, ...]
) -> tuple[str, str]:
    """Idempotently ensure a webhook exists for ``url``. Returns ``(id, url)``.

    Lists first and reuses a URL match (PayPal forbids duplicate URLs); only
    creates when none matches. If creation raises
    ``WEBHOOK_URL_ALREADY_EXISTS`` (the list endpoint can lag a fresh write),
    re-list and return the now-visible match.
    """
    for hook in _list_paypal_webhooks(access_token=access_token, base_url=base_url):
        if _webhook_url_matches(_as_text(hook.get("url")), url):
            return _as_text(hook.get("id")), _as_text(hook.get("url")) or url
    try:
        created = _create_paypal_webhook(
            access_token=access_token, base_url=base_url, url=url, event_types=event_types
        )
        return _as_text(created.get("id")), _as_text(created.get("url")) or url
    except _PaypalWebhookError as exc:
        if exc.name == "WEBHOOK_URL_ALREADY_EXISTS":
            for hook in _list_paypal_webhooks(access_token=access_token, base_url=base_url):
                if _webhook_url_matches(_as_text(hook.get("url")), url):
                    return _as_text(hook.get("id")), _as_text(hook.get("url")) or url
        raise


def _ndjson_has_capture(orders_log: Path, capture_id: str) -> bool:
    """True if a capture_order/webhook_capture row with ``capture_id`` exists.

    Used to make webhook reconciliation idempotent — a capture already
    recorded by the browser flow (or a duplicate webhook) is not re-logged.
    """
    capture_id = _as_text(capture_id)
    if not capture_id or not orders_log.exists():
        return False
    try:
        for line in orders_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if _as_text(row.get("capture_id")) == capture_id:
                return True
    except OSError:
        return False
    return False


def _ndjson_has_receipt_sent(orders_log: Path, capture_id: str) -> bool:
    """True if a ``receipt_email`` row with status ``sent`` exists for ``capture_id``.

    Lets the receipt send be idempotent across the browser capture path and the
    webhook reconciler: once a donor has been emailed their acknowledgement for a
    capture, neither path re-sends. A prior ``skipped``/``failed`` does NOT block a
    later attempt (the webhook may succeed where the browser was unconfigured).
    """
    capture_id = _as_text(capture_id)
    if not capture_id or not orders_log.exists():
        return False
    try:
        for line in orders_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if (
                _as_text(row.get("event")) == "receipt_email"
                and _as_text(row.get("capture_id")) == capture_id
                and _as_text(row.get("status")) == "sent"
            ):
                return True
    except OSError:
        return False
    return False


def _send_receipt_for_capture(
    *,
    private_dir: Path,
    domain: str,
    orders_log: Path,
    order_id: str,
    capture_id: str,
    amount: str,
    currency_code: str,
    donor_email: str = "",
    donor_name: str = "",
) -> str:
    """Send the donor acknowledgement once per capture and log the outcome.

    Shared by the browser capture route and both webhook branches so every
    COMPLETED donation — browser-returned or webhook-reconciled — gets exactly
    one receipt. Deduped on ``capture_id`` (only a prior ``sent`` short-circuits).
    Donor identity is recovered from the create-order row when not supplied; the
    PDF artifact is optional. Returns the email status (``sent``/``skipped``/
    ``failed``/``duplicate``).
    """
    if not capture_id:
        return "skipped"
    if _ndjson_has_receipt_sent(orders_log, capture_id):
        return "duplicate"
    if not donor_email or not donor_name:
        create_entry = _find_create_order_entry(orders_log, order_id) or {}
        donor_email = donor_email or _as_text(create_entry.get("donor_email"))
        donor_name = donor_name or _as_text(create_entry.get("donor_name"))
    # PDF is optional — a configured artifact is attached, its absence never
    # withholds the receipt.
    receipt_path = _resolve_receipt_artifact(private_dir, domain)
    import time as _time

    email_status = _send_donation_receipt_email(
        private_dir=private_dir,
        domain=domain,
        donor_email=donor_email,
        donor_name=donor_name,
        amount=amount,
        currency_code=currency_code,
        capture_id=capture_id,
        receipt_path=receipt_path,
    )
    _append_to_ndjson(orders_log, {
        "event": "receipt_email",
        "order_id": order_id,
        "capture_id": capture_id,
        "domain": domain,
        "donor_email": donor_email,
        "status": email_status,
        "timestamp_ms": int(_time.time() * 1000),
    })
    return email_status


def _append_to_ndjson(path: Path, record: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Durable single-line append: write the whole line then flush + fsync so a
        # captured payment is on disk before we return (a torn/lost tail line would
        # mean a captured-but-unrecorded order). Append stays atomic per line.
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        # A swallowed write here means a captured payment (or other event) goes
        # unrecorded — surface it so a captured-but-unlogged order is detectable.
        _log.exception(
            "ndjson_append_failed",
            extra={"path": str(path), "event": record.get("event")},
        )


def create_app(config: V2PortalHostConfig | None = None) -> Flask:
    if _FLASK_IMPORT_ERROR is not None:
        raise ModuleNotFoundError("flask is required to create the portal host") from _FLASK_IMPORT_ERROR
    host_config = config or V2PortalHostConfig.from_env()
    host_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(host_dir / "templates"),
        static_folder=str(host_dir / "static"),
        static_url_path="/portal/static",
    )
    app.config["MYCITE_V2_PORTAL_HOST_CONFIG"] = host_config
    _warm_system_workbench_projection(host_config)

    @app.get("/healthz")
    @app.get("/portal/healthz")
    def healthz() -> tuple[Any, int]:
        payload = _build_health(host_config)
        return jsonify(payload), 200 if payload["ok"] else 503

    @app.get("/portal")
    def portal_root() -> Any:
        return redirect("/portal/system", code=302)

    @app.get("/portal/system")
    def portal_system_root() -> str:
        return _render_surface(SYSTEM_ROOT_SURFACE_ID, host_config)

    @app.get("/portal/system/tools/<tool_slug>")
    def portal_system_tool(tool_slug: str) -> Any:
        # The FND-CSM tool surface is removed; its functionality moved to the
        # Utilities extensions. Keep a literal bookmark redirect.
        if tool_slug == "fnd-csm":
            return redirect("/portal/utilities/extensions", code=302)
        # Plan v2: the dedicated tool surfaces collapse into the unified
        # workbench at /portal/system. Old bookmarks 302 to the new shape,
        # PRESERVING + canonicalizing the incoming workbench query (document,
        # mode, row, ...) so a deep-linked document is not dropped on redirect:
        #   - workbench-ui → /portal/system?<canonical query>
        #   - agro-erp     → /portal/system?sandbox_filter=agro_erp&<canonical>
        #   - cts-gis      → /portal/system?tools=cts_gis&<canonical>
        #     (the `tool` key below is canonicalized to the plural `tools`)
        _tool_redirect_extra = {
            "workbench-ui": {},
            "agro-erp": {"sandbox_filter": "agro_erp"},
            "cts-gis": {"tool": "cts_gis"},
        }
        if tool_slug in _tool_redirect_extra:
            from MyCiteV2.packages.state_machine.portal_shell import (
                canonical_query_for_surface_query,
            )

            merged = dict(request.args)
            merged.update(_tool_redirect_extra[tool_slug])
            canonical = canonical_query_for_surface_query(
                merged, surface_id=WORKBENCH_UI_TOOL_SURFACE_ID
            )
            target = "/portal/system"
            if canonical:
                target = target + "?" + urllib.parse.urlencode(canonical)
            return redirect(target, code=302)
        surface_id = TOOL_SLUG_TO_SURFACE_ID.get(tool_slug)
        if surface_id is None:
            abort(404)
        return _render_surface(surface_id, host_config)

    @app.get("/portal/network")
    def portal_network() -> str:
        return _render_surface(NETWORK_ROOT_SURFACE_ID, host_config)

    @app.get("/portal/utilities")
    def portal_utilities_root() -> str:
        return _render_surface(UTILITIES_ROOT_SURFACE_ID, host_config)

    # Phase 14b: four dedicated surfaces under Utilities. The old
    # /tool-exposure and /integrations routes 302-redirect for one
    # transition cycle so external bookmarks keep resolving.
    @app.get("/portal/utilities/extensions")
    def portal_utilities_extensions() -> str:
        return _render_surface(UTILITIES_EXTENSIONS_SURFACE_ID, host_config)

    @app.get("/portal/utilities/grantee-profile")
    def portal_utilities_grantee_profile() -> str:
        return _render_surface(UTILITIES_GRANTEE_PROFILE_SURFACE_ID, host_config)

    @app.get("/portal/utilities/tools")
    def portal_utilities_tools() -> str:
        return _render_surface(UTILITIES_TOOLS_SURFACE_ID, host_config)

    @app.get("/portal/utilities/peripherals")
    def portal_utilities_peripherals() -> str:
        return _render_surface(UTILITIES_PERIPHERALS_SURFACE_ID, host_config)

    @app.get("/portal/utilities/tool-exposure")
    def portal_utilities_tool_exposure_legacy() -> Any:
        # Phase 14b: tool-exposure conflated tools + extensions + grantee
        # profile + workbench_ui into one confusing table. Operators are now
        # routed to the dedicated extensions surface. Kept as a redirect for
        # one cycle so external bookmarks still resolve.
        return redirect("/portal/utilities/extensions", code=302)

    @app.get("/portal/utilities/integrations")
    def portal_utilities_integrations_legacy() -> Any:
        # Phase 14b: integrations surface had no operator-actionable
        # content. Redirected to the new peripherals landing.
        return redirect("/portal/utilities/peripherals", code=302)

    @app.get("/portal/api/tools/eligible")
    def portal_tools_eligible() -> tuple[Any, int]:
        # Phase 3 (portal_tool_surface_contract.md): the palette UI calls this
        # endpoint with the currently-selected datum's document_id and
        # datum_address, and receives the subset of tool registry entries
        # whose applies_to_archetype / applies_to_source_kind matches.
        from MyCiteV2.instances._shared.datum_store_accessor import (
            _datum_store_for_authority_db,
        )
        from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
            build_eligible_tools_response,
        )

        document_id = _as_text(request.args.get("document_id"))
        datum_address = _as_text(request.args.get("datum_address"))
        tenant_id = _as_text(request.args.get("tenant_id")) or host_config.portal_instance_id
        datum_store = _datum_store_for_authority_db(host_config.authority_db_file)
        payload = build_eligible_tools_response(
            tenant_id=tenant_id,
            document_id=document_id,
            datum_address=datum_address,
            datum_store=datum_store,
        )
        return jsonify(payload), 200

    @app.get("/portal/api/lenses")
    def portal_lenses_catalog() -> tuple[Any, int]:
        # Lens management: the built-in lens catalog (id / label / description /
        # bindings) + each lens's current enabled state, for the Utilities → Lenses
        # surface and the Control-Panel toggles. See docs/wiki/81.
        from MyCiteV2.instances._shared.runtime.portal_lens_runtime import (
            build_lens_catalog_response,
        )

        return jsonify(build_lens_catalog_response(host_config.private_dir)), 200

    @app.post("/portal/api/lenses/toggle")
    def portal_lenses_toggle() -> tuple[Any, int]:
        # Control-Panel toggle: enable/disable one lens. A disabled lens falls back
        # to the identity passthrough in the workbench render path.
        from MyCiteV2.instances._shared.runtime.portal_lens_runtime import set_lens_enabled

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        body = request.get_json(silent=True) or {}
        lens_id = _as_text(body.get("lens_id"))
        if not lens_id:
            return jsonify({"ok": False, "error": "lens_id_required"}), 400
        enabled = bool(body.get("enabled", True))
        try:
            payload = set_lens_enabled(host_config.private_dir, lens_id=lens_id, enabled=enabled)
        except ValueError as exc:
            return jsonify({"ok": False, "error": "unknown_lens", "detail": str(exc)}), 400
        return jsonify({"ok": True, **payload}), 200

    @app.get("/portal/api/visualizers/for-sandbox")
    def portal_visualizers_for_sandbox() -> tuple[Any, int]:
        # Search-bar discovery: return the visualizers eligible for the contents
        # of a whole sandbox (ranked by reach), plus the document + sandbox lists.
        # Unlike /portal/api/tools/eligible (which answers "tools for THIS doc"),
        # this answers "what can I view in this sandbox?" for the menubar search.
        from MyCiteV2.instances._shared.datum_store_accessor import (
            _datum_store_for_authority_db,
        )
        from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
            build_sandbox_visualizers_response,
        )

        sandbox_id = _as_text(request.args.get("sandbox_id"))
        tenant_id = _as_text(request.args.get("tenant_id")) or host_config.portal_instance_id
        datum_store = _datum_store_for_authority_db(host_config.authority_db_file)
        payload = build_sandbox_visualizers_response(
            tenant_id=tenant_id,
            sandbox_id=sandbox_id,
            datum_store=datum_store,
        )
        return jsonify(payload), 200

    @app.post("/portal/api/resources/upload")
    def portal_resources_upload() -> tuple[Any, int]:
        # Wave-1 backend: operator uploads a site-core gallery artifact
        # (icon/image/document/profile). Raster images are forced to AVIF.
        # The Wave-2 UI adds the upload form + manifest-add affordance; this
        # route is the pure POST handler. Gated by the nginx /portal oauth
        # block — never publicly exposed.
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resource_upload,
        )

        upload = request.files.get("file")
        if upload is None:
            return jsonify({"ok": False, "error": "file_required"}), 400
        file_bytes = upload.read()

        def _field(name: str) -> str:
            return _as_text(request.form.get(name))

        try:
            result = resource_upload.handle_upload(
                file_bytes,
                upload.filename or "",
                _field("kind"),
                title=_field("title"),
                slug=_field("slug"),
                given_name=_field("given_name"),
                owner=_field("owner"),
                webapps_root=host_config.webapps_root,
            )
        except resource_upload.UploadError as exc:
            return jsonify({"ok": False, "error": "invalid_upload", "detail": str(exc)}), 400
        except Exception:  # pragma: no cover - unexpected backend failure
            _log.exception("resource upload failed")
            return jsonify({"ok": False, "error": "upload_failed"}), 500
        return (
            jsonify(
                {
                    "ok": True,
                    "asset_id": result["asset_id"],
                    "asset_path": result["asset_path"],
                    "gallery": result["gallery"],
                }
            ),
            200,
        )

    # ---- Resources extension (ext_resources) backend ------------------
    # Operator-scoped, behind the nginx ^~ /portal + /__fnd oauth blocks.
    # These power the resources extension's profiles contact-app (view +
    # edit + live propagation), icon dedup, and add-to-manifest affordances.
    @app.get("/__fnd/resources/profile/detail")
    def fnd_resources_profile_detail() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        slug = _as_text(request.args.get("slug"))
        if not slug:
            return jsonify({"ok": False, "error": "slug_required"}), 400
        detail = resources_extension.profile_detail(host_config.webapps_root, slug)
        if detail is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404
        # The component-library edit form (shared form system) + a read-only
        # view of every field. The JS renders the form on the right pane.
        edit_frame = resources_extension.build_profile_edit_frame(
            host_config.webapps_root, slug
        )
        return jsonify({"ok": True, "profile": detail, "edit_frame": edit_frame}), 200

    @app.get("/__fnd/resources/leaflets")
    def fnd_resources_leaflets() -> tuple[Any, int]:
        """The full flat leaflet index as JSON, so the library can refresh its
        list after a mutation WITHOUT a full shell reload (preserving the
        operator's facet selections + open detail)."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        leaflets = resources_extension.build_leaflet_index(host_config.webapps_root)
        return jsonify({"ok": True, "leaflets": leaflets}), 200

    @app.post("/__fnd/resources/profile/save")
    def fnd_resources_profile_save() -> tuple[Any, int]:
        """Persist edits to a canonical site-core profile, then re-derive the
        per-site excerpt(s) and rebuild the owning site so the change reaches
        the live page (the gap the operator hit with Nathan Seals)."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        slug = _as_text(payload.get("slug"))
        fields = payload.get("fields")
        if not slug or not isinstance(fields, dict):
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        saved = resources_extension.save_profile(host_config.webapps_root, slug, fields)
        if not saved.get("ok"):
            return jsonify(saved), 400 if saved.get("error") == "profile_not_found" else 500
        # Propagate to per-site excerpts + rebuild. Best-effort: a propagation
        # failure does not undo the canonical save, but is reported so the
        # operator knows the live page may lag.
        rebuild = bool(payload.get("rebuild", True))
        propagation = resources_extension.propagate_profile(
            host_config.webapps_root, slug, rebuild=rebuild
        )
        return jsonify({"ok": True, "saved": saved, "propagation": propagation}), 200

    @app.get("/__fnd/resources/icon/duplicates")
    def fnd_resources_icon_duplicates() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        groups = resources_extension.icon_duplicate_groups(host_config.webapps_root)
        return jsonify({"ok": True, "groups": groups}), 200

    @app.post("/__fnd/resources/icon/dedup")
    def fnd_resources_icon_dedup() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        filename = _as_text(payload.get("filename"))
        if not filename:
            return jsonify({"ok": False, "error": "filename_required"}), 400
        result = resources_extension.remove_icon_duplicate(
            host_config.webapps_root, filename
        )
        return jsonify(result), 200 if result.get("ok") else 409

    @app.post("/__fnd/resources/manifest/add")
    def fnd_resources_manifest_add() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        result = resources_extension.add_asset_to_manifest(
            host_config.webapps_root,
            site=_as_text(payload.get("site")),
            kind=_as_text(payload.get("kind")),
            asset_id=_as_text(payload.get("asset_id")),
            asset_path=_as_text(payload.get("asset_path")),
            entity_scope=_as_text(payload.get("entity_scope")),
        )
        return jsonify(result), 200 if result.get("ok") else 400

    @app.post("/__fnd/resources/manifest/remove")
    def fnd_resources_manifest_remove() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        result = resources_extension.remove_asset_from_manifest(
            host_config.webapps_root,
            site=_as_text(payload.get("site")),
            kind=_as_text(payload.get("kind")),
            asset_path=_as_text(payload.get("asset_path")),
        )
        return jsonify(result), 200 if result.get("ok") else 400

    @app.get("/__fnd/resources/gallery")
    def fnd_resources_gallery() -> tuple[Any, int]:
        """Lazy-load one managed gallery's slug-grouped contents."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        gallery = _as_text(request.args.get("gallery"))
        if gallery not in resources_extension.MANAGED_GALLERIES:
            return jsonify({"ok": False, "error": "unknown_gallery"}), 400
        grouped = resources_extension.build_grouped_gallery(
            host_config.webapps_root, gallery
        )
        return jsonify({"ok": True, "gallery": grouped}), 200

    @app.post("/__fnd/resources/asset/retitle")
    def fnd_resources_asset_retitle() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        result = resources_extension.retitle_asset(
            host_config.webapps_root,
            _as_text(payload.get("gallery")),
            _as_text(payload.get("filename")),
            _as_text(payload.get("new_asset_id")),
        )
        return jsonify(result), 200 if result.get("ok") else 400

    @app.post("/__fnd/resources/asset/rename-slug")
    def fnd_resources_asset_rename_slug() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        result = resources_extension.rename_slug(
            host_config.webapps_root,
            _as_text(payload.get("gallery")),
            _as_text(payload.get("old_slug")),
            _as_text(payload.get("new_slug")),
        )
        if result.get("ok"):
            return jsonify(result), 200
        # collision / in_use / site_entity_slug are conflicts; others are 400.
        conflict = result.get("error") in {"collision", "in_use", "site_entity_slug"}
        return jsonify(result), 409 if conflict else 400

    @app.post("/__fnd/resources/asset/rename-preview")
    def fnd_resources_asset_rename_preview() -> tuple[Any, int]:
        """Dry-run the profile slug-rename cascade: return the change-set
        (excerpts/related/FND refs/data files/sites) WITHOUT mutating anything,
        so the UI can show the operator the impact before applying."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        result = resources_extension.cascade_rename_profile_slug(
            host_config.webapps_root,
            _as_text(payload.get("old_slug")),
            _as_text(payload.get("new_slug")),
            apply=False,
        )
        if result.get("ok"):
            return jsonify(result), 200
        conflict = result.get("error") in {"collision", "site_entity_slug"}
        return jsonify(result), 409 if conflict else 400

    @app.post("/__fnd/resources/asset/delete")
    def fnd_resources_asset_delete() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        payload = _json_payload()
        result = resources_extension.delete_asset_if_unreferenced(
            host_config.webapps_root,
            _as_text(payload.get("gallery")),
            _as_text(payload.get("filename")),
        )
        if result.get("ok"):
            return jsonify(result), 200
        # An asset in use by a site is a conflict, not a bad request.
        return jsonify(result), 409 if result.get("error") == "referenced" else 400

    # ---- Email health surface -----------------------------------------
    # Operator-facing view of the email stack (forwarder routes + DNS/SES
    # deliverability) so a silent outage like the 11-day forwarder drop is
    # VISIBLE from the portal, not just announced by the daily SES alert.
    # Reuses the same checks as the email-health-audit timer. Gated by the
    # oauth2-proxy ^~ /portal block in nginx — never publicly exposed.
    _email_health_cache: dict[str, Any] = {"at": 0.0, "snapshot": None}

    def _email_health_snapshot(force: bool = False) -> dict[str, Any]:
        import time

        from MyCiteV2.scripts.email_health_audit import run_checks

        now = time.time()
        cached = _email_health_cache["snapshot"]
        # The checks shell out to dig + SES (a few seconds); memo briefly so
        # a reload doesn't re-run them. ?refresh=1 forces a fresh run.
        if not force and cached is not None and (now - _email_health_cache["at"]) < 90:
            return cached
        report = run_checks()
        snapshot = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "passed": len(report.passed),
            "failed": len(report.failed),
            "results": [
                {"name": r.name, "ok": r.ok, "detail": r.detail}
                for r in report.results
            ],
        }
        _email_health_cache["snapshot"] = snapshot
        _email_health_cache["at"] = now
        return snapshot

    def _email_routes_snapshot() -> list[dict[str, Any]]:
        # The live mailbox -> destination map the forwarder enforces, read
        # from the same operator profile store the reconciler uses.
        rows: list[dict[str, Any]] = []
        try:
            for profile in _aws_peripheral._profiles.list_profiles():
                ident = profile.get("identity") or {}
                inbound = profile.get("inbound") or {}
                send_as = _as_text(ident.get("send_as_email"))
                if not send_as:
                    continue
                rows.append({
                    "address": send_as,
                    "forwards_to": _as_text(inbound.get("receive_routing_target"))
                    or _as_text(ident.get("operator_inbox_target")),
                    "lifecycle": _as_text((profile.get("workflow") or {}).get("lifecycle_state")),
                })
        except Exception as exc:  # never let the panel 500 on a profile read
            _log.warning("email-health: profile list failed: %s", exc)
        return sorted(rows, key=lambda r: r["address"])

    @app.get("/portal/api/v2/admin/aws/email-health")
    def portal_email_health_json() -> tuple[Any, int]:
        force = _as_text(request.args.get("refresh")) in ("1", "true", "yes")
        snap = _email_health_snapshot(force=force)
        return jsonify({**snap, "routes": _email_routes_snapshot()}), 200

    @app.get("/portal/email-health")
    def portal_email_health_page() -> Any:
        force = _as_text(request.args.get("refresh")) in ("1", "true", "yes")
        snap = _email_health_snapshot(force=force)
        html = _render_email_health_page(snap, _email_routes_snapshot())
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.post("/portal/api/v2/shell")
    def portal_shell() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_portal_shell_entry(
                    _json_payload(),
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                    data_dir=host_config.data_dir,
                    public_dir=host_config.public_dir,
                    private_dir=host_config.private_dir,
                    audit_storage_file=host_config.portal_audit_storage_file,
                    webapps_root=host_config.webapps_root,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                    authority_db_file=host_config.authority_db_file,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))
        except Exception as exc:
            _legacy = _check_legacy_maps_error(exc)
            if _legacy is not None:
                return _legacy
            raise

    @app.post("/portal/api/v2/system/workspace/profile-basics")
    def portal_profile_basics_action() -> tuple[Any, int]:
        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA
            return _runtime_response(
                run_system_profile_basics_action(
                    payload,
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                    data_dir=host_config.data_dir,
                    public_dir=host_config.public_dir,
                    audit_storage_file=host_config.portal_audit_storage_file,
                    authority_db_file=host_config.authority_db_file,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    # CTS-GIS legacy removal (Stage C): the bespoke /tools/cts-gis surface + its
    # actions endpoint are retired. CTS-GIS is now a set of thin read-only
    # WorkbenchTools (cts_gis / cts_gis_district / cts_gis_admin) reached through the
    # unified workbench, and spatial editing is dropped. The mutation router below
    # keeps only the unified datum_workbench path.
    @app.post("/portal/api/v2/mutations/<action>")
    def portal_mutation_action(action: str) -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
            run_datum_workbench_mutation_action,
        )

        try:
            payload = _json_payload()
            target_authority = _nimm_target_authority(payload)
            if target_authority in {"datum_workbench", "datum_document"}:
                result = run_datum_workbench_mutation_action(
                    action,
                    payload,
                    authority_db_file=host_config.authority_db_file,
                    portal_instance_id=host_config.portal_instance_id,
                )
                return jsonify(result), int(result.get("status_code") or (200 if result.get("ok") else 400))
            return _error_response(
                "unsupported_mutation_target",
                "Mutation target_authority must be datum_workbench (cts_gis editing retired).",
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/workbench-ui")
    def portal_workbench_ui() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
            run_portal_workbench_ui,
        )

        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = WORKBENCH_UI_TOOL_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_workbench_ui(
                    payload,
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                    authority_db_file=host_config.authority_db_file,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    # ------------------------------------------------------------------
    # FND newsletter subscribe pipeline routes
    # ------------------------------------------------------------------

    @app.post("/__fnd/grantee/save")
    def fnd_grantee_save() -> tuple[Any, int]:
        """Phase 9 (grantee_profile_contract.md): persist edits made through
        the ext_grantee_profile form. Accepts JSON:
            {"msn_id": "<grantee-msn>", "fields": {<flat-or-dotted keys>}}

        Loads the existing grantee JSON (matched by glob on the msn_id
        suffix), merges in the submitted fields (including dotted-key
        nested sub-configs like "paypal.webhook_url"), validates through
        the GranteeProfile dataclass, and writes atomically via
        save_grantee_profile.

        Returns the persisted profile as JSON on success; 4xx on validation
        failure; 404 when the grantee msn doesn't match any file; 500 on
        write error.
        """
        import glob as _glob
        from pathlib import Path as _Path

        from MyCiteV2.packages.core.grantee import (
            AwsSesConfig,
            ConnectConfig,
            GranteeProfile,
            NewsletterConfig,
            PaypalConfig,
            ReceiptConfig,
            load_grantee_profile,
            save_grantee_profile,
        )
        from MyCiteV2.packages.core.grantee.store import GranteeProfileWriteError

        payload = _json_payload()
        msn_id = _as_text(payload.get("msn_id"))
        fields_raw = payload.get("fields")
        if not msn_id or not isinstance(fields_raw, dict):
            return jsonify({"ok": False, "error": "invalid_request"}), 400

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        # If the request arrived through a per-grantee dashboard (the auth proxy
        # injects the grantee header), it may only edit that grantee's OWN
        # profile — closes a cross-tenant write hole. The operator portal sends
        # no such header and keeps full access.
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            resolve_grantee_from_headers as _resolve_grantee_from_headers,
        )

        _caller = _resolve_grantee_from_headers(
            request.headers,
            fnd_csm_root=_Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm",
        )
        if _caller is not None and _as_text(_caller.get("msn_id")) != msn_id:
            return jsonify({"ok": False, "error": "grantee_not_owned"}), 403

        # Find the file. Grantee files are named
        # grantee.{fnd_msn}.{grantee_msn}.json; we match by the suffix.
        grantee_dir = _Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm"
        candidates = sorted(
            _glob.glob(str(grantee_dir / f"grantee.*.{msn_id}.json"))
        )
        if len(candidates) == 0:
            return jsonify({"ok": False, "error": "grantee_not_found"}), 404
        if len(candidates) > 1:
            return jsonify({"ok": False, "error": "ambiguous_grantee_match"}), 409
        target_path = _Path(candidates[0])

        try:
            current = load_grantee_profile(target_path)
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({"ok": False, "error": "grantee_load_failed", "detail": str(exc)}), 500

        # Split flat dotted-key fields into top-level and sub-config buckets.
        # Phase 17a: ``connect`` joins paypal/aws_ses/newsletter as a
        # known sub-config so the operator can edit forward_to_email
        # via the grantee profile form.
        identity_fields: dict[str, Any] = {}
        sub_buckets: dict[str, dict[str, Any]] = {
            "paypal": {},
            "aws_ses": {},
            "newsletter": {},
            "connect": {},
            "receipt": {},
        }
        for key, value in fields_raw.items():
            key_text = _as_text(key)
            if "." in key_text:
                bucket, leaf = key_text.split(".", 1)
                if bucket in sub_buckets:
                    sub_buckets[bucket][leaf] = value
                continue
            identity_fields[key_text] = value

        # Construct the next profile. The dataclass constructors validate;
        # missing/empty fields preserve the current profile's identity but
        # allow editing of populated values.
        def _list_field(value: Any, current: tuple[str, ...]) -> tuple[str, ...]:
            if isinstance(value, (list, tuple)):
                return tuple(_as_text(v) for v in value if _as_text(v))
            return current

        def _build_sub(cls, bucket: dict[str, Any], current: Any):
            if not bucket:
                return current
            merged: dict[str, Any] = current.to_dict() if current is not None else {}
            for k, v in bucket.items():
                merged[k] = v
            # Drop empty-string keys for cleanliness when nothing is set.
            non_empty = {k: v for k, v in merged.items() if v not in (None, "")}
            if not non_empty:
                return None
            return cls.from_dict(merged)

        try:
            next_profile = GranteeProfile(
                msn_id=current.msn_id,
                label=_as_text(identity_fields.get("label", current.label)),
                short_name=_as_text(identity_fields.get("short_name", current.short_name)),
                domains=_list_field(identity_fields.get("domains"), current.domains),
                users=_list_field(identity_fields.get("users"), current.users),
                paypal=_build_sub(PaypalConfig, sub_buckets["paypal"], current.paypal),
                aws_ses=_build_sub(AwsSesConfig, sub_buckets["aws_ses"], current.aws_ses),
                newsletter=_build_sub(NewsletterConfig, sub_buckets["newsletter"], current.newsletter),
                connect=_build_sub(ConnectConfig, sub_buckets["connect"], current.connect),
                receipt=_build_sub(ReceiptConfig, sub_buckets["receipt"], current.receipt),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": "validation_failed", "detail": str(exc)}), 400

        try:
            save_grantee_profile(target_path, next_profile)
        except GranteeProfileWriteError as exc:
            return jsonify({"ok": False, "error": "storage_error", "detail": str(exc)}), 500

        return jsonify({"ok": True, "profile": next_profile.to_dict()}), 200

    @app.post("/__fnd/newsletter/subscribe")
    def fnd_newsletter_subscribe() -> tuple[Any, int]:
        """Public site-signup endpoint. Phase E.3 shim: validates the
        request shape then dispatches through the canonical mutation
        runtime (target_authority=newsletter_contact_log,
        operation=upsert_subscriber).
        """
        domain = _normalize_domain(request.host)
        known = _newsletter_known_domains(host_config.private_dir)
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404

        raw_email = _fnd_newsletter_request_field("email")
        # Phase 15b: capture first / middle / last when the form supplies
        # them; fall back to a single ``name`` field for legacy forms.
        # The mutation runtime + adapter auto-split a single name token
        # into (first, middle, last) so partial input is still useful.
        first_name = _fnd_newsletter_request_field("first_name")
        middle_name = _fnd_newsletter_request_field("middle_name")
        last_name = _fnd_newsletter_request_field("last_name")
        name = _fnd_newsletter_request_field("name")
        # Phase 16a: phone + zip now persist as their own magnitudes.
        phone = _fnd_newsletter_request_field("phone")
        zip_code = _fnd_newsletter_request_field("zip")

        email = _validate_email(raw_email)
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400

        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "newsletter_contact_log",
                    "operation": "upsert_subscriber",
                    "domain": domain,
                    "email": email,
                    "name": name,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "last_name": last_name,
                    "phone": phone,
                    "zip": zip_code,
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
        return (
            jsonify({"ok": True, "email": email, "subscribed": True}),
            200,
            _legacy_deprecation_headers("newsletter_contact_log", "upsert_subscriber"),
        )

    @app.post("/__fnd/newsletter/unsubscribe")
    def fnd_newsletter_unsubscribe() -> tuple[Any, int]:
        # TODO(mos-migration): replace filesystem contact log write with MOS datum upsert
        domain = _normalize_domain(request.host)
        known = _newsletter_known_domains(host_config.private_dir)
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404

        # Accept token/email from query string or body
        raw_email = (
            str(request.args.get("email") or "").strip()
            or _fnd_newsletter_request_field("email")
        )
        token_value = (
            str(request.args.get("token") or "").strip()
            or _fnd_newsletter_request_field("token")
        )
        email = _validate_email(raw_email)
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400

        # Validate HMAC token via service layer
        try:
            from MyCiteV2.packages.adapters.filesystem.newsletter_state import (
                FilesystemNewsletterStateAdapter,
            )
            from MyCiteV2.packages.modules.cross_domain.newsletter.payload_utils import (
                render_unsubscribe_token as _render_unsubscribe_token,
            )
            state_adapter = FilesystemNewsletterStateAdapter(host_config.private_dir)
            signing_secret = state_adapter.runtime_secret_seed(secret_kind="signing_secret")
            expected = _render_unsubscribe_token(signing_secret, domain=domain, email=email)
            if token_value != expected:
                return jsonify({"ok": False, "error": "invalid_token"}), 403
        except Exception:
            return jsonify({"ok": False, "error": "token_validation_error"}), 500

        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "newsletter_contact_log",
                    "operation": "mark_unsubscribed",
                    "domain": domain,
                    "email": email,
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
        if not (result.get("preview") or {}).get("matched"):
            # Email wasn't on the list (or no list yet) — say so instead of a
            # misleading 200 "unsubscribed".
            return jsonify({"ok": False, "error": "contact_not_found"}), 404
        return (
            jsonify({"ok": True, "email": email, "subscribed": False}),
            200,
            _legacy_deprecation_headers("newsletter_contact_log", "mark_unsubscribed"),
        )

    @app.post("/__fnd/newsletter/dispatch-result")
    def fnd_newsletter_dispatch_result() -> tuple[Any, int]:
        # TODO(mos-migration): replace filesystem contact log write with MOS datum upsert
        domain = _normalize_domain(request.host)
        known = _newsletter_known_domains(host_config.private_dir)
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404

        payload = _json_payload()
        callback_token = str(payload.get("callback_token") or "").strip()
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        email = _validate_email(str(payload.get("email") or ""))
        status = str(payload.get("status") or "").strip().lower()
        message_id = str(payload.get("message_id") or "").strip()
        str(payload.get("queue_message_id") or "").strip()
        error_message = str(payload.get("error_message") or "").strip()

        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400
        if status not in {"sent", "failed"}:
            return jsonify({"ok": False, "error": "invalid_status"}), 400
        if not dispatch_id or not callback_token:
            return jsonify({"ok": False, "error": "missing_required_fields"}), 400

        # Validate dispatch callback token
        try:
            from MyCiteV2.packages.adapters.filesystem.newsletter_state import (
                FilesystemNewsletterStateAdapter,
            )
            state_adapter = FilesystemNewsletterStateAdapter(host_config.private_dir)
            expected_token = state_adapter.runtime_secret_seed(secret_kind="dispatch_secret")
            if callback_token != expected_token:
                return jsonify({"ok": False, "error": "invalid_callback_token"}), 403
        except Exception:
            return jsonify({"ok": False, "error": "token_validation_error"}), 500

        # Phase E.3 shim: dispatch result lands as a record_dispatch_result
        # mutation through the canonical runtime. The legacy
        # dispatch-history array is no longer persisted — the v2 schema
        # reserves `dispatches` but Phase 5 doesn't populate it.
        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "newsletter_contact_log",
                    "operation": "record_dispatch_result",
                    "domain": domain,
                    "email": email,
                    "status": status,
                    "message_id": message_id,
                    "error_message": error_message,
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500
        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
        preview = result.get("preview") or {}
        if not preview.get("matched"):
            return jsonify({"ok": False, "error": "recipient_not_found"}), 404

        return (
            jsonify({"ok": True, "domain": domain, "dispatch_id": dispatch_id, "email": email, "status": status}),
            200,
            _legacy_deprecation_headers("newsletter_contact_log", "record_dispatch_result"),
        )

    # ------------------------------------------------------------------
    # FND Connect-form route (Phase 17c)
    # ------------------------------------------------------------------
    # Public visitor endpoint backing the website Connect form. Persists
    # the visitor's contact info as an unsubscribed contact log row
    # (source=connect_form), then attempts to forward the visitor's
    # message via SES to ``grantee.connect.forward_to_email``. On SES
    # failure the contact is still saved with forward_status=pending
    # so the operator can retry from the Connect extension tab.

    def _resolve_grantee_for_domain(domain: str) -> dict[str, Any]:
        if host_config.private_dir is None or not domain:
            return {}
        try:
            from MyCiteV2.instances._shared.runtime.operational_store import (
                load_grantee_profiles,
            )

            for grantee in load_grantee_profiles(host_config.private_dir):
                domains = [str(d).lower() for d in (grantee.get("domains") or [])]
                if domain.lower() in domains:
                    return grantee
        except Exception:
            # Never swallow silently: a loader/import failure here used to make
            # every public form 404 "domain_not_configured" with no trace, turning
            # a config hiccup into an invisible site-wide outage (the bug this
            # endpoint shipped with). Log with stack so it is diagnosable; still
            # return {} so callers treat it as "unknown domain" rather than
            # crashing the request.
            _log.exception(
                "grantee_profile_load_failed",
                extra={"domain": domain, "private_dir": str(host_config.private_dir)},
            )
        return {}

    def _send_email_extension_message(
        *,
        profile: dict[str, Any],
        grantee: dict[str, Any],
        subject: str,
        body_text: str,
        tag: str,
        template_version: str = "",
        configuration_set: str | None = None,
    ) -> dict[str, Any]:
        """Send a transactional message tied to an operator-mailbox profile.

        Shared between the resend-handoff and send-reminder admin routes.
        Returns ``{ok, sent_to, message_id, sent_at, template_version, send_as,
        detail}``. Always returns a dict (never raises); the caller decides
        the HTTP status from ``ok``.

        The ``configuration_set`` argument lets routes pin a per-purpose SES
        configset for reputation isolation (e.g. ``fnd-transactional`` for
        the onboarding-nudge family). It overrides whatever value is in
        ``grantee.aws_ses.configuration_set``.

        A3 — for the NUDGE class only (``tag == "send_reminder"``): sets RFC
        8058 one-click List-Unsubscribe headers anchored on the profile_id
        and honors a per-profile opt-out (``notifications.unsubscribed``).
        Credential/account-status mail (``tag == "resend_handoff"``) is NOT
        gated and does NOT carry the unsubscribe header — the GET unsubscribe
        page explicitly promises operators still receive handoff mail, and a
        one-click unsubscribe on a credential email would otherwise lock the
        operator out of future credential resends.

        A4 — always sets Reply-To (no conditional path). Falls back to
        ``reply-to@<from_domain>`` if the grantee profile doesn't set one.
        """
        identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
        inbox = _as_text(identity.get("operator_inbox_target"))
        if not inbox:
            return {"ok": False, "detail": "profile missing operator_inbox_target"}

        # The notification opt-out + List-Unsubscribe affordance apply ONLY
        # to nudge-class mail (reminders), never to credential-handoff or
        # account-status mail. resend_handoff must always send + must not
        # advertise one-click unsubscribe.
        is_nudge = tag == "send_reminder"

        # A3: respect a prior one-click unsubscribe so we don't ignore
        # the operator's stated preference even if the admin clicks the
        # Send-reminder button again. Nudge class only.
        notifications = profile.get("notifications") if isinstance(profile.get("notifications"), dict) else {}
        if is_nudge and bool(notifications.get("unsubscribed")):
            return {
                "ok": False,
                "detail": "operator has unsubscribed from notifications",
                "skipped_reason": "unsubscribed",
            }

        aws_cfg = dict(grantee.get("aws_ses") or {})
        if not _as_text(aws_cfg.get("identity")) and not _as_text(aws_cfg.get("from_address")):
            return {"ok": False, "detail": "grantee aws_ses identity not configured"}
        if configuration_set:
            aws_cfg["configuration_set"] = configuration_set

        # A4: always-on Reply-To. Default to reply-to@<from_domain> when
        # the grantee aws_ses doesn't set one (no cross-domain Reply-To;
        # filters score that as suspicious).
        from_address = _as_text(aws_cfg.get("from_address")) or _as_text(aws_cfg.get("identity"))
        from_domain = from_address.rsplit("@", 1)[-1].strip() if "@" in from_address else ""
        reply_to_value = _as_text(aws_cfg.get("reply_to"))
        if not reply_to_value and from_domain:
            reply_to_value = f"reply-to@{from_domain}"
        reply_to_list = [reply_to_value] if reply_to_value else None

        # A3: build the per-profile one-click unsubscribe URL — nudge class
        # ONLY. The route itself (POST = RFC 8058 one-click, GET = browser
        # fallback) is registered below near the other email-admin routes.
        # resend_handoff (credential mail) deliberately carries no
        # List-Unsubscribe header.
        profile_id = _as_text(identity.get("profile_id"))
        extra_headers: dict[str, str] = {}
        if is_nudge and profile_id:
            unsubscribe_url = (
                f"https://{host_config.portal_domain}"
                f"/__fnd/profile/{profile_id}/unsubscribe-notifications"
            )
            extra_headers["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            extra_headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        try:
            send_result = _aws_peripheral.send_email(
                aws_ses_profile=aws_cfg,
                to=[inbox],
                subject=subject,
                body_text=body_text,
                reply_to=reply_to_list,
                extra_headers=extra_headers or None,
            )
        except SesSendError as exc:
            _log.error(
                f"{tag}_ses_failed",
                extra={
                    "profile_id": _as_text(identity.get("profile_id")),
                    "domain": _as_text(identity.get("domain")),
                    "aws_error_code": exc.aws_error_code,
                    "aws_request_id": exc.aws_request_id,
                    "reason": exc.reason,
                },
            )
            return {"ok": False, "detail": exc.reason}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}

        return {
            "ok": True,
            "sent_to": inbox,
            "send_as": _as_text(aws_cfg.get("from_address")) or _as_text(aws_cfg.get("identity")),
            "message_id": _as_text(getattr(send_result, "message_id", None))
            or _as_text(getattr(send_result, "MessageId", None))
            or "",
            "sent_at": _utc_now_iso(),
            "template_version": _as_text(template_version),
        }

    def _reminder_subject_body(
        profile: dict[str, Any], next_step_label: str
    ) -> tuple[str, str]:
        """Build the Subject + plain-text body for the onboarding reminder.

        Distinct from the handoff template: no credentials, polite tone,
        threading hint via In-Reply-To is left to a future iteration (the
        peripherals.aws.send_email surface does not yet expose extra_headers
        for arbitrary RFC 5322 fields in a way that survives DKIM signing).
        """
        ident = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
        send_as = _as_text(ident.get("send_as_email")) or "your new mailbox"
        inbox = _as_text(ident.get("operator_inbox_target")) or "your personal inbox"
        next_step_label = _as_text(next_step_label) or "complete the next step"

        subject = f"[Reminder] Finish setting up {send_as}"
        body = (
            "Hi,\n\n"
            f"This is a follow-up to the setup note we sent earlier about your "
            f"{send_as} mailbox. We have not yet seen the configuration go "
            f"active on our side.\n\n"
            f"The next step is: {next_step_label}.\n\n"
            f"If you still have the original setup email, please follow the "
            f"five-field SMTP instructions there. Replies will arrive at "
            f"{inbox}.\n\n"
            "If you no longer have the original setup email, reply to this "
            "message and we'll reissue fresh credentials. The credentials are "
            f"scoped only to {send_as} and can be rotated at any time.\n\n"
            "Thank you,\n"
            "FND mailbox setup\n"
        )
        return subject, body

    def _ses_forward_connect_message(
        *,
        grantee: dict[str, Any],
        domain: str,
        visitor_email: str,
        visitor_name: str,
        subject: str,
        message: str,
    ) -> str:
        """Attempt to forward the Connect-form message via SES.

        Returns one of:
          - ``"sent"`` on success
          - ``"not_configured"`` if forwarding is not set up (no
            forward_to_email or no aws_ses identity) — distinct from
            "pending" so the dashboard doesn't imply an automatic retry
          - ``"failed"`` on SES failure (the operator can retry from
            the extension tab)
        """
        connect_cfg = grantee.get("connect") if isinstance(grantee.get("connect"), dict) else {}
        aws_cfg = grantee.get("aws_ses") if isinstance(grantee.get("aws_ses"), dict) else {}
        forward_to = _as_text(connect_cfg.get("forward_to_email"))
        ses_identity = _as_text(aws_cfg.get("identity"))
        if not forward_to or not ses_identity:
            # Forwarding isn't configured for this grantee. Return a distinct
            # status (NOT "pending", which implies an automatic retry that will
            # never come) so the dashboard reports "saved — no forward configured"
            # honestly; the contact still lands in the Connect tab.
            return "not_configured"
        display_subject = subject or f"Connect message from {visitor_email}"
        display_from = visitor_name or visitor_email
        body_text = (
            f"From: {display_from} <{visitor_email}>\n"
            f"Domain: {domain}\n"
            f"Subject: {display_subject}\n\n"
            f"{message}\n"
        )
        # multipart/alternative HTML companion — Gmail penalises text-only
        # messages from low-volume senders. Same content, escaped, with
        # the message body preserved as paragraphs so line-breaks survive.
        from html import escape as _html_escape
        message_html = "".join(
            f"<p>{_html_escape(line) or '&nbsp;'}</p>" for line in (message.splitlines() or [""])
        )
        body_html = (
            "<!doctype html><html><body style=\"font-family:system-ui,Arial,sans-serif;"
            "line-height:1.45;color:#222;\">"
            f"<p style=\"margin:0 0 0.4em\"><strong>From:</strong> "
            f"{_html_escape(display_from)} &lt;<a href=\"mailto:{_html_escape(visitor_email)}\">"
            f"{_html_escape(visitor_email)}</a>&gt;</p>"
            f"<p style=\"margin:0 0 0.4em\"><strong>Domain:</strong> {_html_escape(domain)}</p>"
            f"<p style=\"margin:0 0 1em\"><strong>Subject:</strong> "
            f"{_html_escape(display_subject)}</p>"
            f"<hr style=\"border:0;border-top:1px solid #ccc;margin:1em 0\">"
            f"{message_html}"
            "</body></html>"
        )
        # Transactional-message hygiene headers Gmail looks for:
        #  - List-Id identifies the message stream so receivers can group
        #    and score by stream rather than by individual sender.
        #  - List-Unsubscribe + List-Unsubscribe-Post (RFC 8058) is required
        #    for bulk and harmless on transactional; signals
        #    standards-conformance. Points at a mailto: for now — wiring a
        #    one-click HTTP endpoint is a follow-up.
        #  - Auto-Submitted distinguishes machine-generated from human mail
        #    so receivers don't classify as a personal-correspondence outlier.
        list_id = f"connect-form.{domain}"
        extra_headers = {
            "List-Id": f"<{list_id}>",
            "List-Unsubscribe": f"<mailto:{forward_to}?subject=unsubscribe-connect-{domain}>",
            "Auto-Submitted": "auto-generated",
            "X-FND-Stream": "connect-form",
            "X-FND-Source-Domain": domain,
        }
        try:
            _aws_peripheral.send_email(
                aws_ses_profile=aws_cfg,
                to=[forward_to],
                subject=f"[Connect] {display_subject}",
                body_text=body_text,
                body_html=body_html,
                reply_to=[visitor_email] if visitor_email else None,
                extra_headers=extra_headers,
            )
        except SesSendError as exc:
            _log.error(
                "connect_forward_ses_failed",
                extra={
                    "domain": domain,
                    "visitor_email": visitor_email,
                    "aws_error_code": exc.aws_error_code,
                    "aws_request_id": exc.aws_request_id,
                    "reason": exc.reason,
                },
            )
            return "failed"
        return "sent"

    @app.post("/__fnd/connect/submit")
    def fnd_connect_submit() -> tuple[Any, int]:
        """Public Connect-form endpoint. Same calling convention as
        ``/__fnd/newsletter/subscribe`` — domain is derived from the
        request.host, body carries the visitor fields + message.

        Content negotiation: a JSON-body request gets a JSON response
        (the path the shared connect.js takes). A form-encoded request
        (the no-JS fallback path) gets an HTML response with a link back
        to the referring page. This lets visitors with JavaScript
        disabled still file a contact, with a real UX instead of raw
        JSON painted on a blank page.
        """
        is_json_request = request.is_json or "application/json" in (
            request.headers.get("Accept") or ""
        )

        domain = _normalize_domain(request.host)
        if not domain:
            return _connect_response(
                is_json_request, ok=False, status=400, error="missing_domain"
            )

        # Gate to known grantee domains — the public endpoint must not persist
        # contacts for arbitrary Host headers (anti-spam / abuse vector).
        grantee = _resolve_grantee_for_domain(domain)
        if not grantee:
            return _connect_response(
                is_json_request, ok=False, status=404, error="domain_not_configured"
            )

        # Honeypot: a hidden field a real visitor never fills. If a bot fills
        # it, ack success (so it moves on) but persist + forward nothing.
        if _fnd_newsletter_request_field("hp_field"):
            return _connect_response(
                is_json_request, ok=True, status=200, forward_status="sent"
            )

        raw_email = _fnd_newsletter_request_field("email")
        email = _validate_email(raw_email)
        if not email:
            return _connect_response(
                is_json_request, ok=False, status=400, error="invalid_email"
            )
        message = _fnd_newsletter_request_field("message")
        if not message:
            return _connect_response(
                is_json_request, ok=False, status=400, error="missing_message"
            )
        first_name = _fnd_newsletter_request_field("first_name")
        middle_name = _fnd_newsletter_request_field("middle_name")
        last_name = _fnd_newsletter_request_field("last_name")
        phone = _fnd_newsletter_request_field("phone")
        zip_code = _fnd_newsletter_request_field("zip")
        organization = _fnd_newsletter_request_field("organization")
        subject = _fnd_newsletter_request_field("subject")
        display_name = " ".join(t for t in (first_name, last_name) if t) or email

        from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
            run_datum_workbench_mutation_action,
        )

        # 1. Persist FIRST (forward_status=pending). Persisting before the SES
        #    send means a storage failure aborts before any email goes out, so
        #    a visitor retry can't double-send the message to the grantee.
        try:
            persisted = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "newsletter_contact_log",
                    "operation": "submit_connect_form",
                    "domain": domain,
                    "email": email,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "last_name": last_name,
                    "phone": phone,
                    "zip": zip_code,
                    "organization": organization,
                    "subject": subject,
                    "message": message,
                    "forward_status": "pending",
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return _connect_response(
                is_json_request, ok=False, status=500,
                error="storage_error", forward_status="pending",
            )
        if not persisted.get("ok"):
            return _connect_response(
                is_json_request, ok=False, status=500,
                error="storage_error", forward_status="pending",
            )

        # 2. Forward to the grantee inbox via SES (best-effort).
        forward_status = _ses_forward_connect_message(
            grantee=grantee,
            domain=domain,
            visitor_email=email,
            visitor_name=display_name,
            subject=subject,
            message=message,
        )

        # 3. Record the final forward outcome on the now-persisted row
        #    (best-effort — the contact is already saved, so a failure here
        #    only leaves the status as pending, it never loses the message).
        if forward_status and forward_status != "pending":
            try:
                run_datum_workbench_mutation_action(
                    "apply",
                    {
                        "target_authority": "newsletter_contact_log",
                        "operation": "edit_subscriber",
                        "domain": domain,
                        "email": email,
                        "forward_status": forward_status,
                    },
                    authority_db_file=host_config.authority_db_file,
                    portal_instance_id=host_config.portal_instance_id,
                    private_dir=host_config.private_dir,
                )
            except Exception:
                # Best-effort: the contact is already persisted, so a failed
                # status update must not fail the request. But log it (was a
                # silent pass) so a row stuck at the pre-forward status is visible.
                _log.exception(
                    "connect_forward_status_update_failed",
                    extra={"domain": domain, "email": email, "forward_status": forward_status},
                )

        return _connect_response(
            is_json_request, ok=True, status=200,
            email=email, subscribed=False, forward_status=forward_status,
        )

    # ------------------------------------------------------------------
    # FND Newsletter admin routes (Phase 14d.1)
    # ------------------------------------------------------------------
    # Three operator-facing routes that back the Newsletter extension's
    # interactive controls on /portal/utilities/extensions. Unlike the
    # public /__fnd/newsletter/{subscribe,unsubscribe,dispatch-result}
    # endpoints — which derive their target ``domain`` from
    # request.host so the public website can only touch its own
    # contact log — these routes accept the domain explicitly in the
    # JSON body so the portal operator can manage any grantee's list
    # from the same surface.
    #
    # All three dispatch through the canonical mutation runtime
    # (target_authority="newsletter_contact_log") or, in the
    # case of set_sender, persist back to the grantee JSON via
    # save_grantee_profile.

    def _admin_field(payload: dict[str, Any], key: str) -> str:
        return _as_text(payload.get(key)) if isinstance(payload, dict) else ""

    def _newsletter_admin_scope_error(domain: str):
        """Per-grantee scope guard for the operator newsletter-admin routes.

        These routes serve the FND operator portal (no grantee header →
        full access). But they are also reachable through the per-grantee
        ``/dashboard/api/`` proxy, which injects the caller's grantee header.
        When that header is present, restrict the write to the caller's own
        domains so one grantee can't mutate another's contact list.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            resolve_grantee_from_headers,
        )

        if host_config.private_dir is None:
            return None
        caller = resolve_grantee_from_headers(
            request.headers,
            fnd_csm_root=Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm",
        )
        if caller is None:
            return None
        owned = {
            _normalize_domain(str(d))
            for d in caller.get("domains") or []
            if str(d).strip()
        }
        if domain not in owned:
            return jsonify({"ok": False, "error": "domain_not_owned"}), 403
        return None

    def _email_admin_scope_error(*, profile_id: str = "", domain: str = ""):
        """Cross-tenant guard for the operator email-admin routes — mirrors
        ``_newsletter_admin_scope_error``. These routes are also reachable
        through the per-grantee ``/dashboard/api/`` proxy, which injects the
        caller's grantee header. When that header is present the caller may
        only act on a profile/domain it OWNS; otherwise (operator portal, no
        grantee header) full access is allowed. Closes the cross-tenant
        mailbox-takeover hole (a client dashboard POSTing another tenant's
        profile_id). A scoped caller targeting an unknown or unowned profile
        gets a uniform 403 — no existence leak."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            resolve_grantee_from_headers,
        )

        if host_config.private_dir is None:
            return None
        caller = resolve_grantee_from_headers(
            request.headers,
            fnd_csm_root=Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm",
        )
        if caller is None:
            return None  # operator context (no grantee header)
        owned = {
            _normalize_domain(str(d))
            for d in caller.get("domains") or []
            if str(d).strip()
        }
        target_domain = _normalize_domain(domain)
        if not target_domain and profile_id:
            from MyCiteV2.packages.peripherals.aws import ProfileStore

            store = ProfileStore(
                root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
            )
            prof = store.get_profile(profile_id)
            target_domain = (
                _normalize_domain((prof.get("identity") or {}).get("domain"))
                if prof
                else ""
            )
        if not target_domain or target_domain not in owned:
            return jsonify({"ok": False, "error": "domain_not_owned"}), 403
        return None

    @app.post("/__fnd/newsletter/admin/add")
    def fnd_newsletter_admin_add() -> tuple[Any, int]:
        payload = _json_payload()
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
        domain = _normalize_domain(_admin_field(payload, "domain"))
        email = _validate_email(_admin_field(fields, "email"))
        # Phase 15b: capture first / middle / last from the admin form;
        # legacy ``name`` is still accepted and auto-split downstream.
        first_name = _admin_field(fields, "first_name")
        middle_name = _admin_field(fields, "middle_name")
        last_name = _admin_field(fields, "last_name")
        name = _admin_field(fields, "name")
        # Phase 16a: phone + zip + signup_date.
        phone = _admin_field(fields, "phone")
        zip_code = _admin_field(fields, "zip")
        signup_date = _admin_field(fields, "signup_date")

        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400
        known = _newsletter_known_domains(host_config.private_dir)
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404
        scope_err = _newsletter_admin_scope_error(domain)
        if scope_err:
            return scope_err

        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "newsletter_contact_log",
                    "operation": "upsert_subscriber",
                    "domain": domain,
                    "email": email,
                    "name": name,
                    "first_name": first_name,
                    "middle_name": middle_name,
                    "last_name": last_name,
                    "phone": phone,
                    "zip": zip_code,
                    "signup_date": signup_date,
                    "source": "operator",
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
        return jsonify({"ok": True, "domain": domain, "email": email, "subscribed": True}), 200

    @app.post("/__fnd/newsletter/admin/edit")
    def fnd_newsletter_admin_edit() -> tuple[Any, int]:
        """Phase 16a — inline row edit on the newsletter Contacts table.

        Body: ``{"domain": ..., "fields": {"email": ..., <updates>}}``.
        ``email`` identifies the row; supported update keys are
        first_name, middle_name, last_name, phone, zip, signup_date.
        Subscribed state is NOT touched by this route — use the
        per-row Suspend/Resume button (or /__fnd/newsletter/admin/
        remove) for lifecycle changes.
        """
        payload = _json_payload()
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
        domain = _normalize_domain(_admin_field(payload, "domain"))
        email = _validate_email(_admin_field(fields, "email"))

        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400
        known = _newsletter_known_domains(host_config.private_dir)
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404
        scope_err = _newsletter_admin_scope_error(domain)
        if scope_err:
            return scope_err

        edit_payload: dict[str, Any] = {
            "target_authority": "newsletter_contact_log",
            "operation": "edit_subscriber",
            "domain": domain,
            "email": email,
        }
        for key in (
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "zip",
            "organization",
            "signup_date",
        ):
            if isinstance(fields, dict) and key in fields:
                edit_payload[key] = _admin_field(fields, key)

        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
                "apply",
                edit_payload,
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            # The mutation runtime wraps ValueErrors raised by the
            # inner ``edit_subscriber`` op (e.g. ``contact_not_found``
            # or ``contact_log_missing_for_domain``) in the envelope's
            # ``error.message``. Both mean "the operator's email
            # doesn't exist for this domain" → 404.
            err = result.get("error") or {}
            message = _as_text(err.get("message"))
            if "contact_not_found" in message or "contact_log_missing" in message:
                return jsonify({"ok": False, "error": "contact_not_found"}), 404
            return jsonify({"ok": False, "error": "storage_error", "detail": message}), 500

        preview = result.get("preview") or {}
        return (
            jsonify(
                {
                    "ok": True,
                    "domain": domain,
                    "email": email,
                    "updated_fields": preview.get("updated_fields") or [],
                }
            ),
            200,
        )

    @app.post("/__fnd/newsletter/admin/remove")
    def fnd_newsletter_admin_remove() -> tuple[Any, int]:
        payload = _json_payload()
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
        domain = _normalize_domain(_admin_field(payload, "domain"))
        email = _validate_email(_admin_field(fields, "email"))

        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400
        known = _newsletter_known_domains(host_config.private_dir)
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404
        scope_err = _newsletter_admin_scope_error(domain)
        if scope_err:
            return scope_err

        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
                "apply",
                {
                    "target_authority": "newsletter_contact_log",
                    "operation": "mark_unsubscribed",
                    "domain": domain,
                    "email": email,
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
                private_dir=host_config.private_dir,
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
        if not (result.get("preview") or {}).get("matched"):
            # No such contact on this domain — don't pretend we removed one.
            return jsonify({"ok": False, "error": "contact_not_found"}), 404
        return jsonify({"ok": True, "domain": domain, "email": email, "subscribed": False}), 200

    @app.post("/__fnd/newsletter/admin/set_sender")
    def fnd_newsletter_admin_set_sender() -> tuple[Any, int]:
        """Persist the newsletter sender address to the grantee JSON.

        Body: ``{"msn_id": "<grantee>", "fields": {"sender_address": "..."}}``.
        Reuses the existing grantee-save persistence path so the same
        validation + atomic write contract applies. Returns the updated
        newsletter sub-config on success.
        """
        import glob as _glob
        from pathlib import Path as _Path

        from MyCiteV2.packages.core.grantee import (
            AwsSesConfig,
            GranteeProfile,
            NewsletterConfig,
            PaypalConfig,
            load_grantee_profile,
            save_grantee_profile,
        )
        from MyCiteV2.packages.core.grantee.store import GranteeProfileWriteError

        payload = _json_payload()
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
        msn_id = _admin_field(payload, "msn_id")
        sender_address = _validate_email(_admin_field(fields, "sender_address"))

        if not msn_id:
            return jsonify({"ok": False, "error": "missing_msn_id"}), 400
        if not sender_address:
            return jsonify({"ok": False, "error": "invalid_email"}), 400
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        grantee_dir = _Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm"
        candidates = sorted(_glob.glob(str(grantee_dir / f"grantee.*.{msn_id}.json")))
        if len(candidates) == 0:
            return jsonify({"ok": False, "error": "grantee_not_found"}), 404
        if len(candidates) > 1:
            return jsonify({"ok": False, "error": "ambiguous_grantee_match"}), 409
        target_path = _Path(candidates[0])

        try:
            current = load_grantee_profile(target_path)
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({"ok": False, "error": "grantee_load_failed", "detail": str(exc)}), 500

        # Operator must be in the grantee's users list — prevents
        # promoting an arbitrary email into the sender slot.
        if sender_address not in {u.lower() for u in current.users}:
            return jsonify({"ok": False, "error": "sender_not_in_users"}), 400

        current_newsletter = current.newsletter.to_dict() if current.newsletter is not None else {}
        current_newsletter["selected_sender_address"] = sender_address
        try:
            next_profile = GranteeProfile(
                msn_id=current.msn_id,
                label=current.label,
                short_name=current.short_name,
                domains=current.domains,
                users=current.users,
                paypal=current.paypal,
                aws_ses=current.aws_ses,
                newsletter=NewsletterConfig.from_dict(current_newsletter),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": "validation_failed", "detail": str(exc)}), 400

        # Suppress unused import warnings — kept for symmetry with grantee-save.
        del AwsSesConfig, PaypalConfig

        try:
            save_grantee_profile(target_path, next_profile)
        except GranteeProfileWriteError as exc:
            return jsonify({"ok": False, "error": "storage_error", "detail": str(exc)}), 500

        return (
            jsonify({
                "ok": True,
                "msn_id": msn_id,
                "newsletter": next_profile.newsletter.to_dict() if next_profile.newsletter else {},
            }),
            200,
        )

    # ------------------------------------------------------------------
    # FND Email admin route (Phase 14d.2)
    # ------------------------------------------------------------------
    # The Email extension surfaces a per-row Suspend / Resume button.
    # The handler toggles ``workflow.lifecycle_state`` on the matching
    # AWS-CSM operator profile JSON. Add-mailbox flow is deferred: the
    # LIVE_AWS_PROFILE_SCHEMA carries enough required fields (smtp,
    # verification, provider, workflow, inbound) that constructing a
    # net-new profile via a form is its own scope; suspend ships now
    # because operators need it for runbook lockouts today.

    def _post_profile_save_hook(profile_id: str, *, op: str) -> None:
        """C2 — refresh the ses-forwarder Lambda's FORWARD_TO_MAP_JSON
        after any profile-JSON write or delete. Fire-and-log: errors
        are swallowed (and logged) so the admin action returns OK even
        if the Lambda env update fails — the next sync run will retry.

        Without this hook, the operator had to manually run
        sync_aws_csm_forward_maps.py after every profile edit; missing
        a run silently dropped inbound mail for newly-added recipients.

        IMPORTANT: the forward map MUST be rebuilt from the SAME profile
        directory the edit/remove routes write to —
        ``host_config.private_dir/utilities/tools/aws-csm``. The
        module-level ``_aws_peripheral`` was constructed with no
        profile_store, so its ProfileStore defaults to
        ``deployed/<grantee>/...`` which is a DIFFERENT directory on this
        host; syncing from it would rebuild the map from a stale set and
        miss the just-saved edit. We therefore list profiles from the
        correct root and pass them explicitly.
        """
        if host_config.private_dir is None:
            return
        try:
            from MyCiteV2.packages.peripherals.aws import ProfileStore

            store = ProfileStore(
                root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
            )
            _aws_peripheral.sync_operator_forwarding_routes(
                profiles=store.list_profiles(), dry_run=False
            )
        except Exception as exc:
            _log.error(
                "post_profile_save_hook_failed",
                extra={"profile_id": profile_id, "op": op, "err": str(exc)},
            )

    @app.post("/__fnd/email/admin/suspend")
    def fnd_email_admin_suspend() -> tuple[Any, int]:
        payload = _json_payload()
        profile_id = _as_text(payload.get("profile_id"))
        suspended = bool(payload.get("suspended"))

        if not profile_id:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        scope_err = _email_admin_scope_error(profile_id=profile_id)
        if scope_err:
            return scope_err
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        try:
            from MyCiteV2.packages.peripherals.aws import ProfileStore
        except Exception:
            return jsonify({"ok": False, "error": "module_load_failed"}), 500

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        # The profile_id itself is a valid tenant_scope_id (matches
        # identity.profile_id branch of load_profile), so we
        # can scope reads + writes by it without knowing the tenant.
        current = store.load_profile(tenant_scope_id=profile_id, profile_id=profile_id)
        if current is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404

        workflow = dict(current.get("workflow") or {})
        workflow["lifecycle_state"] = "suspended" if suspended else "operational"
        next_payload = dict(current)
        next_payload["workflow"] = workflow

        try:
            store.save_profile(
                tenant_scope_id=profile_id,
                profile_id=profile_id,
                payload=next_payload,
            )
        except (ValueError, OSError) as exc:
            return jsonify({"ok": False, "error": "storage_error", "detail": str(exc)}), 500

        return jsonify(
            {
                "ok": True,
                "profile_id": profile_id,
                "lifecycle_state": workflow["lifecycle_state"],
            }
        ), 200

    # ------------------------------------------------------------------
    # C3 — DMARC policy ramp (advisory by default; guarded apply)
    # ------------------------------------------------------------------
    # Reads the current _dmarc TXT, checks MAIL-FROM-live + alignment +
    # dwell preconditions (active-task guardrail G-1: never ramp past
    # p=none without MAIL FROM live + >=7d + >=95% alignment, never skip a
    # rung, never jump straight to p=reject), and:
    #   * default (no confirm): returns the advisory — current rung,
    #     proposed next rung, and any blockers. Touches nothing.
    #   * confirm=true AND allowed: UPSERTs the next rung's TXT record.
    #
    # alignment_pct + days_at_current have no automated source yet (the
    # DMARC aggregate-report parser is future work), so the operator
    # passes them in the request when they have the data from the SES /
    # mailbox-provider console. Absent → the ramp is blocked, which is
    # the safe default.
    @app.post("/__fnd/email/admin/dmarc-ramp")
    def fnd_email_admin_dmarc_ramp() -> tuple[Any, int]:
        payload = _json_payload()
        domain = _normalize_domain(_as_text(payload.get("domain")))
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        scope_err = _email_admin_scope_error(domain=domain)
        if scope_err:
            return scope_err
        confirm = bool(payload.get("confirm"))
        alignment_pct = payload.get("alignment_pct")
        days_at_current = payload.get("days_at_current")
        try:
            alignment_pct = float(alignment_pct) if alignment_pct is not None else None
        except (TypeError, ValueError):
            alignment_pct = None
        try:
            days_at_current = int(days_at_current) if days_at_current is not None else None
        except (TypeError, ValueError):
            days_at_current = None

        try:
            from MyCiteV2.packages.peripherals.aws.dmarc_ramp import compute_dmarc_ramp
        except Exception:
            return jsonify({"ok": False, "error": "module_load_failed"}), 500

        current = _aws_peripheral.get_dmarc_policy(domain)
        if not current.get("ok"):
            return jsonify({"ok": False, "error": current.get("error", "read_failed")}), 404

        # MAIL FROM live? Read the SES identity's MAIL FROM status.
        mail_from_live = False
        try:
            ses = _aws_peripheral._client("ses")
            mf = ses.get_identity_mail_from_domain_attributes(Identities=[domain])
            status = (
                mf.get("MailFromDomainAttributes", {})
                .get(domain, {})
                .get("MailFromDomainStatus", "")
            )
            mail_from_live = status == "Success"
        except Exception:
            mail_from_live = False

        decision = compute_dmarc_ramp(
            current_tags=current.get("tags") or {},
            mail_from_live=mail_from_live,
            alignment_pct=alignment_pct,
            days_at_current=days_at_current,
        )

        if not confirm or not decision["allowed"]:
            # Advisory only — never mutate without confirm AND allowed.
            return jsonify(
                {
                    "ok": True,
                    "applied": False,
                    "domain": domain,
                    "mail_from_live": mail_from_live,
                    "decision": decision,
                }
            ), 200

        apply_result = _aws_peripheral.apply_dmarc_policy(
            domain, decision["proposed_record"], dry_run=False
        )
        return jsonify(
            {
                "ok": bool(apply_result.get("ok")),
                "applied": bool(apply_result.get("ok")),
                "domain": domain,
                "decision": decision,
                "apply_result": apply_result,
            }
        ), (200 if apply_result.get("ok") else 502)

    # ------------------------------------------------------------------
    # A3 — RFC 8058 one-click unsubscribe for transactional onboarding mail
    # ------------------------------------------------------------------
    # Every nudge (resend-handoff, send-reminder) emitted by the portal
    # carries List-Unsubscribe + List-Unsubscribe-Post headers pointing at
    # this route. POST is the RFC 8058 one-click endpoint that Gmail /
    # O365 hit when the operator clicks the in-MUA Unsubscribe button.
    # GET is the browser fallback if the operator pastes the URL.
    #
    # The opt-out is recorded on the profile JSON; _send_email_extension_message
    # checks `notifications.unsubscribed` and refuses to send if set.
    # Suspend / Resume + Resend handoff are not gated by this — only the
    # nudge-class messages (reminders) honor it.
    @app.post("/__fnd/profile/<profile_id>/unsubscribe-notifications")
    def fnd_profile_unsubscribe_notifications_post(profile_id: str) -> tuple[Any, int]:
        profile_id_clean = _as_text(profile_id)
        if not profile_id_clean:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500
        try:
            from MyCiteV2.packages.peripherals.aws import ProfileStore
        except Exception:
            return jsonify({"ok": False, "error": "module_load_failed"}), 500

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        current = store.load_profile(
            tenant_scope_id=profile_id_clean, profile_id=profile_id_clean
        )
        if current is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404

        notifications = dict(current.get("notifications") or {})
        if notifications.get("unsubscribed"):
            # Idempotent — repeat one-click POSTs return ok.
            return jsonify(
                {"ok": True, "profile_id": profile_id_clean, "already_unsubscribed": True}
            ), 200
        notifications["unsubscribed"] = True
        notifications["unsubscribed_at"] = _utc_now_iso()
        next_payload = dict(current)
        next_payload["notifications"] = notifications
        try:
            store.save_profile(
                tenant_scope_id=profile_id_clean,
                profile_id=profile_id_clean,
                payload=next_payload,
            )
        except (ValueError, OSError) as exc:
            return jsonify(
                {"ok": False, "error": "storage_error", "detail": str(exc)}
            ), 500
        return jsonify(
            {
                "ok": True,
                "profile_id": profile_id_clean,
                "unsubscribed_at": notifications["unsubscribed_at"],
            }
        ), 200

    @app.get("/__fnd/profile/<profile_id>/unsubscribe-notifications")
    def fnd_profile_unsubscribe_notifications_get(profile_id: str) -> tuple[Any, int]:
        """Browser fallback. Renders a minimal confirmation page; if the
        operator hits Confirm, an HTML form POSTs to the same URL and the
        opt-out is recorded the same way the one-click MUA path would.
        """
        profile_id_clean = _as_text(profile_id)
        if not profile_id_clean:
            return ("Missing profile id.", 400)
        if host_config.private_dir is None:
            return ("Server not configured.", 500)
        try:
            from MyCiteV2.packages.peripherals.aws import ProfileStore
        except Exception:
            return ("Server module load failed.", 500)
        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        current = store.load_profile(
            tenant_scope_id=profile_id_clean, profile_id=profile_id_clean
        )
        if current is None:
            return ("Unknown profile.", 404)
        already = bool((current.get("notifications") or {}).get("unsubscribed"))
        page = (
            "<!doctype html><meta charset='utf-8'>"
            "<title>Unsubscribe from onboarding notifications</title>"
            "<style>body{font-family:Georgia,serif;max-width:560px;margin:64px auto;"
            "padding:0 24px;line-height:1.5;color:#222}</style>"
        )
        if already:
            page += (
                "<h1>You're already unsubscribed.</h1>"
                "<p>No further onboarding-reminder emails will be sent to this profile.</p>"
            )
            return (page, 200)
        page += (
            "<h1>Unsubscribe from onboarding reminders?</h1>"
            "<p>This stops the periodic reminder emails that ask you to finish "
            "setting up your mailbox. You will still receive credential-handoff "
            "and account-status messages.</p>"
            f"<form method='post' action='/__fnd/profile/{profile_id_clean}/unsubscribe-notifications'>"
            "<button type='submit' style='padding:10px 20px;font-size:1em;"
            "cursor:pointer;background:#444;color:#fff;border:0;border-radius:4px;'>"
            "Confirm unsubscribe</button>"
            "</form>"
        )
        return (page, 200)

    # ------------------------------------------------------------------
    # FND Email admin route — inline edit operator-profile fields
    # ------------------------------------------------------------------
    # Updates the cosmetic / routing fields the operator legitimately
    # tweaks after the mailbox is alive:
    #
    #   identity.send_as_email
    #   identity.role
    #   identity.operator_inbox_target
    #
    # Identity primary keys (profile_id, domain, mailbox_local_part,
    # tenant_id) are NOT mutable here — changing them re-onboards the
    # mailbox; that work belongs to a dedicated rebuild flow, not an
    # inline edit. Unknown field keys are ignored.
    @app.post("/__fnd/email/admin/edit")
    def fnd_email_admin_edit() -> tuple[Any, int]:
        payload = _json_payload()
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else {}
        profile_id = _as_text(payload.get("profile_id"))

        if not profile_id:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        scope_err = _email_admin_scope_error(profile_id=profile_id)
        if scope_err:
            return scope_err
        if not isinstance(fields, dict) or not fields:
            return jsonify({"ok": False, "error": "missing_fields"}), 400
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        try:
            from MyCiteV2.packages.peripherals.aws import ProfileStore
        except Exception:
            return jsonify({"ok": False, "error": "module_load_failed"}), 500

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        current = store.load_profile(
            tenant_scope_id=profile_id, profile_id=profile_id
        )
        if current is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404

        allowed_keys = {"send_as_email", "role", "operator_inbox_target"}
        identity = dict(current.get("identity") or {})
        updated: list[str] = []
        for key in allowed_keys:
            if key in fields:
                identity[key] = _as_text(fields.get(key))
                updated.append(key)
        if not updated:
            return jsonify({"ok": False, "error": "no_supported_fields"}), 400

        next_payload = dict(current)
        next_payload["identity"] = identity
        # The forwarder reconciler (iter_profile_recipient_targets) prefers
        # inbound.receive_routing_target over identity.operator_inbox_target, so
        # a forward-to edit that only touched identity silently didn't take
        # effect. Keep them in lockstep (mirrors onboard_alias's dual-write).
        if "operator_inbox_target" in fields:
            inbound = dict(next_payload.get("inbound") or {})
            inbound["receive_routing_target"] = _as_text(fields.get("operator_inbox_target"))
            next_payload["inbound"] = inbound
        try:
            store.save_profile(
                tenant_scope_id=profile_id,
                profile_id=profile_id,
                payload=next_payload,
            )
        except (ValueError, OSError) as exc:
            return jsonify(
                {"ok": False, "error": "storage_error", "detail": str(exc)}
            ), 500

        # C2: an edit may have changed send_as_email / operator_inbox_target,
        # both of which feed the forwarder's FORWARD_TO_MAP_JSON. Refresh it
        # so inbound mail for the edited mailbox routes correctly without a
        # manual sync_aws_csm_forward_maps.py run.
        _post_profile_save_hook(profile_id, op="edit")

        return jsonify(
            {
                "ok": True,
                "profile_id": profile_id,
                "updated_fields": updated,
            }
        ), 200

    # ------------------------------------------------------------------
    # FND Email admin route — remove operator profile (delete JSON on disk)
    # ------------------------------------------------------------------
    # Deletes the operator-profile JSON file. SES identity registration,
    # inbound rules, and forward map entries are NOT touched — only the
    # portal's view of the mailbox. Re-bootstrapping with the same
    # profile_id will recreate the JSON. Use Suspend (not Remove) for a
    # reversible disable.
    @app.post("/__fnd/email/admin/remove")
    def fnd_email_admin_remove() -> tuple[Any, int]:
        payload = _json_payload()
        profile_id = _as_text(payload.get("profile_id"))

        if not profile_id:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        scope_err = _email_admin_scope_error(profile_id=profile_id)
        if scope_err:
            return scope_err
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        try:
            from MyCiteV2.packages.peripherals.aws import ProfileStore
        except Exception:
            return jsonify({"ok": False, "error": "module_load_failed"}), 500

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        current = store.load_profile(
            tenant_scope_id=profile_id, profile_id=profile_id
        )
        if current is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404

        source_path = _as_text(current.get("_source_path"))
        if not source_path:
            return jsonify({"ok": False, "error": "source_path_missing"}), 500
        try:
            Path(source_path).unlink()
        except OSError as exc:
            return jsonify(
                {"ok": False, "error": "storage_error", "detail": str(exc)}
            ), 500

        # C2: the removed profile's send_as → target route must drop out of
        # the forwarder's FORWARD_TO_MAP_JSON so inbound mail for the gone
        # mailbox stops being relayed.
        _post_profile_save_hook(profile_id, op="remove")

        return jsonify(
            {
                "ok": True,
                "profile_id": profile_id,
                "removed_path": source_path,
            }
        ), 200

    # ------------------------------------------------------------------
    # FND Email admin route — resend handoff email (2026-05-18; rewired 2026-05-22)
    # ------------------------------------------------------------------
    # Re-dispatches the operator-mailbox handoff notice for a profile
    # whose onboarding is still in progress (lifecycle still ``draft``).
    #
    # History: the original implementation imported
    # ``AwsEc2RoleOnboardingCloudAdapter`` from
    # ``MyCiteV2.packages.adapters.event_transport``. That adapter — and
    # its companion ``read_handoff_secret`` SMTP-credential reader — were
    # removed in commit 68f0676 (AWS-CSM onboarding-cloud bloat sweep),
    # but the call site here was not updated, so every click of the
    # button hit ``module_load_failed`` (500).
    #
    # The rewire below uses the existing ``_aws_peripheral`` send surface
    # directly. ``read_handoff_secret`` is gone and a derived SMTP password
    # is unrecoverable once issued (IAM returns the secret only at creation),
    # so the resent message is the *handoff notice* body only — it does NOT
    # re-embed an SMTP password. Operators who lost the original credential
    # package should re-run ``issue-smtp-credentials`` (which self-provisions
    # fresh creds from the EC2 host under /aws-cms/smtp/ and rotates the key);
    # this button just nudges them otherwise.

    @app.post("/__fnd/email/admin/resend-handoff")
    def fnd_email_admin_resend_handoff() -> tuple[Any, int]:
        payload = _json_payload()
        profile_id = _as_text(payload.get("profile_id"))

        if not profile_id:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        scope_err = _email_admin_scope_error(profile_id=profile_id)
        if scope_err:
            return scope_err
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        try:
            from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
            from MyCiteV2.packages.peripherals.aws import ProfileStore
            from MyCiteV2.packages.peripherals.aws.handoff_template import (
                HANDOFF_TEMPLATE_VERSION,
                handoff_body,
                handoff_subject,
            )
        except Exception as exc:
            return jsonify(
                {"ok": False, "error": "module_load_failed", "detail": str(exc)}
            ), 500

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        current = store.load_profile(
            tenant_scope_id=profile_id, profile_id=profile_id
        )
        if current is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404

        profile_domain = _as_text(
            (current.get("identity") or {}).get("domain")
        )
        grantee_for_send = _resolve_grantee_for_domain(profile_domain)
        result = _send_email_extension_message(
            profile=current,
            grantee=grantee_for_send,
            subject=handoff_subject(current),
            body_text=handoff_body(current, {}),  # password unavailable; template falls back
            tag="resend_handoff",
            template_version=HANDOFF_TEMPLATE_VERSION,
            configuration_set="fnd-transactional",
        )
        if not result.get("ok"):
            return jsonify(
                {"ok": False, "error": "send_failed",
                 "detail": _as_text(result.get("detail"))}
            ), 502

        identity = dict(current.get("identity") or {})
        workflow = dict(current.get("workflow") or {})
        workflow["handoff_email_sent_to"] = _as_text(result.get("sent_to"))
        workflow["handoff_email_message_id"] = _as_text(result.get("message_id"))
        workflow["handoff_email_sent_at"] = _as_text(result.get("sent_at"))
        workflow["handoff_template_version"] = _as_text(
            result.get("template_version")
        )
        workflow["handoff_status"] = "instruction_sent"
        next_payload = dict(current)
        next_payload["workflow"] = workflow

        try:
            store.save_profile(
                tenant_scope_id=profile_id,
                profile_id=profile_id,
                payload=next_payload,
            )
        except (ValueError, OSError) as exc:
            return jsonify(
                {"ok": False, "error": "storage_error", "detail": str(exc)}
            ), 500

        if host_config.portal_audit_storage_file is not None:
            try:
                audit_adapter = FilesystemAuditLogAdapter(
                    host_config.portal_audit_storage_file
                )
                from MyCiteV2.packages.ports.audit_log import AuditLogAppendRequest

                audit_adapter.append_audit_record(
                    AuditLogAppendRequest(
                        record={
                            "event_type": "portal.aws.send_handoff_email.accepted",
                            "shell_verb": "portal.aws.send_handoff_email",
                            "focus_subject": profile_id,
                            "details": {
                                "profile_id": profile_id,
                                "tenant_scope_id": _as_text(
                                    identity.get("tenant_id")
                                )
                                or profile_id,
                                "send_as_email": _as_text(result.get("send_as"))
                                or _as_text(identity.get("send_as_email")),
                                "sent_to": _as_text(result.get("sent_to")),
                                "message_id": _as_text(result.get("message_id")),
                                "handoff_provider": _as_text(
                                    identity.get("handoff_provider")
                                ),
                                "template_version": _as_text(
                                    result.get("template_version")
                                ),
                            },
                        }
                    )
                )
            except Exception:
                # Audit failure must not break the send; the profile
                # JSON itself carries the handoff_email_* fields as a
                # secondary durable record.
                pass

        return jsonify(
            {
                "ok": True,
                "profile_id": profile_id,
                "message_id": _as_text(result.get("message_id")),
                "sent_to": _as_text(result.get("sent_to")),
                "sent_at": _as_text(result.get("sent_at")),
                "template_version": _as_text(result.get("template_version")),
            }
        ), 200

    # ------------------------------------------------------------------
    # FND Email admin route — send onboarding reminder (2026-05-22)
    # ------------------------------------------------------------------
    # Distinct from resend-handoff: re-sending the handoff package
    # repeats SMTP credentials, which clutters inboxes and trains
    # filters to flag handoff mail as bulk. A reminder is a polite
    # nudge with no credentials, gated on:
    #
    #   - handoff_email_sent_at must be non-empty
    #   - lifecycle must not already be operational / suspended
    #   - the derived onboarding sequence still has a next_step
    #   - cooldown: no two reminders inside 24h
    #
    # The same gates are enforced in
    # ``utilities_extensions.email._send_reminder_action_for_profile`` so
    # the button is hidden / disabled in the UI; this route re-checks
    # server-side so a hand-rolled request cannot bypass the cooldown.

    @app.post("/__fnd/email/admin/send-reminder")
    def fnd_email_admin_send_reminder() -> tuple[Any, int]:
        payload = _json_payload()
        profile_id = _as_text(payload.get("profile_id"))

        if not profile_id:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        scope_err = _email_admin_scope_error(profile_id=profile_id)
        if scope_err:
            return scope_err
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        try:
            from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
                _onboarding_progress,
                _reminder_cooldown_remaining,
            )
            from MyCiteV2.packages.adapters.filesystem import FilesystemAuditLogAdapter
            from MyCiteV2.packages.peripherals.aws import ProfileStore
        except Exception as exc:
            return jsonify(
                {"ok": False, "error": "module_load_failed", "detail": str(exc)}
            ), 500

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        current = store.load_profile(
            tenant_scope_id=profile_id, profile_id=profile_id
        )
        if current is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404

        workflow = dict(current.get("workflow") or {})
        lifecycle = _as_text(workflow.get("lifecycle_state")).lower()
        if lifecycle in {"operational", "suspended"}:
            return jsonify(
                {"ok": False, "error": "not_eligible", "detail": f"lifecycle={lifecycle}"}
            ), 409
        if not _as_text(workflow.get("handoff_email_sent_at")):
            return jsonify(
                {"ok": False, "error": "not_eligible", "detail": "handoff_not_sent"}
            ), 409

        progress = _onboarding_progress(current)
        next_step = (progress.get("next_step") or {}).get("label") or ""
        if not next_step:
            return jsonify(
                {"ok": False, "error": "not_eligible", "detail": "no_next_step"}
            ), 409

        cooldown = _reminder_cooldown_remaining(workflow)
        if cooldown is not None:
            hours = max(1, round(cooldown.total_seconds() / 3600))
            return jsonify(
                {"ok": False, "error": "cooldown_active",
                 "detail": f"reminder sent within last {24 - hours}h; retry in ~{hours}h"}
            ), 429

        profile_domain = _as_text(
            (current.get("identity") or {}).get("domain")
        )
        grantee_for_send = _resolve_grantee_for_domain(profile_domain)

        subject, body = _reminder_subject_body(current, next_step)
        result = _send_email_extension_message(
            profile=current,
            grantee=grantee_for_send,
            subject=subject,
            body_text=body,
            tag="send_reminder",
            template_version="reminder_v1_2026_05",
            configuration_set="fnd-transactional",
        )
        if not result.get("ok"):
            return jsonify(
                {"ok": False, "error": "send_failed",
                 "detail": _as_text(result.get("detail"))}
            ), 502

        workflow["reminder_sent_at"] = _as_text(result.get("sent_at"))
        workflow["reminder_message_id"] = _as_text(result.get("message_id"))
        workflow["reminder_template_version"] = _as_text(result.get("template_version"))
        workflow["reminder_next_step"] = next_step
        next_payload = dict(current)
        next_payload["workflow"] = workflow

        try:
            store.save_profile(
                tenant_scope_id=profile_id,
                profile_id=profile_id,
                payload=next_payload,
            )
        except (ValueError, OSError) as exc:
            return jsonify(
                {"ok": False, "error": "storage_error", "detail": str(exc)}
            ), 500

        if host_config.portal_audit_storage_file is not None:
            try:
                audit_adapter = FilesystemAuditLogAdapter(
                    host_config.portal_audit_storage_file
                )
                from MyCiteV2.packages.ports.audit_log import AuditLogAppendRequest

                audit_adapter.append_audit_record(
                    AuditLogAppendRequest(
                        record={
                            "event_type": "portal.aws.send_reminder_email.accepted",
                            "shell_verb": "portal.aws.send_reminder_email",
                            "focus_subject": profile_id,
                            "details": {
                                "profile_id": profile_id,
                                "domain": profile_domain,
                                "next_step": next_step,
                                "sent_to": _as_text(result.get("sent_to")),
                                "message_id": _as_text(result.get("message_id")),
                                "template_version": _as_text(
                                    result.get("template_version")
                                ),
                            },
                        }
                    )
                )
            except Exception:
                pass

        return jsonify(
            {
                "ok": True,
                "profile_id": profile_id,
                "message_id": _as_text(result.get("message_id")),
                "sent_to": _as_text(result.get("sent_to")),
                "sent_at": _as_text(result.get("sent_at")),
                "next_step": next_step,
                "template_version": _as_text(result.get("template_version")),
            }
        ), 200

    # ------------------------------------------------------------------
    # FND Analytics admin route (post-2026-05 — MOS adapter retired)
    # ------------------------------------------------------------------
    # The Analytics extension card surfaces a Refresh button that POSTs
    # here. The handler no longer persists anything to MOS — analytics
    # storage is on-disk NDJSON only, per the analytics_event_schema.md
    # contract. The handler now just invalidates the in-memory summary
    # cache so the next /__fnd/analytics/summary call recomputes from
    # the canonical NDJSON without a stale 60s TTL hit.

    # ------------------------------------------------------------------
    # FND Analytics raw-event collector (Phase 18a)
    # ------------------------------------------------------------------
    # Browser-facing collector. Every <script src="/__fnd/analytics.js">
    # in the 3 webdesigns POSTs each captured event here. The endpoint
    # validates + server-stamps + appends to the canonical NDJSON file
    # under <webapps>/clients/<domain>/analytics/events/<YYYY-MM>.ndjson.
    # Visitor identity is an HttpOnly first-party cookie ``fnd_vid``
    # minted on first request; the hash of that cookie + IP is what
    # actually lands in the event row (the raw values never persist).

    _ANALYTICS_VISITOR_COOKIE = "fnd_vid"
    _ANALYTICS_SALT_HOLDER: dict[str, str] = {}
    _ANALYTICS_DEDUP_WINDOW_MS = 250
    _ANALYTICS_DEDUP: dict[tuple[str, str, str], int] = {}

    # Module-scoped TTL cache for /__fnd/analytics/summary. Cache key
    # is (msn_id, start, end, cache_generation) — the generation token
    # is the mtime of <analytics_root>/.cache_gen, so /__fnd/analytics/
    # refresh can invalidate across all gunicorn workers by touching
    # one file (clearing a worker-local dict only flushed half the
    # cache with --workers 2 --preload).
    _ANALYTICS_SUMMARY_CACHE: dict[tuple[str, str, str, float], tuple[float, dict[str, Any]]] = {}
    _ANALYTICS_SUMMARY_TTL = 60.0
    _ANALYTICS_CACHE_GEN_FILENAME = ".cache_gen"

    def _analytics_cache_gen_path() -> Path | None:
        if host_config.private_dir is None:
            return None
        return (
            Path(host_config.private_dir)
            / "utilities"
            / "tools"
            / "analytics"
            / _ANALYTICS_CACHE_GEN_FILENAME
        )

    def _analytics_cache_gen() -> float:
        path = _analytics_cache_gen_path()
        if path is None:
            return 0.0
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return 0.0
        except OSError:
            return 0.0

    def _configured_fnd_csm_root() -> Path:
        # Grantee profiles live under the app's CONFIGURED private_dir. Resolving
        # against this (rather than the tolling module's hardcoded default live
        # path) is a no-op on the deploy host — where private_dir IS
        # /srv/webapps/mycite/fnd/private — and the only thing that makes grantee
        # resolution work under a test/non-default config.
        return Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm"

    def _is_operator_request() -> bool:
        # Operator context = no oauth2-proxy grantee header. Mirrors
        # the convention used by /__fnd/tolling/refresh.
        return not _as_text(request.headers.get("X-Auth-Request-Grantee"))

    def _analytics_salt() -> str:
        cached = _ANALYTICS_SALT_HOLDER.get("salt")
        if cached:
            return cached
        if host_config.private_dir is None:
            return ""
        secret_path = (
            Path(host_config.private_dir)
            / "utilities"
            / "tools"
            / "analytics"
            / "secret.txt"
        )
        try:
            if secret_path.exists():
                value = secret_path.read_text(encoding="utf-8").strip()
            else:
                import secrets as _secrets

                value = _secrets.token_hex(32)
                secret_path.parent.mkdir(parents=True, exist_ok=True)
                secret_path.write_text(value, encoding="utf-8")
        except OSError:
            value = ""
        if value:
            _ANALYTICS_SALT_HOLDER["salt"] = value
        return value

    def _analytics_remote_addr() -> str:
        # nginx passes the public IP via X-Forwarded-For; fall back to
        # X-Real-IP and finally request.remote_addr.
        forwarded = _as_text(request.headers.get("X-Forwarded-For"))
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
        return _as_text(request.headers.get("X-Real-IP")) or _as_text(
            request.remote_addr
        )

    def _analytics_dedup_hit(
        visitor_cookie_hash: str, page_path: str, event_type: str
    ) -> bool:
        # Best-effort same-process dedup so a naive retry from the
        # browser doesn't create two rows. The window is 250ms.
        import time as _time

        key = (visitor_cookie_hash, page_path, event_type)
        now_ms = int(_time.time() * 1000)
        prev = _ANALYTICS_DEDUP.get(key)
        if prev is not None and now_ms - prev <= _ANALYTICS_DEDUP_WINDOW_MS:
            return True
        _ANALYTICS_DEDUP[key] = now_ms
        # Lazy GC: cap dictionary size at 4096 entries.
        if len(_ANALYTICS_DEDUP) > 4096:
            cutoff = now_ms - 5 * _ANALYTICS_DEDUP_WINDOW_MS
            for k, ts in list(_ANALYTICS_DEDUP.items()):
                if ts < cutoff:
                    _ANALYTICS_DEDUP.pop(k, None)
        return False

    @app.get("/__fnd/analytics.js")
    def fnd_analytics_js() -> Any:
        # Phase 18a stub: serve an empty JS body so the existing
        # <script src="/__fnd/analytics.js"> tags on every webdesign
        # page stop returning 404. Phase 18b replaces this with the
        # actual capture script from clients/_shared/site-core/.
        site_core_path = Path(
            "/srv/webapps/clients/_shared/site-core/js/extensions/analytics.js"
        )
        body = ""
        if site_core_path.exists():
            try:
                body = site_core_path.read_text(encoding="utf-8")
            except OSError:
                body = ""
        response = make_response(body, 200)
        response.headers["Content-Type"] = "application/javascript; charset=utf-8"
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    def _analytics_webapps_root() -> str | None:
        # The leaflets live at <webapps_root>/clients/_shared/site-core/analytics.
        # Live, private_dir is .../mycite/<instance>/private and the store derives
        # webapps_root from it, so this can be None; tests pass an explicit
        # webapps_root on the host config. Env is the last resort.
        if getattr(host_config, "webapps_root", None):
            return str(host_config.webapps_root)
        import os as _os

        return _os.environ.get("MYCITE_WEBAPPS_ROOT") or None

    def _campaign_tracked_url(domain: str, campaign: dict[str, Any]) -> str:
        """Public tracked URL for a campaign: the target page on the grantee's
        primary domain with the ``?fnd_c=<token>`` attribution param appended.
        analytics.js reads ``fnd_c`` and stamps it onto the session."""
        domain = _as_text(domain)
        target = _as_text(campaign.get("target_path")) or "/"
        if not target.startswith("/"):
            target = "/" + target
        token = _as_text(campaign.get("token"))
        if not domain:
            return f"{target}?fnd_c={token}"
        sep = "&" if "?" in target else "?"
        return f"https://{domain}{target}{sep}fnd_c={token}"

    @app.post("/__fnd/analytics/event")
    def fnd_analytics_event() -> tuple[Any, int]:
        from MyCiteV2.packages.core.analytics import RawEvent

        body = _json_payload()
        domain = _normalize_domain(request.host)
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400

        visitor_cookie = _as_text(request.cookies.get(_ANALYTICS_VISITOR_COOKIE))
        mint_cookie = not visitor_cookie
        if mint_cookie:
            import secrets as _secrets

            visitor_cookie = _secrets.token_urlsafe(18)

        salt = _analytics_salt()
        try:
            received_at_utc = datetime.now(UTC).isoformat()
            event = RawEvent.from_request(
                body,
                domain=domain,
                site_id=host_config.portal_instance_id,
                environment="prod",
                visitor_cookie=visitor_cookie,
                remote_addr=_analytics_remote_addr(),
                user_agent=_as_text(request.headers.get("User-Agent")),
                salt=salt,
                received_at_utc=received_at_utc,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": "invalid_event", "detail": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "schema_error"}), 500

        if _analytics_dedup_hit(
            event.visitor_cookie_id_hash, event.page_path, event.event_type
        ):
            response = make_response(jsonify({"ok": True, "deduped": True}), 200)
            if mint_cookie:
                response.set_cookie(
                    _ANALYTICS_VISITOR_COOKIE,
                    visitor_cookie,
                    max_age=365 * 24 * 60 * 60,
                    httponly=True,
                    secure=True,
                    samesite="Lax",
                    path="/",
                )
            return response, 200

        try:
            # Leaflet is the only store: buffer the event and let the
            # write-coalescer flush it into the monthly site-core leaflet
            # (visitors → sessions → events). The buffer keeps the beacon
            # fast despite frequent heartbeats; the leaflet adapter folds
            # heartbeats/scrolls into their page_view at merge time.
            from MyCiteV2.instances._shared.runtime.analytics_ingest import (
                get_ingest_buffer,
            )
            from MyCiteV2.packages.adapters.filesystem import entity_for_domain

            if host_config.private_dir is None:
                return jsonify({"ok": False, "error": "no_private_dir"}), 500
            entity = entity_for_domain(domain)
            buffer = get_ingest_buffer(
                private_dir=host_config.private_dir,
                webapps_root=_analytics_webapps_root(),
            )
            buffer.add(entity, domain, event.to_dict())
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        response = make_response(jsonify({"ok": True}), 200)
        if mint_cookie:
            response.set_cookie(
                _ANALYTICS_VISITOR_COOKIE,
                visitor_cookie,
                max_age=365 * 24 * 60 * 60,
                httponly=True,
                secure=True,
                samesite="Lax",
                path="/",
            )
        return response, 200

    @app.post("/__fnd/analytics/refresh")
    def fnd_analytics_refresh() -> tuple[Any, int]:
        """Operator refresh: flush any buffered events into the monthly
        leaflet and bump the analytics-cache generation token so every
        gunicorn worker misses its summary cache on the next
        /__fnd/analytics/summary call. The leaflet is the authoritative
        store; this just forces a materialize + recompute."""
        payload = _json_payload()
        domain = _normalize_domain(_as_text(payload.get("domain")))
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400

        # Flush pending in-memory events so the recompute sees the latest.
        try:
            from MyCiteV2.instances._shared.runtime.analytics_ingest import (
                get_ingest_buffer,
            )

            if host_config.private_dir is not None:
                get_ingest_buffer(
                    private_dir=host_config.private_dir,
                    webapps_root=_analytics_webapps_root(),
                ).flush_all()
        except Exception:
            pass

        # Touch the cache-generation token file. Every worker observes
        # the new mtime on its next request and naturally misses the
        # cache (the gen is part of the cache key). The clear() trick
        # we used before only flushed the calling worker's copy.
        gen_path = _analytics_cache_gen_path()
        if gen_path is not None:
            try:
                import os as _os
                gen_path.parent.mkdir(parents=True, exist_ok=True)
                gen_path.touch(exist_ok=True)
                # Bump the mtime explicitly so two refreshes inside the
                # same second still produce strictly-greater values
                # (filesystem mtime resolution can be 1s).
                stat = gen_path.stat()
                _os.utime(gen_path, (stat.st_atime, stat.st_mtime + 1))
            except OSError:
                pass

        return jsonify(
            {
                "ok": True,
                "domain": domain,
                "cache_generation_bumped": True,
            }
        ), 200

    # ------------------------------------------------------------------
    # FND PayPal admin route (Phase 14d.3) — CSV export of orders
    # ------------------------------------------------------------------
    # The PayPal extension surfaces an "Export CSV" link that hits this
    # GET endpoint. Returns ``text/csv`` with one row per order plus
    # a Content-Disposition header so the browser downloads it.

    @app.get("/__fnd/paypal/admin/export")
    def fnd_paypal_admin_export() -> tuple[Any, int]:
        import csv as _csv
        import io as _io

        domain = _normalize_domain(_as_text(request.args.get("domain")))
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400

        orders: list[dict[str, Any]] = []
        # Single source of truth: the append-only order log that create-order,
        # capture-order, and the webhook reconciler all write to. (Previously
        # this read MOS first and only fell back to the ndjson log when MOS was
        # empty — which silently hid every real donation once a MOS row
        # existed, since the live write path only ever wrote the ndjson log.)
        if host_config.private_dir is not None:
            ndjson_path = (
                Path(host_config.private_dir)
                / "utilities"
                / "tools"
                / "paypal-csm"
                / "orders.ndjson"
            )
            try:
                if ndjson_path.exists():
                    for line in ndjson_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            order = json.loads(line)
                        except Exception:
                            continue
                        if _as_text(order.get("domain")).lower() != domain.lower():
                            continue
                        orders.append(order)
            except Exception:
                pass

        buf = _io.StringIO()
        writer = _csv.writer(buf)
        writer.writerow(
            [
                "timestamp_ms",
                "event",
                "order_id",
                "status",
                "amount",
                "currency_code",
                "domain",
                "donor_email",
                "donor_name",
            ]
        )
        for o in orders:
            writer.writerow(
                [
                    _as_text(o.get("timestamp_ms")),
                    _as_text(o.get("event")),
                    _as_text(o.get("order_id")),
                    _as_text(o.get("status")),
                    _as_text(o.get("amount")),
                    _as_text(o.get("currency_code") or o.get("currency")),
                    _as_text(o.get("domain")),
                    _as_text(o.get("donor_email")),
                    _as_text(o.get("donor_name")),
                ]
            )
        body = buf.getvalue()

        response = make_response(body, 200)
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="paypal-orders-{domain}.csv"'
        )
        return response, 200

    def _grantee_file_for_msn(msn_id: str):
        """Locate the single grantee JSON for an msn. Returns (path, None) or
        (None, error_response)."""
        import glob as _glob
        from pathlib import Path as _Path

        if host_config.private_dir is None:
            return None, (jsonify({"ok": False, "error": "private_dir_not_configured"}), 500)
        grantee_dir = _Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm"
        candidates = sorted(_glob.glob(str(grantee_dir / f"grantee.*.{msn_id}.json")))
        if not candidates:
            return None, (jsonify({"ok": False, "error": "grantee_not_found"}), 404)
        if len(candidates) > 1:
            return None, (jsonify({"ok": False, "error": "ambiguous_grantee_match"}), 409)
        return _Path(candidates[0]), None

    def _paypal_config_view(paypal: Any) -> dict[str, Any]:
        """Project a PaypalConfig for the dashboard — the secret is never
        returned in full, only a boolean + last-4 so the operator can confirm
        which secret is set."""
        client_id = _as_text(paypal.client_id) if paypal else ""
        secret = _as_text(paypal.client_secret) if paypal else ""
        return {
            "mode": (_as_text(getattr(paypal, "mode", "")) or "link") if paypal else "link",
            "payment_link": _as_text(getattr(paypal, "payment_link", "")) if paypal else "",
            "client_id": client_id,
            "environment": _as_text(paypal.environment) if paypal else "sandbox",
            "plan_id": _as_text(getattr(paypal, "plan_id", "")) if paypal else "",
            "webhook_url": _as_text(paypal.webhook_url) if paypal else "",
            "webhook_id": _as_text(paypal.webhook_id) if paypal else "",
            "has_secret": bool(secret),
            "secret_tail": secret[-4:] if secret else "",
        }

    def _receipt_config_view(receipt: Any) -> dict[str, Any]:
        """Project a ReceiptConfig for the dashboard — the EIN is masked
        (has_ein + last-4 only) the same way the client secret is, so a blank
        field on save means "leave the stored EIN unchanged."""
        ein = _as_text(getattr(receipt, "ein", "")) if receipt else ""
        return {
            "legal_name": _as_text(getattr(receipt, "legal_name", "")) if receipt else "",
            "tax_status": (_as_text(getattr(receipt, "tax_status", "")) or "501(c)(3)") if receipt else "501(c)(3)",
            "mailing_address": _as_text(getattr(receipt, "mailing_address", "")) if receipt else "",
            "signer_name": _as_text(getattr(receipt, "signer_name", "")) if receipt else "",
            "signer_title": _as_text(getattr(receipt, "signer_title", "")) if receipt else "",
            "acknowledgement_statement": (
                _as_text(getattr(receipt, "acknowledgement_statement", ""))
                if receipt
                else ""
            ) or "No goods or services were provided in exchange for this contribution.",
            "has_ein": bool(ein),
            "ein_tail": ein[-4:] if ein else "",
        }

    @app.get("/__fnd/paypal/admin/config")
    def fnd_paypal_admin_config() -> tuple[Any, int]:
        """Operator/grantee-scoped read of the caller grantee's PayPal config.
        The client_secret is masked (has_secret + last-4 only)."""
        from MyCiteV2.packages.core.grantee import load_grantee_profile

        msn, err = _resolve_grantee_scope()
        if err:
            return err
        path, perr = _grantee_file_for_msn(msn)
        if perr:
            return perr
        try:
            profile = load_grantee_profile(path)
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({"ok": False, "error": "grantee_load_failed", "detail": str(exc)}), 500
        return jsonify({
            "ok": True,
            "paypal": _paypal_config_view(profile.paypal),
            "receipt": _receipt_config_view(profile.receipt),
        }), 200

    @app.get("/__fnd/paypal/config")
    def fnd_paypal_public_config() -> tuple[Any, int]:
        """PUBLIC, domain-resolved PayPal config for the site's checkout JS.

        Resolves the grantee by request Host (the same way create-order does) and
        returns ONLY the fields the browser needs to load the SDK / pick the flow:
        mode, client_id, environment, plan_id, payment_link. The client_secret is
        NEVER returned (client_id is public by PayPal's design). No oauth gate —
        this is consumed by the public donate/subscribe pages.
        """
        domain = _normalize_domain(request.host)
        grantee = _load_grantee_for_domain(host_config.private_dir, domain)
        cfg = (
            grantee.get("paypal")
            if grantee and isinstance(grantee.get("paypal"), dict)
            else {}
        )
        mode = _as_text(cfg.get("mode")).lower()
        if not mode:
            mode = "rest" if _as_text(cfg.get("client_secret")) else "link"
        return jsonify({
            "ok": True,
            "mode": mode,
            "client_id": _as_text(cfg.get("client_id")),
            "environment": _as_text(cfg.get("environment")) or "sandbox",
            "plan_id": _as_text(cfg.get("plan_id")),
            "payment_link": _as_text(cfg.get("payment_link")),
        }), 200

    @app.post("/__fnd/paypal/admin/update")
    def fnd_paypal_admin_update() -> tuple[Any, int]:
        """Operator/grantee-scoped write of the caller grantee's PayPal config.

        Validates ``environment`` ∈ {sandbox, live}. An empty client_id /
        client_secret means "leave unchanged" — the GET never returns the
        secret, so the form field is blank and a no-op save must not wipe it.
        Credentials are read fresh per request (mtime-invalidated grantee
        cache), so an update re-wires create-order/capture-order with no
        portal restart.

        The donation webhook is auto-provisioned: the URL is derived from the
        grantee's domain and the PayPal webhook is created (or reused) for the
        events the reconciler handles, with the returned id stored. The client
        does not supply webhook_url / webhook_id. A provisioning failure does
        not fail the save — the response carries a ``webhook_warning`` instead.
        """
        from dataclasses import replace as _dc_replace

        from MyCiteV2.packages.core.grantee import (
            PaypalConfig,
            ReceiptConfig,
            load_grantee_profile,
            save_grantee_profile,
        )
        from MyCiteV2.packages.core.grantee.store import GranteeProfileWriteError

        msn, err = _resolve_grantee_scope()
        if err:
            return err
        path, perr = _grantee_file_for_msn(msn)
        if perr:
            return perr
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400
        environment = _as_text(body.get("environment")).lower() or "sandbox"
        if environment not in {"sandbox", "live"}:
            return jsonify({"ok": False, "error": "invalid_environment"}), 400
        mode = _as_text(body.get("mode")).lower()
        if mode and mode not in {"link", "rest"}:
            return jsonify({"ok": False, "error": "invalid_mode"}), 400

        try:
            profile = load_grantee_profile(path)
        except (FileNotFoundError, ValueError) as exc:
            return jsonify({"ok": False, "error": "grantee_load_failed", "detail": str(exc)}), 500

        if not mode:
            # Back-compat: respect the stored mode (already migrated on load);
            # a credentialed save with no explicit mode is REST; otherwise link.
            stored_mode = _as_text(profile.paypal.mode) if profile.paypal else ""
            mode = stored_mode or (
                "rest"
                if (_as_text(body.get("client_id")) or _as_text(body.get("client_secret")))
                else "link"
            )

        merged = profile.paypal.to_dict() if profile.paypal else {}
        merged["environment"] = environment
        merged["mode"] = mode
        if mode == "link":
            # Link mode: a hosted donate URL — zero secret custody, no webhook.
            # PaypalConfig.from_dict validates payment_link as an http(s) URL.
            merged["payment_link"] = _as_text(body.get("payment_link"))
        else:
            # REST mode. webhook_url / webhook_id are NOT accepted from the
            # client — auto-provisioned below. Empty client_id / client_secret
            # => leave the stored value unchanged (the GET never returns the secret).
            new_client_id = _as_text(body.get("client_id"))
            if new_client_id:
                merged["client_id"] = new_client_id
            new_client_secret = _as_text(body.get("client_secret"))
            if new_client_secret:
                merged["client_secret"] = new_client_secret
            # plan_id is public (GET returns it), so the form round-trips it;
            # honor it whenever the key is present (allows set AND clear).
            if "plan_id" in body:
                merged["plan_id"] = _as_text(body.get("plan_id"))

        try:
            next_profile = _dc_replace(profile, paypal=PaypalConfig.from_dict(merged))
        except ValueError as exc:
            return jsonify({"ok": False, "error": "validation_failed", "detail": str(exc)}), 400

        # Receipt identity (org legal-name/EIN/tax-status/address/signer/statement).
        # Optional object in the same payload, edited from the dashboard payment tab
        # or the FND portal grantee editor. A blank EIN means "leave the stored EIN
        # unchanged" (the GET masks it), mirroring client_secret semantics.
        if isinstance(body.get("receipt"), dict):
            r_in = body["receipt"]
            merged_r = profile.receipt.to_dict() if profile.receipt else {}
            for k in (
                "legal_name", "tax_status", "mailing_address",
                "signer_name", "signer_title", "acknowledgement_statement",
            ):
                if k in r_in:
                    merged_r[k] = _as_text(r_in.get(k))
            new_ein = _as_text(r_in.get("ein"))
            if new_ein:
                merged_r["ein"] = new_ein
            try:
                next_profile = _dc_replace(next_profile, receipt=ReceiptConfig.from_dict(merged_r))
            except ValueError as exc:
                return jsonify({"ok": False, "error": "validation_failed", "detail": str(exc)}), 400

        try:
            save_grantee_profile(path, next_profile)
        except GranteeProfileWriteError as exc:
            return jsonify({"ok": False, "error": "storage_error", "detail": str(exc)}), 500

        # Auto-provision the donation webhook so the operator never creates one
        # in PayPal or pastes a Webhook ID. Credentials are saved ABOVE first,
        # so any failure here only yields a warning — creds are never lost.
        # Idempotent: a re-save reuses the existing webhook for the same URL.
        webhook_warning = ""
        pp = next_profile.paypal
        client_id = _as_text(pp.client_id) if pp else ""
        client_secret = _as_text(pp.client_secret) if pp else ""
        if mode != "rest":
            pass  # link mode: no REST credentials, no webhook to provision
        elif not (client_id and client_secret):
            webhook_warning = "credentials_incomplete"
        else:
            # Prefer the domain already carried by a stored webhook_url so a
            # re-save never migrates a multi-domain grantee's webhook to a
            # different domain; otherwise use the first domain.
            stored_host = _normalize_domain(
                urllib.parse.urlsplit(_as_text(pp.webhook_url)).netloc
            )
            domains = [_normalize_domain(d) for d in next_profile.domains if _as_text(d)]
            webhook_domain = stored_host if stored_host in domains else (domains[0] if domains else "")
            if not webhook_domain:
                webhook_warning = "no_domain_for_grantee"
            else:
                webhook_url = f"https://{webhook_domain}/__fnd/paypal/webhook"
                base_url = _paypal_base_url(_as_text(pp.environment))
                try:
                    token = _get_paypal_access_token(client_id, client_secret, base_url)
                    wid, wurl = _find_or_create_paypal_webhook(
                        access_token=token,
                        base_url=base_url,
                        url=webhook_url,
                        event_types=_PAYPAL_WEBHOOK_EVENT_TYPES,
                    )
                    merged2 = pp.to_dict()
                    merged2["webhook_id"] = wid
                    merged2["webhook_url"] = wurl
                    next_profile = _dc_replace(next_profile, paypal=PaypalConfig.from_dict(merged2))
                    save_grantee_profile(path, next_profile)
                except Exception as exc:
                    webhook_warning = "provisioning_failed"
                    _log.warning(
                        "paypal_webhook_provision_failed domain=%s detail=%s", webhook_domain, exc
                    )

        return jsonify(
            {
                "ok": True,
                "paypal": _paypal_config_view(next_profile.paypal),
                "receipt": _receipt_config_view(next_profile.receipt),
                "webhook_warning": webhook_warning,
            }
        ), 200

    # ------------------------------------------------------------------
    # FND PayPal order mediation routes (peripheral)
    # ------------------------------------------------------------------

    @app.post("/__fnd/paypal/create-order")
    def fnd_paypal_create_order() -> tuple[Any, int]:
        payload = _json_payload()
        domain = _normalize_domain(request.host)
        amount = _as_text(payload.get("amount"))
        donor_name = _as_text(payload.get("donor_name"))
        donor_email = _as_text(payload.get("donor_email"))
        designation = _as_text(payload.get("designation"))

        # Link mode: the grantee uses a hosted PayPal donate link (no server
        # mediation / secret custody). Return it for the donor JS to redirect
        # to — the amount is collected on PayPal's hosted page, so no amount is
        # required here. Short-circuits before any credential/order logic.
        link_grantee = _load_grantee_for_domain(host_config.private_dir, domain)
        link_cfg = (
            link_grantee.get("paypal")
            if link_grantee and isinstance(link_grantee.get("paypal"), dict)
            else {}
        )
        if _as_text(link_cfg.get("mode")).lower() == "link":
            link = _as_text(link_cfg.get("payment_link"))
            if not link:
                return jsonify({"ok": False, "error": "payment_link_not_set"}), 503
            return jsonify({"ok": True, "mode": "link", "payment_link": link}), 200

        if not amount:
            return jsonify({"ok": False, "error": "missing_amount"}), 400
        try:
            amount_value = Decimal(amount)
        except (InvalidOperation, ValueError):
            return jsonify({"ok": False, "error": "invalid_amount"}), 400
        if not amount_value.is_finite() or amount_value <= 0:
            return jsonify({"ok": False, "error": "invalid_amount"}), 400
        # Normalize to a 2-decimal string PayPal accepts. The raw value was
        # previously forwarded verbatim, so "0", "0.00", "-5", "abc", "NaN" all
        # reached PayPal and surfaced as opaque 502s (or a $0 order).
        amount = f"{amount_value:.2f}"

        private_dir = host_config.private_dir
        domain_profile = _load_domain_profile(private_dir, domain)
        if domain_profile is None:
            return jsonify({"ok": False, "error": "domain_profile_not_found"}), 404

        tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
        tenant_config = _load_tenant_config(private_dir, tenant_ref)
        if tenant_config is None:
            return jsonify({"ok": False, "error": "tenant_config_not_found"}), 503

        credentials = _resolve_paypal_credentials_for_domain(private_dir, domain, tenant_config)
        if credentials is None:
            return jsonify({"ok": False, "error": "credentials_not_set"}), 503

        client_id, client_secret, resolved_env = credentials
        environment = resolved_env or _as_text(domain_profile.get("environment")) or "sandbox"
        base_url = _paypal_base_url(environment)
        checkout_ctx = domain_profile.get("checkout_context", {})
        donation_defaults = domain_profile.get("donation_defaults", {})
        brand_name = _as_text(domain_profile.get("brand_name"))
        custom_id_prefix = _as_text(donation_defaults.get("custom_id_prefix")) or "donation"
        item_description = _as_text(donation_defaults.get("item_description"))
        return_url = _as_text(checkout_ctx.get("return_url"))
        cancel_url = _as_text(checkout_ctx.get("cancel_url"))
        currency_code = _as_text(checkout_ctx.get("currency_code")) or "USD"

        import time as _time
        timestamp_ms = int(_time.time() * 1000)
        custom_id = f"{custom_id_prefix}-{timestamp_ms}"

        try:
            access_token = _get_paypal_access_token(client_id, client_secret, base_url)
            order_result = _create_paypal_order(
                access_token=access_token,
                base_url=base_url,
                body={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "amount": {"currency_code": currency_code, "value": amount},
                        "custom_id": custom_id,
                        "description": item_description,
                    }],
                    "application_context": {
                        "brand_name": brand_name,
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    },
                },
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": "paypal_api_error", "detail": str(exc)}), 502

        order_id = _as_text(order_result.get("id"))
        approval_url = ""
        for link in order_result.get("links", []):
            if isinstance(link, dict) and _as_text(link.get("rel")) == "approve":
                approval_url = _as_text(link.get("href"))
                break

        orders_log = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
        _append_to_ndjson(orders_log, {
            "event": "create_order",
            "order_id": order_id,
            "custom_id": custom_id,
            "domain": domain,
            "amount": amount,
            "currency_code": currency_code,
            "status": _as_text(order_result.get("status")),
            "approval_url": approval_url,
            "donor_name": donor_name,
            "donor_email": donor_email,
            "designation": designation,
            "timestamp_ms": timestamp_ms,
        })

        return jsonify({"ok": True, "order_id": order_id, "approval_url": approval_url,
                        "status": _as_text(order_result.get("status"))}), 200

    def _upsert_donor_contact(domain: str, donor_email: str, donor_name: str) -> str:
        """Resolve-or-create the donor as a contact in the grantee's contact
        log; return the canonical email key (``""`` when no email/failure).

        Mirrors ``fnd_contacts_add``: a NEW contact lands unsubscribed with
        ``source='paypal_donation'``; an EXISTING contact is left as-is on the
        subscribe flag (a donation never re-subscribes a newsletter member).
        Email-keyed, so calling it from both the browser capture and the
        webhook is idempotent. Best-effort — a contact-store failure must never
        fail the capture, exactly like the receipt email.
        """
        email = _as_text(donor_email).strip().lower()
        if not email or host_config.private_dir is None:
            return ""
        try:
            adapter = _newsletter_state_adapter(host_config)
            log = adapter.load_contact_log(domain=domain) or {
                "domain": domain,
                "contacts": [],
                "dispatches": [],
            }
            now_iso = _utc_now_iso()
            contacts = list(log.get("contacts") or [])
            index = next(
                (i for i, c in enumerate(contacts) if _as_text(c.get("email")).lower() == email),
                None,
            )
            existing = contacts[index] if index is not None else None
            patch: dict[str, Any] = {"email": email, "name": donor_name}
            if existing is None:
                patch["source"] = "paypal_donation"
                patch["signup_date"] = now_iso[:10]
                patch["subscribed"] = False
            row = canonical_contact_entry(existing=existing, patch=patch, now=now_iso)
            if index is not None:
                contacts[index] = row
            else:
                contacts.append(row)
            log["contacts"] = contacts
            log["updated_at"] = now_iso
            adapter.save_contact_log(domain=domain, payload=log)
            return _as_text(row.get("email")) or email
        except Exception as exc:
            _log.warning("paypal_donor_contact_upsert_failed domain=%s detail=%s", domain, exc)
            return ""

    def _capture_and_log_paypal_order(domain: str, order_id: str) -> tuple[dict[str, Any], int]:
        """Capture an approved PayPal order + append the result to the single
        order log. Shared by the browser capture route and the webhook
        reconciler. Returns ``(payload, status_code)`` — payload is
        ``{ok, capture_id, status, amount, currency_code}`` on success or
        ``{ok: False, error, ...}`` otherwise.
        """
        private_dir = host_config.private_dir
        domain_profile = _load_domain_profile(private_dir, domain)
        if domain_profile is None:
            return {"ok": False, "error": "domain_profile_not_found"}, 404
        tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
        tenant_config = _load_tenant_config(private_dir, tenant_ref)
        if tenant_config is None:
            return {"ok": False, "error": "tenant_config_not_found"}, 503
        credentials = _resolve_paypal_credentials_for_domain(private_dir, domain, tenant_config)
        if credentials is None:
            return {"ok": False, "error": "credentials_not_set"}, 503
        client_id, client_secret, resolved_env = credentials
        environment = resolved_env or _as_text(domain_profile.get("environment")) or "sandbox"
        base_url = _paypal_base_url(environment)
        orders_log = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"

        def _augment_with_receipt(result: dict[str, Any]) -> dict[str, Any]:
            # On a COMPLETED capture, send the donor acknowledgement once (deduped
            # on capture_id) and expose its status + the optional PDF URL. Shared
            # across the browser route and the webhook CHECKOUT.ORDER.APPROVED path,
            # both of which return through this helper.
            if _as_text(result.get("status")).upper() != "COMPLETED":
                return result
            result["receipt_email_status"] = _send_receipt_for_capture(
                private_dir=private_dir,
                domain=domain,
                orders_log=orders_log,
                order_id=order_id,
                capture_id=_as_text(result.get("capture_id")),
                amount=_as_text(result.get("amount")),
                currency_code=_as_text(result.get("currency_code")),
            )
            if _resolve_receipt_artifact(private_dir, domain) is not None:
                result["receipt_document_url"] = (
                    f"/__fnd/donation/receipt-document?domain={urllib.parse.quote(domain, safe='')}"
                )
            return result

        # Idempotency: if this order was already captured (retry, double-click, or
        # webhook+browser race), return the recorded result instead of re-calling
        # PayPal — a second capture 502s ORDER_ALREADY_CAPTURED for a donor who paid.
        prior_capture = _find_completed_capture_entry(orders_log, order_id)
        if prior_capture is not None:
            return _augment_with_receipt({
                "ok": True,
                "capture_id": _as_text(prior_capture.get("capture_id")),
                "status": _as_text(prior_capture.get("status")) or "COMPLETED",
                "amount": _as_text(prior_capture.get("amount")),
                "currency_code": _as_text(prior_capture.get("currency_code")),
            }), 200
        try:
            access_token = _get_paypal_access_token(client_id, client_secret, base_url)
            capture_result = _capture_paypal_order(
                access_token=access_token, base_url=base_url, order_id=order_id
            )
        except Exception as exc:
            return {"ok": False, "error": "paypal_api_error", "detail": str(exc)}, 502
        status = _as_text(capture_result.get("status"))
        capture_id = capture_amount = currency_code = ""
        purchase_units = capture_result.get("purchase_units", [])
        if purchase_units and isinstance(purchase_units, list) and isinstance(purchase_units[0], dict):
            # PayPal may return payments present-but-null for non-COMPLETED states;
            # `.get("payments", {})` would not guard that, so coerce with `or {}`.
            payments = purchase_units[0].get("payments") or {}
            captures = (payments.get("captures") if isinstance(payments, dict) else None) or []
            if captures and isinstance(captures, list) and isinstance(captures[0], dict):
                capture_id = _as_text(captures[0].get("id"))
                amount_obj = captures[0].get("amount") or {}
                capture_amount = _as_text(amount_obj.get("value"))
                currency_code = _as_text(amount_obj.get("currency_code"))
        import time as _time
        # The capture API response carries no donor identity — recover it from
        # the create-order row and link the donor to a contact (only on a
        # completed capture). Best-effort; never fails the capture.
        create_entry = _find_create_order_entry(orders_log, order_id) or {}
        donor_email = _as_text(create_entry.get("donor_email"))
        donor_name = _as_text(create_entry.get("donor_name"))
        contact_email = (
            _upsert_donor_contact(domain, donor_email, donor_name)
            if status.upper() == "COMPLETED"
            else ""
        )
        _append_to_ndjson(orders_log, {
            "event": "capture_order",
            "order_id": order_id,
            "capture_id": capture_id,
            "domain": domain,
            "amount": capture_amount,
            "currency_code": currency_code,
            "status": status,
            "donor_email": donor_email,
            "donor_name": donor_name,
            "contact_email": contact_email,
            "timestamp_ms": int(_time.time() * 1000),
        })
        return _augment_with_receipt({
            "ok": True,
            "capture_id": capture_id,
            "status": status,
            "amount": capture_amount,
            "currency_code": currency_code,
        }), 200

    @app.post("/__fnd/paypal/capture-order")
    def fnd_paypal_capture_order() -> tuple[Any, int]:
        payload = _json_payload()
        domain = _normalize_domain(request.host)
        order_id = _as_text(payload.get("order_id"))

        if not order_id:
            return jsonify({"ok": False, "error": "missing_order_id"}), 400

        # The shared helper captures, logs, and (on COMPLETED) sends the donor
        # receipt once — deduped on capture_id — returning receipt_email_status
        # and (when a PDF is configured) receipt_document_url in the payload.
        result, code = _capture_and_log_paypal_order(domain, order_id)
        return jsonify(result), code

    @app.post("/__fnd/paypal/webhook")
    def fnd_paypal_webhook() -> tuple[Any, int]:
        """Public PayPal webhook receiver. Verifies the event signature against
        the grantee's configured ``webhook_id``, then reconciles:

          * CHECKOUT.ORDER.APPROVED  -> capture the order server-side (covers a
            donor who approved on PayPal but never returned to the browser
            capture step), then log it.
          * PAYMENT.CAPTURE.COMPLETED -> idempotently record the capture if the
            browser flow hasn't already logged it (dedup on capture_id).

        Returns 2xx only after a verified event has been handled.
        """
        domain = _normalize_domain(request.host)
        private_dir = host_config.private_dir
        if not domain or private_dir is None:
            return jsonify({"ok": False, "error": "missing_domain"}), 400

        event = request.get_json(silent=True)
        if not isinstance(event, dict):
            return jsonify({"ok": False, "error": "invalid_payload"}), 400

        domain_profile = _load_domain_profile(private_dir, domain)
        if domain_profile is None:
            return jsonify({"ok": False, "error": "domain_profile_not_found"}), 404
        tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
        tenant_config = _load_tenant_config(private_dir, tenant_ref)
        if tenant_config is None:
            return jsonify({"ok": False, "error": "tenant_config_not_found"}), 503
        credentials = _resolve_paypal_credentials_for_domain(private_dir, domain, tenant_config)
        if credentials is None:
            return jsonify({"ok": False, "error": "credentials_not_set"}), 503
        client_id, client_secret, resolved_env = credentials
        environment = resolved_env or _as_text(domain_profile.get("environment")) or "sandbox"
        base_url = _paypal_base_url(environment)

        grantee = _load_grantee_for_domain(private_dir, domain) or {}
        paypal_cfg = grantee.get("paypal") if isinstance(grantee.get("paypal"), dict) else {}
        webhook_id = _as_text(paypal_cfg.get("webhook_id"))
        if not webhook_id:
            return jsonify({"ok": False, "error": "webhook_id_not_set"}), 503

        try:
            access_token = _get_paypal_access_token(client_id, client_secret, base_url)
        except Exception as exc:
            return jsonify({"ok": False, "error": "paypal_api_error", "detail": str(exc)}), 502

        if not _verify_paypal_webhook_signature(
            access_token=access_token,
            base_url=base_url,
            headers=request.headers,
            webhook_id=webhook_id,
            event_body=event,
        ):
            return jsonify({"ok": False, "error": "signature_verification_failed"}), 400

        import time as _time

        event_type = _as_text(event.get("event_type")).upper()
        resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
        orders_log = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"

        if event_type == "CHECKOUT.ORDER.APPROVED":
            order_id = _as_text(resource.get("id"))
            if not order_id:
                return jsonify({"ok": False, "error": "missing_order_id"}), 400
            result, _code = _capture_and_log_paypal_order(domain, order_id)
            return jsonify(
                {"ok": True, "event_type": event_type, "captured": bool(result.get("ok"))}
            ), 200

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            capture_id = _as_text(resource.get("id"))
            amount_obj = resource.get("amount") if isinstance(resource.get("amount"), dict) else {}
            related = {}
            supp = resource.get("supplementary_data")
            if isinstance(supp, dict) and isinstance(supp.get("related_ids"), dict):
                related = supp["related_ids"]
            if capture_id and not _ndjson_has_capture(orders_log, capture_id):
                # Donor identity isn't on the webhook resource — recover it
                # from the create-order row and link the donor to a contact.
                order_id = _as_text(related.get("order_id"))
                create_entry = _find_create_order_entry(orders_log, order_id) or {}
                donor_email = _as_text(create_entry.get("donor_email"))
                donor_name = _as_text(create_entry.get("donor_name"))
                contact_email = _upsert_donor_contact(domain, donor_email, donor_name)
                _append_to_ndjson(orders_log, {
                    "event": "webhook_capture",
                    "order_id": order_id,
                    "capture_id": capture_id,
                    "domain": domain,
                    "amount": _as_text(amount_obj.get("value")),
                    "currency_code": _as_text(amount_obj.get("currency_code")),
                    "status": _as_text(resource.get("status")) or "COMPLETED",
                    "donor_email": donor_email,
                    "donor_name": donor_name,
                    "contact_email": contact_email,
                    "timestamp_ms": int(_time.time() * 1000),
                })
                # Webhook-reconciled donations (donor approved on PayPal but never
                # returned to the browser capture step) get the same donor receipt
                # the browser path sends — deduped on capture_id so a browser+webhook
                # race never double-sends.
                _send_receipt_for_capture(
                    private_dir=private_dir,
                    domain=domain,
                    orders_log=orders_log,
                    order_id=order_id,
                    capture_id=capture_id,
                    amount=_as_text(amount_obj.get("value")),
                    currency_code=_as_text(amount_obj.get("currency_code")),
                    donor_email=donor_email,
                    donor_name=donor_name,
                )
            return jsonify({"ok": True, "event_type": event_type, "recorded": True}), 200

        # Verified, but not an event type we reconcile — acknowledge it.
        return jsonify({"ok": True, "event_type": event_type, "handled": False}), 200

    @app.get("/__fnd/donation/receipt-document")
    def fnd_donation_receipt_document() -> Any:
        """Serve the configured tax-exempt receipt PDF for a domain.

        The artifact path is read from the domain profile's
        ``donation_defaults.receipt_artifact_path`` and joined under the
        fixed ``/srv/webapps/clients/_shared/site-core/document/`` parent.
        Path-traversal attempts (``..``, absolute paths, symlink escape)
        and unconfigured/missing files all collapse to 404 so the route
        does not leak validation signal.
        """
        from flask import send_from_directory

        domain = _normalize_domain(_as_text(request.args.get("domain")) or request.host)
        if not domain:
            abort(404)
        private_dir = host_config.private_dir
        receipt_path = _resolve_receipt_artifact(private_dir, domain)
        if receipt_path is None:
            abort(404)
        return send_from_directory(
            str(receipt_path.parent),
            receipt_path.name,
            as_attachment=True,
        )

    # ------------------------------------------------------------------
    # Tolling — per-grantee cost itemization. Consumed by the per-client
    # /dashboard/ static surfaces (proxied same-origin from the client
    # vhost to keep CORS off the critical path).
    #
    # Scope-guard + period helpers (`_resolve_grantee_scope`,
    # `_parse_period_args`) are defined further down where the
    # grantee-summary route lives; all routes in this block use them.
    # ------------------------------------------------------------------

    @app.get("/__fnd/tolling/itemize")
    def fnd_tolling_itemize() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            bandwidth_share_for_grantee,
            compute_bandwidth_cost,
            domains_for_grantee,
        )
        from MyCiteV2.packages.peripherals.aws.contracts import CostBreakdown

        requested_msn, err = _resolve_grantee_scope()
        if err:
            return err
        start_d, end_d, err = _parse_period_args()
        if err:
            return err

        # Cost Explorer slice.
        cost: CostBreakdown = _aws_peripheral.get_costs_by_grantee(
            msn_id=requested_msn,
            start=start_d.isoformat(),
            end=end_d.isoformat(),
        )

        # Bandwidth share from nginx access logs (no MOS dependency).
        bandwidth = bandwidth_share_for_grantee(
            requested_msn, start_d, end_d
        )

        # Bandwidth dollar attribution: account-wide EC2
        # DataTransfer-Out spend × this grantee's share. Approximates
        # per-tenant egress cost on the shared instance.
        dt = _aws_peripheral.get_data_transfer_out_cost(
            start=start_d.isoformat(), end=end_d.isoformat()
        )
        attribution = compute_bandwidth_cost(bandwidth, dt)
        bandwidth_cost = {
            "currency": attribution["currency"],
            "amount": f"{attribution['amount_value']:.10f}",
            "account_total": attribution["account_total"],
        }

        return jsonify({
            "ok": True,
            "grantee": {
                "msn_id": requested_msn,
                "domains": domains_for_grantee(requested_msn),
            },
            "period": {
                "start": start_d.isoformat(),
                "end": end_d.isoformat(),
            },
            "costs": cost,
            "bandwidth_share": bandwidth,
            "bandwidth_cost": bandwidth_cost,
        }), 200

    @app.get("/__fnd/tolling/overview")
    def fnd_tolling_overview() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            OPERATOR_MSN_ID,
            bandwidth_share_by_domain,
            load_grantee_directory,
            resolve_grantee_from_headers,
        )

        # Operator-only: this returns EVERY grantee's costs + the full roster.
        # A scoped (client) caller arrives through the per-grantee /dashboard/api/
        # proxy carrying its own X-Auth-Request-Grantee header, so reject anyone
        # who resolves to a non-operator grantee. (Mirrors the ledger/billing-rules
        # gate; the operator surface is header-absent and still passes.)
        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is not None and str(caller.get("msn_id")) != OPERATOR_MSN_ID:
            return jsonify({"ok": False, "error": "operator_only"}), 403

        start_d, end_d, err = _parse_period_args()
        if err:
            return err

        overview = _aws_peripheral.get_costs_overview(
            start=start_d.isoformat(), end=end_d.isoformat()
        )
        bandwidth = bandwidth_share_by_domain(start_d, end_d)
        grantees = [
            {
                "msn_id": _as_text(p.get("msn_id")),
                "short_name": _as_text(p.get("short_name")),
                "label": _as_text(p.get("label")),
                "domains": [str(d) for d in p.get("domains") or []],
            }
            for p in load_grantee_directory()
        ]

        return jsonify({
            "ok": True,
            "period": {
                "start": start_d.isoformat(),
                "end": end_d.isoformat(),
            },
            "grantees": grantees,
            "costs_by_msn_id": overview,
            "bandwidth_share_by_domain": bandwidth,
        }), 200

    # Note: _ANALYTICS_SUMMARY_CACHE + _ANALYTICS_SUMMARY_TTL are
    # declared earlier in the route-registration block so the refresh
    # handler can invalidate entries.

    @app.get("/__fnd/analytics/summary")
    def fnd_analytics_summary() -> tuple[Any, int]:
        """Per-grantee analytics rollup for the dashboard Analytics tab.

        Reads the monthly analytics leaflets at
        /srv/webapps/clients/_shared/site-core/analytics/
        <YYYY-MM>-00.record-analytics.<entity>-website.<month>_analytics.yaml,
        flattens them to the event shape the derivations consume, filters by
        the requested window + non-bot, and returns totals, top pages, and the
        widget aggregates. Window is inclusive on both ends.
        """
        import time as _time

        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            domains_for_grantee,
        )

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500

        requested_msn, err = _resolve_grantee_scope()
        if err:
            return err
        start_d, end_d, err = _parse_period_args()
        if err:
            return err

        cache_gen = _analytics_cache_gen()
        cache_key = (requested_msn, start_d.isoformat(), end_d.isoformat(), cache_gen)
        now = _time.monotonic()
        cached = _ANALYTICS_SUMMARY_CACHE.get(cache_key)
        if cached is not None and now - cached[0] < _ANALYTICS_SUMMARY_TTL:
            return jsonify(cached[1]), 200
        # Lightweight eviction: when the gen bumps, old keys are stale.
        # Drop any cache entry whose key carries a gen lower than the
        # current one. Cheap because the cache holds at most a handful
        # of (msn, start, end) tuples per generation.
        if cache_gen:
            for stale_key in [k for k in _ANALYTICS_SUMMARY_CACHE if k[3] < cache_gen]:
                _ANALYTICS_SUMMARY_CACHE.pop(stale_key, None)

        domains = domains_for_grantee(
            requested_msn, fnd_csm_root=_configured_fnd_csm_root()
        )

        from collections import Counter as _Counter

        from MyCiteV2.packages.adapters.filesystem import (
            AnalyticsLeafletStore,
            entity_for_domain,
        )
        from MyCiteV2.packages.core.analytics import derivations as _derivations
        from MyCiteV2.packages.core.analytics import leaflet_model as _lm

        # One entity owns a grantee's domain(s) (CVCC owns two). The monthly
        # leaflets are keyed by entity, so resolve it from the first domain.
        entity = entity_for_domain(domains[0]) if domains else ""

        # Leaflets are one file per (entity, YYYY-MM). Enumerate every month
        # that overlaps the requested window.
        months: list[str] = []
        cursor = start_d.replace(day=1)
        while cursor <= end_d:
            months.append(cursor.strftime("%Y-%m"))
            year, month = cursor.year, cursor.month
            cursor = cursor.replace(year=year + 1, month=1) if month == 12 \
                else cursor.replace(month=month + 1)

        store = AnalyticsLeafletStore(
            private_dir=host_config.private_dir,
            webapps_root=_analytics_webapps_root(),
        )

        # Flatten every in-window leaflet month into the flat event shape the
        # derivations consume, then filter to [from, to] (inclusive both ends:
        # the dashboard's MTD/7d/30d presets set `to` to today, and a user
        # reading "through 2026-05-21" expects that day's events to count).
        all_events: list[dict[str, Any]] = []
        for leaflet in store.read_range(entity, months):
            for ev in _lm.flatten_events(leaflet):
                occurred = _as_text(ev.get("occurred_at_utc"))[:10]
                if occurred < start_d.isoformat() or occurred > end_d.isoformat():
                    continue
                all_events.append(ev)

        total_events = 0
        bot_events = 0
        unique_visitors: set[str] = set()
        page_counts: dict[str, int] = {}
        referrer_counts: dict[str, int] = {}
        event_type_counts: dict[str, int] = {}
        device_counts: dict[str, int] = {}
        for event in all_events:
            total_events += 1
            if event.get("is_bot"):
                bot_events += 1
                continue
            visitor = _as_text(event.get("visitor_cookie_id_hash"))
            if visitor:
                unique_visitors.add(visitor)
            page = _as_text(event.get("page_path")) or "/"
            page_counts[page] = page_counts.get(page, 0) + 1
            et = _as_text(event.get("event_type")) or "(unknown)"
            event_type_counts[et] = event_type_counts.get(et, 0) + 1
            ref = _as_text(event.get("referrer_domain"))
            if ref:
                referrer_counts[ref] = referrer_counts.get(ref, 0) + 1
            dev = _as_text(event.get("device_type"))
            if dev:
                device_counts[dev] = device_counts.get(dev, 0) + 1

        def _top(d: dict[str, int], n: int = 10) -> list[dict[str, int | str]]:
            return [{"key": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]]

        # Schema-v3 / JSON Analytics Log Vision derivations.
        humans, bots = _derivations.filter_bots(all_events)
        sessions = _derivations.sessionize(humans)

        # Visitor summaries — top 10 by total active time.
        visitor_tokens: list[str] = []
        seen_v: set[str] = set()
        for ev in humans:
            t = _as_text(ev.get("visitor_cookie_id_hash"))
            if t and t not in seen_v:
                seen_v.add(t)
                visitor_tokens.append(t)
        v_summaries = [
            _derivations.visitor_summary(humans, vt) for vt in visitor_tokens
        ]
        v_summaries.sort(key=lambda v: v.get("total_active_time_ms") or 0, reverse=True)
        visitor_summary_top10 = v_summaries[:10]

        # Interest-category rollup across all visitors.
        interest_counts: _Counter = _Counter()
        interest_total_views = 0
        for vt in visitor_tokens:
            prof = _derivations.visitor_interest_profile(humans, vt)
            for cat, info in (prof.get("categories") or {}).items():
                interest_counts[cat] += info.get("hits", 0)
            interest_total_views += prof.get("total_page_views", 0)
        interest_profile_categories = (
            [
                {
                    "category": cat,
                    "hits": hits,
                    "pct_of_views": round(100 * hits / interest_total_views, 2)
                    if interest_total_views
                    else 0.0,
                }
                for cat, hits in interest_counts.most_common()
            ]
            if interest_total_views
            else []
        )

        abandoned = _derivations.abandoned_intent_sessions(sessions)
        dead_ends = _derivations.dead_end_pages(sessions)
        assists = _derivations.conversion_assisting_pages(humans)
        origin_dist = _derivations.traffic_origin_classification(humans)

        # Bot-classifier breakdown for the bot_separation widget.
        bot_class_counts: _Counter = _Counter()
        for ev in bots:
            bot_class_counts[_as_text(ev.get("bot_class")) or "unclassified"] += 1
        bot_separation = {
            "human_events": len(humans),
            "bot_events": len(bots),
            "bot_class_breakdown": [
                {"bot_class": k, "count": v}
                for k, v in bot_class_counts.most_common()
            ],
        }

        # Quality-flag triage histogram (operator-only payload key).
        quality_flag_counts: _Counter = _Counter()
        for ev in all_events:
            for tok in ev.get("quality_flags") or []:
                quality_flag_counts[tok] += 1
        debugging_triage_buckets = [
            {"flag": flag, "count": count}
            for flag, count in quality_flag_counts.most_common()
        ]

        # Pie-chart-friendly aggregates for the Overview sub-tab. Each is a
        # ranked [{key, count}] list (plus the human/bot split) the dashboard
        # renders as a donut + legend.
        widgets = {
            "referrers_by_sessions": [
                {"key": r["referrer_domain"], "count": r["sessions"]}
                for r in _derivations.rank_referrers(humans, top_k=8)
            ],
            "origin_distribution": [
                {"key": k, "count": v.get("sessions", 0)}
                for k, v in sorted(
                    origin_dist.items(), key=lambda kv: -kv[1].get("sessions", 0)
                )
            ],
            "device_split": [
                {"key": k, "count": v}
                for k, v in sorted(device_counts.items(), key=lambda kv: -kv[1])
            ],
            "human_vs_bot": [
                {"key": "human", "count": len(humans)},
                {"key": "bot", "count": len(bots)},
            ],
            "bot_class_breakdown": [
                {"key": b["bot_class"], "count": b["count"]}
                for b in bot_separation["bot_class_breakdown"]
            ],
        }

        payload = {
            "ok": True,
            "grantee": {"msn_id": requested_msn, "domains": domains},
            "period": {
                "start": start_d.isoformat(),
                "end": end_d.isoformat(),
            },
            "summary": {
                "total_events": total_events,
                "human_events": total_events - bot_events,
                "bot_events": bot_events,
                "unique_visitors": len(unique_visitors),
                "event_types": event_type_counts,
            },
            "top_pages": _top(page_counts, 10),
            "top_referrers": _top(referrer_counts, 10),
            "widgets": widgets,
            # Schema-v3 / JSON Analytics Log Vision rollups.
            "visitor_summary_top10": visitor_summary_top10,
            "interest_profile_categories": interest_profile_categories,
            "abandoned_intent_sessions": {
                "count": len(abandoned),
                "sample": abandoned[:10],
            },
            "dead_end_pages": dead_ends,
            "conversion_assisting_pages": assists,
            "origin_type_distribution": origin_dist,
            "bot_separation": bot_separation,
        }
        # Operator-only diagnostic block. Grantee-context callers
        # (oauth2-proxy attached X-Auth-Request-Grantee header) never
        # see it; their dashboard JS hides the section when the key
        # is absent. Operator context = header missing.
        if _is_operator_request():
            payload["debugging"] = {
                "quality_flag_buckets": debugging_triage_buckets,
            }
        _ANALYTICS_SUMMARY_CACHE[cache_key] = (now, payload)
        return jsonify(payload), 200

    @app.get("/__fnd/analytics/records")
    def fnd_analytics_records() -> tuple[Any, int]:
        """Per-grantee monthly leaflet records for the Records sub-tab.

        Without ``?period=`` → the list of available ``YYYY-MM`` periods plus
        the newest month's leaflet. With ``?period=YYYY-MM`` → that month's
        leaflet (visitors → sessions → events) for the per-month table view.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            domains_for_grantee,
        )
        from MyCiteV2.packages.adapters.filesystem import (
            AnalyticsLeafletStore,
            entity_for_domain,
        )

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        requested_msn, err = _resolve_grantee_scope()
        if err:
            return err
        domains = domains_for_grantee(
            requested_msn, fnd_csm_root=_configured_fnd_csm_root()
        )
        entity = entity_for_domain(domains[0]) if domains else ""
        store = AnalyticsLeafletStore(
            private_dir=host_config.private_dir,
            webapps_root=_analytics_webapps_root(),
        )
        periods = store.available_periods(entity)
        period = _as_text(request.args.get("period"))
        if not period and periods:
            period = periods[-1]
        leaflet = store.load_month(entity, period) if period else None
        return jsonify({
            "ok": True,
            "grantee": {"msn_id": requested_msn, "domains": domains},
            "periods": periods,
            "period": period,
            "leaflet": leaflet,
        }), 200

    @app.route("/__fnd/analytics/campaigns", methods=["GET", "POST"])
    def fnd_analytics_campaigns() -> tuple[Any, int]:
        """Pre-tracked link + QR campaigns for the Campaigns sub-tab.

        GET  → list campaigns with attributed session/visitor counts.
        POST → create a campaign (mint token); returns the row + tracked URL.
        Scope-guarded: a grantee only ever sees/creates its own campaigns.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            domains_for_grantee,
        )
        from MyCiteV2.packages.adapters.filesystem import (
            AnalyticsLeafletStore,
            CampaignLeafletStore,
            entity_for_domain,
        )

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        requested_msn, err = _resolve_grantee_scope()
        if err:
            return err
        domains = domains_for_grantee(
            requested_msn, fnd_csm_root=_configured_fnd_csm_root()
        )
        primary_domain = domains[0] if domains else ""
        entity = entity_for_domain(primary_domain) if primary_domain else ""
        cstore = CampaignLeafletStore(
            private_dir=host_config.private_dir,
            webapps_root=_analytics_webapps_root(),
        )

        if request.method == "POST":
            body = _json_payload()
            try:
                row = cstore.add_campaign(
                    entity,
                    primary_domain,
                    label=_as_text(body.get("label")),
                    target_path=_as_text(body.get("target_path")) or "/",
                    source=_as_text(body.get("source")),
                    medium=_as_text(body.get("medium")) or "link",
                    notes=_as_text(body.get("notes")),
                )
            except ValueError as exc:
                return jsonify({"ok": False, "error": "invalid_campaign", "detail": str(exc)}), 400
            row["tracked_url"] = _campaign_tracked_url(primary_domain, row)
            return jsonify({"ok": True, "campaign": row}), 200

        # GET — list + attribute. Counts are tallied over the leaflets in a
        # bounded recent window so the list reflects real usage without a full
        # historical scan.
        store = AnalyticsLeafletStore(
            private_dir=host_config.private_dir,
            webapps_root=_analytics_webapps_root(),
        )
        periods = store.available_periods(entity)[-6:]
        token_sessions: dict[str, int] = {}
        token_visitors: dict[str, set[str]] = {}
        for leaflet in store.read_range(entity, periods):
            for v in leaflet.get("visitors") or []:
                cookie = v.get("visitor_cookie_id_hash") or ""
                for s in v.get("sessions") or []:
                    tok = ((s.get("routed_from") or {}).get("campaign_token")) or ""
                    if not tok:
                        continue
                    token_sessions[tok] = token_sessions.get(tok, 0) + 1
                    token_visitors.setdefault(tok, set()).add(cookie)
        campaigns = []
        for c in cstore.list_campaigns(entity):
            tok = c.get("token") or ""
            campaigns.append({
                **c,
                "tracked_url": _campaign_tracked_url(primary_domain, c),
                "attributed_sessions": token_sessions.get(tok, 0),
                "attributed_visitors": len(token_visitors.get(tok, set())),
            })
        return jsonify({
            "ok": True,
            "grantee": {"msn_id": requested_msn, "domains": domains},
            "primary_domain": primary_domain,
            "campaigns": campaigns,
        }), 200

    @app.get("/__fnd/newsletter/contacts")
    def fnd_newsletter_contacts() -> tuple[Any, int]:
        """Read-only contact list for a grantee's first domain. Used
        by the grantee dashboard's Contacts tab; scope-guarded so
        only the owning grantee (or unauthenticated operator) sees it.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            domains_for_grantee,
        )

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500

        requested_msn, err = _resolve_grantee_scope()
        if err:
            return err

        domains = domains_for_grantee(requested_msn)
        # The contact ROSTER lives in the per-entity YAML leaflet now, not the
        # legacy JSON contact log (which holds dispatch history only). Read the
        # COMPOSED view via the adapter so this list isn't empty/stale after the
        # contacts cutover — same single-source-of-truth path the dashboard
        # aggregator uses.
        adapter = _newsletter_state_adapter(host_config)
        contacts: list[dict[str, Any]] = []
        for d in domains:
            data = adapter.load_contact_log(domain=d) or {}
            for c in data.get("contacts") or []:
                contacts.append({**c, "_domain": d})
        contacts.sort(key=lambda c: str(c.get("email", "")))
        active = sum(1 for c in contacts if c.get("subscribed"))
        return jsonify({
            "ok": True,
            "grantee": {
                "msn_id": requested_msn,
                "domains": domains,
            },
            "summary": {
                "total": len(contacts),
                "active": active,
                "unsubscribed": len(contacts) - active,
            },
            "contacts": contacts,
        }), 200

    @app.post("/__fnd/newsletter/inbound-capture")
    def fnd_newsletter_inbound_capture() -> tuple[Any, int]:
        """Endpoint the `newsletter-inbound-capture` Lambda calls when
        SES captures an email to a configured `news@<domain>` address.

        Flow:
          1. Lambda extracts {domain, sender, recipient, subject,
             ses_message_id, s3_uri, captured_at} from the SES event
             + computes an HMAC over them with the per-tenant secret
             from Secrets Manager. Signs the payload + POSTs here with
             the signature in the `X-Newsletter-Inbound-Signature`
             header (and in the body, for convenience).
          2. We pull the per-tenant SUBMITTER ALLOWLIST from the
             grantee newsletter profile (`allowed_submitters` list,
             or the existing `selected_author_address` as a fallback)
             and reject 403 if the sender isn't on it.
          3. We hand off to NewsletterService.process_inbound_capture,
             which re-validates the signature, reads the S3 object,
             extracts the MIME body, and enqueues one SQS message per
             active contact (each with its own unsubscribe URL+token).
        """
        from MyCiteV2.packages.adapters.event_transport import (
            NewsletterCloudAdapter,
        )
        from MyCiteV2.packages.adapters.filesystem import (
            FilesystemNewsletterStateAdapter,
        )
        from MyCiteV2.packages.modules.cross_domain.newsletter import (
            NewsletterService,
        )

        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500

        body = _json_payload()
        signature = (
            _as_text(request.headers.get("X-Newsletter-Inbound-Signature"))
            or _as_text(body.get("signature"))
        )
        domain = _as_text(body.get("domain")).lower()
        sender = _as_text(body.get("sender")).lower()
        recipient = _as_text(body.get("recipient")).lower()
        ses_message_id = _as_text(body.get("ses_message_id"))
        s3_uri = _as_text(body.get("s3_uri"))
        subject = _as_text(body.get("subject"))
        captured_at = _as_text(body.get("captured_at"))

        if not all([signature, domain, sender, recipient, ses_message_id, s3_uri, captured_at]):
            return jsonify({"ok": False, "error": "missing_fields"}), 400

        # Submitter allowlist. The per-domain newsletter profile
        # carries `allowed_submitters` (list of normalized emails).
        # When set, it is THE canonical list — the author identity is
        # not implicitly allowed (the "who can send FROM" identity is
        # different from "who can SUBMIT TO news@"). When the field is
        # absent we fall back to `selected_author_address` for
        # backward-compat with any flow that authored via the SES
        # identity directly.
        state = FilesystemNewsletterStateAdapter(Path(host_config.private_dir))
        profile = state.load_profile(domain=domain) or {}
        explicit_allowlist = [
            _as_text(e).lower()
            for e in (profile.get("allowed_submitters") or [])
            if _as_text(e)
        ]
        if explicit_allowlist:
            allowed = set(explicit_allowlist)
        else:
            author = _as_text(profile.get("selected_author_address")).lower()
            allowed = {author} if author else set()
        if not allowed:
            _log.warning(
                "newsletter_inbound_no_allowlist",
                extra={"domain": domain, "sender": sender},
            )
            return jsonify({"ok": False, "error": "no_allowlist_configured"}), 403
        if sender not in allowed:
            _log.warning(
                "newsletter_inbound_blocked_sender",
                extra={"domain": domain, "sender": sender, "allowed": sorted(allowed)},
            )
            return jsonify({"ok": False, "error": "sender_not_allowed"}), 403

        # Hand off to the canonical processor (it re-validates the
        # signature against Secrets Manager; we don't trust the local
        # check alone).
        tenant_id = _as_text(host_config.portal_instance_id) or "fnd"
        service = NewsletterService(
            state, NewsletterCloudAdapter(), tenant_id=tenant_id
        )
        callback_base = f"https://{domain}/__fnd/newsletter"
        try:
            result = service.process_inbound_capture(
                signature=signature,
                domain=domain,
                ses_message_id=ses_message_id,
                s3_uri=s3_uri,
                sender=sender,
                recipient=recipient,
                subject=subject,
                captured_at=captured_at,
                dispatcher_callback_url=f"{callback_base}/dispatch-result",
                inbound_callback_url=f"{callback_base}/inbound-capture",
            )
        except PermissionError as exc:
            _log.warning("newsletter_inbound_bad_signature",
                         extra={"domain": domain, "err": str(exc)})
            return jsonify({"ok": False, "error": "bad_signature"}), 403
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        except Exception as exc:
            _log.error("newsletter_inbound_dispatch_failed",
                       extra={"domain": domain, "err": str(exc)})
            return jsonify({"ok": False, "error": "dispatch_failed"}), 500

        return jsonify({"ok": True, **result}), 200

    def _resolve_event_scope() -> tuple[str | None, tuple[Any, int] | None]:
        """Resolve the calling grantee's client slug for the generic
        /__fnd/events/* routes.

        Returns ``(client_slug, None)`` on success or ``(None, error)``
        on a scope problem. An unauthenticated operator (header-absent,
        no matching grantee for the host) resolves to ``client_slug =
        None`` — i.e. an unscoped view across every client's events,
        which is the operator surface. A scoped client caller resolves to
        its own slug (derived from the grantee label/short_name the same
        way the migration derives ``client``), so it only ever sees and
        writes its own events.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.events import (
            _client_slug,
        )
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            grantee_for_domain,
            resolve_grantee_from_headers,
        )

        caller = resolve_grantee_from_headers(
            request.headers, fnd_csm_root=_configured_fnd_csm_root()
        )
        if caller is None:
            caller = grantee_for_domain(
                _normalize_domain(request.host),
                fnd_csm_root=_configured_fnd_csm_root(),
            )
        if caller is None:
            # Operator surface: unscoped.
            return None, None
        # Prefer the human label (gives e.g. "brocks_pressure_washing",
        # matching the migration), fall back to short_name.
        slug_source = str(caller.get("label") or caller.get("short_name") or "")
        client_slug = _client_slug(slug_source)
        if not client_slug or client_slug == "unknown":
            return None, (
                jsonify({"ok": False, "error": "client_unresolved"}),
                403,
            )
        return client_slug, None

    @app.get("/__fnd/events/list")
    def fnd_events_list() -> tuple[Any, int]:
        """Return the calling client's event leaflets + KPI summary,
        read from the shared events gallery under
        <webapps_root>/clients/_shared/site-core/events/. Grantee-scoped:
        a client sees only its own events; an unauthenticated operator
        sees all."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.events import (
            events_summary,
            list_events,
        )
        client, err = _resolve_event_scope()
        if err:
            return err
        rows = list_events(host_config.webapps_root, client=client)
        return jsonify({
            "ok": True,
            "summary": events_summary(rows),
            "events": rows,
            # Legacy alias so pre-migration dashboard JS keeps rendering.
            "jobs": rows,
        }), 200

    @app.get("/__fnd/events/analytics")
    def fnd_events_analytics() -> tuple[Any, int]:
        """Richer analytics for the dashboard Analytics section:
        revenue-by-month, lead-source / status / tag-type breakdowns,
        per-service price distribution with quartiles + Tukey fences.
        Grantee-scoped."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.events import (
            aggregate_analytics,
            events_summary,
            list_events,
        )
        client, err = _resolve_event_scope()
        if err:
            return err
        # Glob the gallery once and feed the same rows to both aggregators
        # so the dashboard's KPI strip (renderKpis(analytics.summary)) and
        # the breakdowns derive from one read.
        rows = list_events(host_config.webapps_root, client=client)
        return jsonify(
            {
                "ok": True,
                "summary": events_summary(rows),
                **aggregate_analytics(rows),
            }
        ), 200

    @app.get("/__fnd/custom/list")
    def fnd_custom_list() -> tuple[Any, int]:
        """Return the calling client's artifact-custom residual leaflets
        (read-only) for the dashboard CUSTOM subtab. Grantee-scoped via the same
        resolver as /events/*; these carry PII so a scoped client sees only its
        own, an unauthenticated operator sees all."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.resources_extension import (
            custom_detail,
        )
        client, err = _resolve_event_scope()
        if err:
            return err
        detail = custom_detail(host_config.webapps_root, client=client)
        return jsonify({"ok": True, **detail}), 200

    @app.post("/__fnd/events/save")
    def fnd_events_save() -> tuple[Any, int]:
        """Create or update an event leaflet. Accepts the dashboard's
        flat form (event_id / date / status / title / location /
        description / leaflet_url) plus optional nested job-kind extras
        (customer / home / tags / pricing / notes) and optional
        event_kind; missing fields filled with sensible defaults (auto
        id, today, status=booked). The client slug is forced to the
        calling grantee's so a caller can't write into another client's
        namespace."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.events import (
            save_event,
        )
        client, err = _resolve_event_scope()
        if err:
            return err
        if client is None:
            # The operator surface has no single client to attribute a
            # write to; require a scoped caller for create/update.
            return jsonify({"ok": False, "error": "client_required"}), 400
        body = _json_payload()
        if not isinstance(body, dict) or not body:
            return jsonify({"ok": False, "error": "missing_payload"}), 400
        try:
            saved = save_event(body, webapps_root=host_config.webapps_root, client=client)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            _log.error("events_save_failed", extra={"err": str(exc)})
            return jsonify({"ok": False, "error": "save_failed"}), 500
        return jsonify({"ok": True, "event": saved, "job": saved}), 200

    @app.delete("/__fnd/events/<event_id>")
    def fnd_events_delete(event_id: str) -> tuple[Any, int]:
        """Remove an event leaflet by top-level `id`, within the calling
        client's scope."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.events import (
            delete_event,
        )
        client, err = _resolve_event_scope()
        if err:
            return err
        if not delete_event(
            event_id, webapps_root=host_config.webapps_root, client=client
        ):
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify({"ok": True, "id": event_id}), 200

    # ------------------------------------------------------------------
    # Backward-compat aliases: the old BPW-specific /__fnd/bpw-jobs/*
    # routes now delegate to the generic events handlers above. They
    # remain so any cached/older dashboard JS keeps working through the
    # migration; new code should call /__fnd/events/*.
    # ------------------------------------------------------------------

    @app.get("/__fnd/bpw-jobs/list")
    def fnd_bpw_jobs_list() -> tuple[Any, int]:
        return fnd_events_list()

    @app.get("/__fnd/bpw-jobs/analytics")
    def fnd_bpw_jobs_analytics() -> tuple[Any, int]:
        return fnd_events_analytics()

    @app.post("/__fnd/bpw-jobs/save")
    def fnd_bpw_jobs_save() -> tuple[Any, int]:
        return fnd_events_save()

    @app.delete("/__fnd/bpw-jobs/<job_id>")
    def fnd_bpw_jobs_delete(job_id: str) -> tuple[Any, int]:
        return fnd_events_delete(job_id)

    @app.get("/__fnd/tolling/snapshot")
    def fnd_tolling_snapshot() -> tuple[Any, int]:
        """Read the persisted tolling JSON for a grantee. This is what
        the per-client `/dashboard/` fetches — no live AWS calls per
        page-load. The JSON is refreshed by the operator on demand via
        /__fnd/tolling/refresh."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            read_tolling_snapshot,
        )

        requested_msn, err = _resolve_grantee_scope()
        if err:
            return err

        snapshot = read_tolling_snapshot(requested_msn)
        return jsonify({"ok": True, **snapshot}), 200

    @app.post("/__fnd/tolling/refresh")
    def fnd_tolling_refresh() -> tuple[Any, int]:
        """Operator action: rebuild the operator ledger for `period`
        from live AWS + nginx logs, then derive every grantee's invoice
        from the ledger × billing rules. Operator-only."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            refresh_all,
            resolve_grantee_from_headers,
        )

        # Operator-only — reject any logged-in grantee caller. No
        # oauth2-proxy headers = operator context (dev tooling, cron).
        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is not None:
            return jsonify({"ok": False, "error": "operator_only"}), 403

        period = _as_text(request.args.get("period"))
        if not period:
            period = datetime.now(UTC).date().strftime("%Y-%m")

        try:
            result = refresh_all(period, aws_peripheral=_aws_peripheral)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            _log.error("tolling_refresh_failed",
                       extra={"period": period, "err": str(exc)})
            return jsonify({"ok": False, "error": "refresh_failed"}), 500

        return jsonify(result), 200

    @app.get("/__fnd/tolling/ledger")
    def fnd_tolling_ledger() -> tuple[Any, int]:
        """Operator-only: read the raw operator ledger row for a period.

        Returns every itemized AWS line for the month with attribution
        (direct/shared_pool/residue) and totals. Used by the FND
        dashboard's operator panel to render the raw cost view + drive
        the rate-card editor.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            OPERATOR_MSN_ID,
            read_ledger_row,
            resolve_grantee_from_headers,
        )

        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is not None and str(caller.get("msn_id")) != OPERATOR_MSN_ID:
            return jsonify({"ok": False, "error": "operator_only"}), 403

        period = _as_text(request.args.get("period"))
        if not period:
            period = datetime.now(UTC).date().strftime("%Y-%m")

        row = read_ledger_row(period)
        if row is None:
            return jsonify({"ok": True, "period": period, "empty": True}), 200
        return jsonify({"ok": True, "period": period, "row": row}), 200

    @app.get("/__fnd/tolling/billing-rules")
    def fnd_tolling_billing_rules_get() -> tuple[Any, int]:
        """Operator-only: read the current billing rules (margins, waivers, pool splits)."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            OPERATOR_MSN_ID,
            read_billing_rules,
            resolve_grantee_from_headers,
        )

        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is not None and str(caller.get("msn_id")) != OPERATOR_MSN_ID:
            return jsonify({"ok": False, "error": "operator_only"}), 403
        return jsonify({"ok": True, "rules": read_billing_rules()}), 200

    @app.post("/__fnd/tolling/billing-rules")
    def fnd_tolling_billing_rules_set() -> tuple[Any, int]:
        """Operator-only: persist updated billing rules. Body is the
        full rules JSON. Validation: margin_pct ∈ [0, 1000], schema
        version must match. On success the next refresh recomputes
        invoices through the new rules.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            BILLING_RULES_SCHEMA,
            LINE_ITEM_CATEGORIES,
            OPERATOR_MSN_ID,
            resolve_grantee_from_headers,
            write_billing_rules,
        )

        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is not None and str(caller.get("msn_id")) != OPERATOR_MSN_ID:
            return jsonify({"ok": False, "error": "operator_only"}), 403

        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400

        # Validate categories used in per_grantee waivers
        valid_categories = set(LINE_ITEM_CATEGORIES)
        for msn, grantee_rules in (body.get("per_grantee") or {}).items():
            for cat in grantee_rules.get("waive_categories") or []:
                if cat not in valid_categories:
                    return jsonify({
                        "ok": False, "error": "invalid_category",
                        "msn": msn, "category": cat,
                    }), 400

        # Validate margin range
        margin = (body.get("defaults") or {}).get("margin_pct")
        if margin is not None:
            try:
                m = float(margin)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "margin_pct_not_numeric"}), 400
            if not (0 <= m <= 1000):
                return jsonify({"ok": False, "error": "margin_pct_out_of_range"}), 400

        # Validate shared-pool split modes + residue handling (allow-list) so a
        # typo returns 400 instead of silently falling through to absorb_fnd.
        defaults = body.get("defaults") or {}
        valid_pool_modes = {"absorb_fnd", "by_bandwidth_share", "equal"}
        for pool, pool_rule in (defaults.get("shared_pool_split") or {}).items():
            mode = (pool_rule or {}).get("mode")
            if mode is not None and mode not in valid_pool_modes:
                return jsonify({
                    "ok": False, "error": "invalid_pool_split_mode",
                    "pool": pool, "mode": mode,
                }), 400
        residue_mode = defaults.get("residue_handling")
        if residue_mode is not None and residue_mode not in {"absorb_fnd", "passthrough"}:
            return jsonify({
                "ok": False, "error": "invalid_residue_handling",
                "residue_handling": residue_mode,
            }), 400

        body.setdefault("schema", BILLING_RULES_SCHEMA)
        try:
            saved = write_billing_rules(body)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "rules": saved}), 200

    @app.get("/__fnd/tolling/whoami")
    def fnd_tolling_whoami() -> tuple[Any, int]:
        """Resolve the caller's grantee identity.

        Resolution order:
          1. oauth2-proxy headers (X-Auth-Request-Grantee / Email) —
             once Keycloak is wired, this is the authoritative path.
          2. Request host — the per-client `/dashboard/` lives at the
             grantee's own domain, so request.host identifies the
             owning grantee. Used during the no-auth dev preview.
        Returns 200 with `grantee: null` only when neither resolves.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            grantee_for_domain,
            resolve_grantee_from_headers,
        )

        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is None:
            caller = grantee_for_domain(_normalize_domain(request.host), fnd_csm_root=_configured_fnd_csm_root())
        if caller is None:
            return jsonify({"ok": True, "grantee": None}), 200
        return jsonify({
            "ok": True,
            "grantee": {
                "msn_id": _as_text(caller.get("msn_id")),
                "short_name": _as_text(caller.get("short_name")),
                "label": _as_text(caller.get("label")),
                "domains": [str(d) for d in caller.get("domains") or []],
            },
        }), 200

    def _resolve_grantee_scope() -> tuple[str, tuple[Any, int] | None]:
        """Resolve the requested grantee msn against the caller's scope.
        Returns (msn_id, None) on success, ("", error_response) otherwise.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            grantee_for_domain,
            resolve_grantee_from_headers,
        )
        requested_msn = _as_text(request.args.get("grantee"))
        caller = resolve_grantee_from_headers(request.headers, fnd_csm_root=_configured_fnd_csm_root())
        if caller is None:
            caller = grantee_for_domain(
                _normalize_domain(request.host), fnd_csm_root=_configured_fnd_csm_root()
            )
        if caller is not None:
            caller_msn = _as_text(caller.get("msn_id"))
            if requested_msn and requested_msn != caller_msn:
                return "", (jsonify({"ok": False, "error": "scope_mismatch"}), 403)
            if not requested_msn:
                requested_msn = caller_msn
        if not requested_msn:
            return "", (jsonify({"ok": False, "error": "missing_grantee"}), 400)
        return requested_msn, None

    def _parse_period_args() -> tuple[Any, Any, tuple[Any, int] | None]:
        """Parse ?from= / ?to= ISO dates, default to MTD.
        Returns (start, end, None) or (None, None, error_response).
        """
        from datetime import date as _date
        from_raw = _as_text(request.args.get("from"))
        to_raw = _as_text(request.args.get("to"))
        try:
            today = datetime.now(UTC).date()
            start_d = _date.fromisoformat(from_raw) if from_raw else today.replace(day=1)
            end_d = _date.fromisoformat(to_raw) if to_raw else today
        except ValueError:
            return None, None, (jsonify({"ok": False, "error": "bad_period"}), 400)
        return start_d, end_d, None

    @app.get("/__fnd/resources/summary")
    def fnd_resources_summary() -> tuple[Any, int]:
        """Grantee-scoped asset/resource inventory for the RESOURCES tab —
        the caller's own site images/icons/documents/profiles from its
        record-manifests. Scoped by _resolve_grantee_scope (a grantee never
        sees another site's assets)."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.dashboard_aggregate import (
            build_resources_summary,
        )
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        msn, err = _resolve_grantee_scope()
        if err:
            return err
        payload = build_resources_summary(
            msn_id=msn,
            fnd_csm_root=Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm",
            webapps_clients_root=Path(host_config.webapps_root) / "clients",
        )
        return jsonify({"ok": True, **payload}), 200

    def _grantee_scope_tokens(grantee: dict[str, Any] | None) -> list[str]:
        """Identity tokens for a grantee used to scope the public profile
        roster to its own entity: short_name + label + each owned domain."""
        if not grantee:
            return []
        tokens = [
            _as_text(grantee.get("short_name")),
            _as_text(grantee.get("label")),
        ]
        tokens += [_as_text(d) for d in grantee.get("domains") or []]
        return [t for t in tokens if t]

    @app.get("/__fnd/resources/profiles")
    def fnd_resources_profiles() -> tuple[Any, int]:
        """READ-ONLY grantee-scoped profile roster for the dashboard RESOURCES
        tab. Returns the public profiles relevant to the caller's entity (or
        the full public roster when scoping is ambiguous — read-only is safe).
        Never exposes a non-public/operator-only profile, and has no
        write/edit path (editing lives in the operator portal)."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        msn, err = _resolve_grantee_scope()
        if err:
            return err
        grantee = _contacts_caller_grantee(msn) if host_config.private_dir else None
        profiles = resources_extension.grantee_profiles(
            host_config.webapps_root, _grantee_scope_tokens(grantee)
        )
        return jsonify({"ok": True, "profiles": profiles}), 200

    @app.get("/__fnd/resources/profile")
    def fnd_resources_profile() -> tuple[Any, int]:
        """READ-ONLY full detail for one profile, for the dashboard RESOURCES
        tab. Grantee-scoped + restricted to public, in-scope profiles so a
        grantee can only open a profile its roster could already list."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions import (
            resources_extension,
        )

        msn, err = _resolve_grantee_scope()
        if err:
            return err
        slug = _as_text(request.args.get("slug"))
        if not slug:
            return jsonify({"ok": False, "error": "slug_required"}), 400
        grantee = _contacts_caller_grantee(msn) if host_config.private_dir else None
        roster = resources_extension.grantee_profiles(
            host_config.webapps_root, _grantee_scope_tokens(grantee)
        )
        if not any(row.get("slug") == slug for row in roster):
            return jsonify({"ok": False, "error": "profile_not_found"}), 404
        detail = resources_extension.profile_detail(host_config.webapps_root, slug)
        if detail is None:
            return jsonify({"ok": False, "error": "profile_not_found"}), 404
        return jsonify({"ok": True, "profile": detail}), 200

    @app.get("/__fnd/grantee/summary")
    def fnd_grantee_summary() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.dashboard_aggregate import (
            build_grantee_summary,
        )
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        msn, err = _resolve_grantee_scope()
        if err:
            return err
        start_d, end_d, err = _parse_period_args()
        if err:
            return err
        payload = build_grantee_summary(
            msn_id=msn,
            period=(start_d, end_d),
            fnd_csm_root=Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm",
            aws_peripheral=_aws_peripheral,
            private_dir=Path(host_config.private_dir),
        )
        return jsonify({"ok": True, **payload}), 200

    # ------------------------------------------------------------------
    # Dashboard Contacts tab — per-grantee address book.
    # ------------------------------------------------------------------
    # The Contacts tab on the per-client `/dashboard/` shows the union of
    # all contact-log JSONs across every domain the grantee owns and
    # supports add + edit-by-email (no delete; submitters are the natural
    # primary key and the email subjects them to GDPR-style retention
    # policies separately).
    #
    # Auth: identical scope check to the Tolling/Email endpoints — the
    # caller's grantee is resolved from oauth2-proxy headers (Keycloak)
    # or, in the no-auth dev preview, from request.host. The requested
    # `grantee` query arg must match the caller's msn, and any `domain`
    # in the body must be one the caller owns.

    def _contacts_caller_grantee(requested_msn: str) -> dict[str, Any] | None:
        """Return the full grantee profile dict for the caller's msn.

        Used to materialize the `domains` list owned by the grantee +
        return label / short_name in the list response.
        """
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            load_grantee_directory,
        )
        if host_config.private_dir is None:
            return None
        directory = Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm"
        for profile in load_grantee_directory(directory):
            if str(profile.get("msn_id", "")) == requested_msn:
                return profile
        return None

    def _contacts_identity_view(record: dict[str, Any]) -> dict[str, Any]:
        """Project a contact record down to its identity fields only.

        Strips message/subject (historic leftover keys), keeps subscribe
        state + lifecycle timestamps so the UI can show source/created.
        """
        return {
            "email": _as_text(record.get("email")),
            "name": _as_text(record.get("name")),
            "first_name": _as_text(record.get("first_name")),
            "middle_name": _as_text(record.get("middle_name")),
            "last_name": _as_text(record.get("last_name")),
            "phone": _as_text(record.get("phone")),
            "zip": _as_text(record.get("zip")),
            "organization": _as_text(record.get("organization")),
            "subscribed": bool(record.get("subscribed")),
            "source": _as_text(record.get("source")),
            "forward_status": _as_text(record.get("forward_status")),
            "signup_date": _as_text(record.get("signup_date")),
            "created_at": _as_text(record.get("created_at")),
            "updated_at": _as_text(record.get("updated_at")),
        }

    @app.get("/__fnd/contacts/list")
    def fnd_contacts_list() -> tuple[Any, int]:
        """Union of every contact-log row across the caller grantee's
        domains. Identity fields only — message/subject never surface."""
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        msn, err = _resolve_grantee_scope()
        if err:
            return err
        grantee = _contacts_caller_grantee(msn)
        if grantee is None:
            return jsonify({"ok": False, "error": "grantee_not_found"}), 404
        owned_domains = [
            _normalize_domain(str(d))
            for d in grantee.get("domains") or []
            if str(d).strip()
        ]
        adapter = _newsletter_state_adapter(host_config)
        contacts: list[dict[str, Any]] = []
        for domain in owned_domains:
            log = adapter.load_contact_log(domain=domain) or {}
            for record in log.get("contacts") or []:
                if not isinstance(record, dict):
                    continue
                row = _contacts_identity_view(record)
                row["domain"] = domain
                contacts.append(row)
        contacts.sort(
            key=lambda r: (r.get("updated_at") or r.get("created_at") or ""),
            reverse=True,
        )
        return jsonify({
            "ok": True,
            "grantee": {
                "msn_id": _as_text(grantee.get("msn_id")),
                "label": _as_text(grantee.get("label")),
                "short_name": _as_text(grantee.get("short_name")),
                "domains": owned_domains,
            },
            "contacts": contacts,
        }), 200

    @app.post("/__fnd/contacts/add")
    def fnd_contacts_add() -> tuple[Any, int]:
        """Dashboard add path — identity-only, no email sent. Upserts by
        email. If a row exists, identity fields patch in (existing
        subscribed state is preserved); if not, a new unsubscribed row
        lands with source=dashboard_add."""
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        msn, err = _resolve_grantee_scope()
        if err:
            return err
        grantee = _contacts_caller_grantee(msn)
        if grantee is None:
            return jsonify({"ok": False, "error": "grantee_not_found"}), 404
        owned_domains = {
            _normalize_domain(str(d))
            for d in grantee.get("domains") or []
            if str(d).strip()
        }
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400
        domain = _normalize_domain(_as_text(body.get("domain")))
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if domain not in owned_domains:
            return jsonify({"ok": False, "error": "domain_not_owned"}), 403
        email = _validate_email(body.get("email"))
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400

        adapter = _newsletter_state_adapter(host_config)
        log = adapter.load_contact_log(domain=domain) or {
            "domain": domain,
            "contacts": [],
            "dispatches": [],
        }
        now_iso = _utc_now_iso()
        today_date = now_iso[:10] if len(now_iso) >= 10 else now_iso
        contacts = list(log.get("contacts") or [])
        index = next(
            (
                i
                for i, c in enumerate(contacts)
                if _as_text(c.get("email")).lower() == email
            ),
            None,
        )
        existing = contacts[index] if index is not None else None
        patch: dict[str, Any] = {
            "email": email,
            "first_name": _as_text(body.get("first_name")),
            "middle_name": _as_text(body.get("middle_name")),
            "last_name": _as_text(body.get("last_name")),
            "phone": _as_text(body.get("phone")),
            "zip": _as_text(body.get("zip")),
            "organization": _as_text(body.get("organization")),
        }
        if existing is None:
            # New contact lands unsubscribed; the operator opts them in via the
            # per-row toggle. Adding an EXISTING contact never re-subscribes it.
            patch["source"] = "dashboard_add"
            patch["signup_date"] = today_date
            patch["subscribed"] = False
        row = canonical_contact_entry(existing=existing, patch=patch, now=now_iso)
        if index is not None:
            contacts[index] = row
        else:
            contacts.append(row)
        log["contacts"] = contacts
        log["updated_at"] = now_iso
        adapter.save_contact_log(domain=domain, payload=log)

        view = _contacts_identity_view(row)
        view["domain"] = domain
        return jsonify({"ok": True, "contact": view}), 200

    @app.post("/__fnd/contacts/update")
    def fnd_contacts_update() -> tuple[Any, int]:
        """Dashboard edit path — locate by `email` (natural key), patch
        identity fields. Supports `new_email` to rename a row; the
        rename rejects on collision with another row in the same log."""
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        msn, err = _resolve_grantee_scope()
        if err:
            return err
        grantee = _contacts_caller_grantee(msn)
        if grantee is None:
            return jsonify({"ok": False, "error": "grantee_not_found"}), 404
        owned_domains = {
            _normalize_domain(str(d))
            for d in grantee.get("domains") or []
            if str(d).strip()
        }
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400
        domain = _normalize_domain(_as_text(body.get("domain")))
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if domain not in owned_domains:
            return jsonify({"ok": False, "error": "domain_not_owned"}), 403
        email = _validate_email(body.get("email"))
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400

        adapter = _newsletter_state_adapter(host_config)
        log = adapter.load_contact_log(domain=domain)
        if not log:
            return jsonify({"ok": False, "error": "contact_log_missing"}), 404
        contacts = list(log.get("contacts") or [])
        target = None
        for c in contacts:
            if _as_text(c.get("email")).lower() == email:
                target = c
                break
        if target is None:
            return jsonify({"ok": False, "error": "contact_not_found"}), 404

        # Optional rename — must be a valid email and must not collide.
        new_email_raw = body.get("new_email")
        if new_email_raw is not None and _as_text(new_email_raw):
            new_email = _validate_email(new_email_raw)
            if not new_email:
                return jsonify({"ok": False, "error": "invalid_new_email"}), 400
            if new_email != email:
                for c in contacts:
                    if c is target:
                        continue
                    if _as_text(c.get("email")).lower() == new_email:
                        return jsonify({"ok": False, "error": "new_email_collision"}), 409
                target["email"] = new_email

        # Identity patch — an empty value means "no change", so the dashboard
        # can submit the whole form without wiping stored phone/zip/etc.
        patch: dict[str, Any] = {"email": _as_text(target.get("email"))}
        for key in ("first_name", "middle_name", "last_name", "phone", "zip", "organization"):
            if key in body:
                patch[key] = _as_text(body.get(key))
        now_iso = _utc_now_iso()
        index = contacts.index(target)
        contacts[index] = canonical_contact_entry(existing=target, patch=patch, now=now_iso)
        log["contacts"] = contacts
        log["updated_at"] = now_iso
        adapter.save_contact_log(domain=domain, payload=log)

        view = _contacts_identity_view(contacts[index])
        view["domain"] = domain
        return jsonify({"ok": True, "contact": view}), 200

    # ------------------------------------------------------------------
    # Grantee self-service email management — add / edit / remove a
    # client's own personal *user* aliases from the dashboard.
    # ------------------------------------------------------------------
    # Domain-scoped exactly like /__fnd/contacts/*. Operator-RESERVED
    # functional addresses (admin@, postmaster@, news@, …) and any profile
    # explicitly marked role="role" are NEVER grantee-mutable — only the
    # operator (onboard-role) touches those. Writes go to the canonical
    # (live) aws-csm store and re-sync the forwarder via onboard_alias /
    # _post_profile_save_hook — the same paths the operator routes use.
    _LOCAL_PART_RE = re.compile(r"[a-z0-9._-]+")

    def _normalize_local(value: object) -> str:
        return _as_text(value).lower()

    def _grantee_email_ctx() -> tuple[dict[str, Any] | None, tuple[Any, int] | None]:
        if host_config.private_dir is None:
            return None, (jsonify({"ok": False, "error": "no_private_dir"}), 500)
        msn, err = _resolve_grantee_scope()
        if err:
            return None, err
        grantee = _contacts_caller_grantee(msn)
        if grantee is None:
            return None, (jsonify({"ok": False, "error": "grantee_not_found"}), 404)
        owned = {
            _normalize_domain(str(d))
            for d in grantee.get("domains") or []
            if str(d).strip()
        }
        from MyCiteV2.packages.peripherals.aws import ProfileStore

        store = ProfileStore(
            root=Path(host_config.private_dir) / "utilities" / "tools" / "aws-csm"
        )
        return {"msn": msn, "grantee": grantee, "owned": owned, "store": store}, None

    def _grantee_alias_guard(
        local: str, domain: str, owned: set[str], reserved
    ) -> tuple[Any, int] | None:
        if not local:
            return jsonify({"ok": False, "error": "missing_local"}), 400
        # Strict charset defeats casing/whitespace/`@`/path-traversal tricks;
        # reject bare-dot / leading-dot too. Normalisation already lowercased.
        if (
            local in (".", "..")
            or local.startswith(".")
            or not _LOCAL_PART_RE.fullmatch(local)
        ):
            return jsonify({"ok": False, "error": "invalid_local_part"}), 400
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if domain not in owned:
            return jsonify({"ok": False, "error": "domain_not_owned"}), 403
        if local in reserved:
            return jsonify({"ok": False, "error": "reserved_local_part"}), 403
        return None

    def _grantee_owned_user_alias(store, domain: str, local: str):
        """Return the on-disk profile for (domain, local) if it is a grantee-
        manageable user alias, else (None, error_response)."""
        match = next(
            (
                p
                for p in store.profiles_by_domain(domain)
                if _normalize_local((p.get("identity") or {}).get("mailbox_local_part"))
                == local
            ),
            None,
        )
        if match is None:
            return None, (jsonify({"ok": False, "error": "alias_not_found"}), 404)
        # Allowlist, not denylist: only explicitly user-tagged aliases are
        # grantee-managed. Operator / functional profiles use role=operator |
        # technical_contact | role | "" and stay operator-only even when their
        # local-part is not in the reserved name denylist (e.g. tech@, finance@,
        # an operator-tagged marilyn@). Fail closed.
        if _as_text((match.get("identity") or {}).get("role")).lower() != "user":
            return None, (jsonify({"ok": False, "error": "not_user_alias"}), 403)
        return match, None

    @app.post("/__fnd/email/grantee/add")
    def fnd_email_grantee_add() -> tuple[Any, int]:
        from MyCiteV2.packages.peripherals.aws.onboard import (
            RESERVED_ROLE_LOCALPARTS,
            onboard_alias,
        )

        ctx, err = _grantee_email_ctx()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400
        domain = _normalize_domain(_as_text(body.get("domain")))
        local = _normalize_local(body.get("local"))
        guard = _grantee_alias_guard(local, domain, ctx["owned"], RESERVED_ROLE_LOCALPARTS)
        if guard:
            return guard
        forward_to = _validate_email(body.get("forward_to"))
        if not forward_to:
            return jsonify({"ok": False, "error": "invalid_forward_to"}), 400
        # onboard_alias is an UPSERT — guard against an "add" silently
        # overwriting an existing operator/functional profile on that address.
        # A grantee may only (re)create a user-tagged alias; anything else is
        # operator-managed (same allowlist as edit/remove).
        existing = next(
            (
                p
                for p in ctx["store"].profiles_by_domain(domain)
                if _normalize_local((p.get("identity") or {}).get("mailbox_local_part")) == local
            ),
            None,
        )
        if existing is not None and _as_text((existing.get("identity") or {}).get("role")).lower() != "user":
            return jsonify({"ok": False, "error": "reserved_local_part"}), 403
        try:
            # kind="user" is hard-coded server-side — never read from the body,
            # so a grantee can never mint a role alias by smuggling `kind`.
            result = onboard_alias(
                adapter=_aws_peripheral, store=ctx["store"], kind="user",
                domain=domain, local=local, forward_to=forward_to,
                display_name=_as_text(body.get("display_name")), tenant_slug=None,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": "tenant_slug_required", "detail": str(exc)}), 400
        except Exception as exc:
            _log.error("grantee_alias_add_failed", extra={"err": str(exc)})
            return jsonify({"ok": False, "error": "sync_failed", "detail": str(exc)}), 502
        return jsonify({"ok": True, **result}), 200

    @app.post("/__fnd/email/grantee/edit")
    def fnd_email_grantee_edit() -> tuple[Any, int]:
        from MyCiteV2.packages.peripherals.aws.onboard import (
            RESERVED_ROLE_LOCALPARTS,
            onboard_alias,
        )

        ctx, err = _grantee_email_ctx()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400
        domain = _normalize_domain(_as_text(body.get("domain")))
        local = _normalize_local(body.get("local"))
        guard = _grantee_alias_guard(local, domain, ctx["owned"], RESERVED_ROLE_LOCALPARTS)
        if guard:
            return guard
        forward_to = _validate_email(body.get("forward_to"))
        if not forward_to:
            return jsonify({"ok": False, "error": "invalid_forward_to"}), 400
        match, merr = _grantee_owned_user_alias(ctx["store"], domain, local)
        if merr:
            return merr
        # Re-onboard with the new forward_to. onboard_alias dual-writes
        # inbound.receive_routing_target + identity.operator_inbox_target and
        # re-syncs the forwarder — the operator admin/edit route only writes
        # the latter, so this is the more-correct path.
        try:
            result = onboard_alias(
                adapter=_aws_peripheral, store=ctx["store"], kind="user",
                domain=domain, local=local, forward_to=forward_to,
                display_name=_as_text((match.get("identity") or {}).get("display_name")),
                tenant_slug=None,
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": "edit_failed", "detail": str(exc)}), 400
        except Exception as exc:
            _log.error("grantee_alias_edit_failed", extra={"err": str(exc)})
            return jsonify({"ok": False, "error": "sync_failed", "detail": str(exc)}), 502
        return jsonify({"ok": True, **result}), 200

    @app.post("/__fnd/email/grantee/remove")
    def fnd_email_grantee_remove() -> tuple[Any, int]:
        from MyCiteV2.packages.peripherals.aws.onboard import RESERVED_ROLE_LOCALPARTS

        ctx, err = _grantee_email_ctx()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "body_must_be_object"}), 400
        domain = _normalize_domain(_as_text(body.get("domain")))
        local = _normalize_local(body.get("local"))
        guard = _grantee_alias_guard(local, domain, ctx["owned"], RESERVED_ROLE_LOCALPARTS)
        if guard:
            return guard
        match, merr = _grantee_owned_user_alias(ctx["store"], domain, local)
        if merr:
            return merr
        source_path = _as_text(match.get("_source_path"))
        profile_id = _as_text((match.get("identity") or {}).get("profile_id"))
        if not source_path:
            return jsonify({"ok": False, "error": "source_path_missing"}), 500
        try:
            Path(source_path).unlink()
        except OSError as exc:
            return jsonify({"ok": False, "error": "storage_error", "detail": str(exc)}), 500
        # Drop the route from FORWARD_TO_MAP_JSON (same hook the operator
        # remove route uses).
        _post_profile_save_hook(profile_id, op="remove")
        return jsonify(
            {"ok": True, "address": f"{local}@{domain}", "removed_path": source_path}
        ), 200

    @app.get("/__fnd/email/dashboard")
    def fnd_email_dashboard() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.dashboard_aggregate import (
            build_email_dashboard,
        )
        from MyCiteV2.packages.adapters.sql.fnd_email_deliverability import (
            MosDatumEmailDeliverabilityAdapter,
        )
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "no_private_dir"}), 500
        if host_config.authority_db_file is None:
            return jsonify({"ok": False, "error": "no_authority_db"}), 500
        msn, err = _resolve_grantee_scope()
        if err:
            return err
        start_d, end_d, err = _parse_period_args()
        if err:
            return err
        deliverability_adapter = MosDatumEmailDeliverabilityAdapter(
            authority_db_file=host_config.authority_db_file,
            tenant_id=host_config.portal_instance_id or "fnd",
        )
        payload = build_email_dashboard(
            msn_id=msn,
            period=(start_d, end_d),
            fnd_csm_root=Path(host_config.private_dir) / "utilities" / "tools" / "fnd-csm",
            private_dir=Path(host_config.private_dir),
            deliverability_adapter=deliverability_adapter,
            aws_peripheral=_aws_peripheral,
        )
        return jsonify({"ok": True, **payload}), 200

    return app


__all__ = [
    "HOST_SHAPE",
    "PORTAL_SHELL_ASSET_MANIFEST_SCHEMA",
    "V2_PORTAL_ERROR_SCHEMA",
    "V2_PORTAL_HEALTH_SCHEMA",
    "V2PortalHostConfig",
    "build_shell_asset_manifest",
    "create_app",
]
