from __future__ import annotations

import base64
from dataclasses import dataclass
import glob
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone
from typing import Any, Mapping

try:
    from flask import Flask, abort, jsonify, redirect, render_template, request
    _FLASK_IMPORT_ERROR: ModuleNotFoundError | None = None
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in dependency-light test environments
    Flask = Any  # type: ignore[misc,assignment]
    _FLASK_IMPORT_ERROR = exc

    def _raise_flask_import_error(*_args: Any, **_kwargs: Any) -> Any:
        raise ModuleNotFoundError("flask is required to run the portal host") from _FLASK_IMPORT_ERROR

    abort = jsonify = redirect = render_template = _raise_flask_import_error

    class _MissingRequest:
        def get_json(self, *args: Any, **kwargs: Any) -> Any:
            return _raise_flask_import_error(*args, **kwargs)

    request = _MissingRequest()

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
    run_portal_shell_entry,
    run_system_profile_basics_action,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
    CTS_GIS_TOOL_REQUEST_SCHEMA,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
    build_tool_exposure_policy,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    CTS_GIS_TOOL_SURFACE_ID,
    FND_CSM_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    PortalScope,
    build_portal_shell_state_from_query,
    build_portal_tool_registry_entries,
    requires_shell_state_machine,
)

V2_PORTAL_HEALTH_SCHEMA = "mycite.v2.portal.health.v1"
V2_PORTAL_ERROR_SCHEMA = "mycite.v2.portal.error.v1"
HOST_SHAPE = "v2_native"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


PORTAL_BUILD_ID = _as_text(os.environ.get("MYCITE_V2_PORTAL_BUILD_ID")) or "not-set"
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
        "module_id": "fnd_csm_workspace",
        "file": "v2_portal_fnd_csm_workspace.js",
        "load_phase": "deferred",
        "loading_scope": ("system.tools.fnd_csm",),
        "budget_group": "deferred_tool_renderers",
        "exports": (
            {
                "global": "PortalFndCsmWorkspaceRenderer",
                "required_callables": ("render",),
            },
            {
                "global": "PortalFndCsmInterfacePanelRenderer",
                "required_callables": ("render",),
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
        "module_id": "interface_panel_renderers",
        "file": "v2_portal_interface_panel_host.js",
        "load_phase": "startup_critical",
        "loading_scope": ("shared_interface_panel_host",),
        "budget_group": "initial_shell",
        "exports": (
            {
                "global": "PortalShellInterfacePanelRenderer",
                "required_callables": ("render",),
            },
        ),
    },
    {
        "module_id": "cts_gis_surface",
        "file": "v2_portal_interface_panel_renderers.js",
        "load_phase": "deferred",
        "loading_scope": ("system.tools.cts_gis",),
        "budget_group": "deferred_tool_renderers",
        "exports": (
            {
                "global": "PortalCtsGisInterfacePanelRenderer",
                "required_callables": ("render",),
            },
        ),
    },
    {
        "module_id": "cts_gis_workspace",
        "file": "v2_portal_interface_panel_renderers.js",
        "load_phase": "deferred",
        "loading_scope": ("system.tools.cts_gis",),
        "budget_group": "deferred_tool_renderers",
        "exports": (
            {
                "global": "PortalCtsGisWorkspaceRenderer",
                "required_callables": ("render",),
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
    for asset in list(styles.values()) + [
        scripts.get("portal_js"),
        scripts.get("shell_entry"),
    ]:
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
    if requires_shell_state_machine(surface_id):
        shell_state = build_portal_shell_state_from_query(
            surface_id=surface_id,
            portal_scope=portal_scope,
            query=query_params,
        )
        if shell_state is not None:
            payload["shell_state"] = shell_state.to_dict()
    elif query_params:
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
    def from_env(cls) -> "V2PortalHostConfig":
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
    "fnd-csm": FND_CSM_TOOL_SURFACE_ID,
    "workbench-ui": WORKBENCH_UI_TOOL_SURFACE_ID,
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
    return jsonify(envelope), _runtime_status_code(envelope)


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


def _tool_payload_for_mutation(action: str, payload: dict[str, Any], *, request_schema: str) -> dict[str, Any]:
    envelope_payload = payload.get("nimm_envelope")
    directive_payload: dict[str, Any] = {}
    if isinstance(envelope_payload, Mapping):
        from MyCiteV2.packages.state_machine.nimm import NimmDirectiveEnvelope

        envelope = NimmDirectiveEnvelope.from_dict(dict(envelope_payload))
        directive_payload = dict(envelope.directive.payload or {})
    action_kind = _as_text(payload.get("action_kind") or directive_payload.get("action_kind") or action)
    raw_action_payload = payload.get("action_payload")
    if raw_action_payload is None:
        raw_action_payload = directive_payload.get("action_payload")
    return {
        **dict(payload),
        "schema": request_schema,
        "action_kind": action_kind,
        "action_payload": dict(raw_action_payload) if isinstance(raw_action_payload, Mapping) else {},
    }


def _render_surface(surface_id: str, host_config: V2PortalHostConfig) -> str:
    shell_asset_manifest = build_shell_asset_manifest(PORTAL_BUILD_ID)
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
    )


def _warm_system_workbench_projection(config: V2PortalHostConfig) -> None:
    # Warm the heavy system-workbench projection cache so first portal open
    # does not pay full datum-recognition cost on request path.
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
        # Best-effort warmup only; health/error routes remain source of truth.
        return


def _build_health(config: V2PortalHostConfig) -> dict[str, Any]:
    static_dir = Path(__file__).resolve().parent / "static"
    shell_asset_manifest = build_shell_asset_manifest(PORTAL_BUILD_ID)
    static_files = _shell_asset_files_from_manifest(shell_asset_manifest)
    return {
        "schema": V2_PORTAL_HEALTH_SCHEMA,
        "ok": all((static_dir / name).is_file() for name in static_files),
        "host_shape": HOST_SHAPE,
        "portal_build_id": PORTAL_BUILD_ID,
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

_NEWSLETTER_WEBAPPS_ROOT = "/srv/webapps/clients"
_NEWSLETTER_ADMIN_PROFILE_GLOB = (
    "/srv/mycite-state/instances/fnd/private/utilities/tools/newsletter-admin/newsletter-admin.*.json"
)
_CONTACT_LOG_SCHEMA = "mycite.webapp.contact_log.v1"

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _newsletter_contact_log_path(domain: str) -> Path:
    """Derive canonical contact log path from domain.

    Pattern: /srv/webapps/clients/<domain>/contacts/<domain>-contact_log.json
    The route handler must NOT rely on the newsletter-admin profile's
    contact_log_path field at runtime (may be stale).
    """
    return Path(_NEWSLETTER_WEBAPPS_ROOT) / domain / "contacts" / f"{domain}-contact_log.json"


def _newsletter_known_domains() -> list[str]:
    """Load known newsletter domains from newsletter-admin profile directory."""
    domains: list[str] = []
    for path in glob.glob(_NEWSLETTER_ADMIN_PROFILE_GLOB):
        basename = os.path.basename(path)
        # newsletter-admin.<domain>.json
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
    return datetime.now(timezone.utc).isoformat()


def _load_contact_log(path: Path, *, domain: str) -> dict[str, Any]:
    """Load contact log JSON; bootstrap empty log if absent or unparseable."""
    if path.exists() and path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("schema") == _CONTACT_LOG_SCHEMA:
                return payload
        except Exception:
            pass
    return {
        "schema": _CONTACT_LOG_SCHEMA,
        "domain": domain,
        "contacts": [],
        "dispatches": [],
        "updated_at": "",
    }


def _write_contact_log_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write contact log atomically via temp-file rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-contact-log-")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2) + "\n")
        os.rename(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _upsert_subscriber(
    contact_log: dict[str, Any],
    *,
    email: str,
    name: str,
    zip_code: str,
    now_iso: str,
) -> dict[str, Any]:
    """Upsert a subscriber record. Sorts contacts by email. Returns the upserted record.

    Write contract:
    - Does NOT touch dispatches array.
    - Does NOT modify any contact other than the target email.
    - Sorts contacts ascending by email after upsert.
    """
    contacts: list[dict[str, Any]] = list(contact_log.get("contacts") or [])
    by_email: dict[str, dict[str, Any]] = {
        str(row.get("email", "")).lower(): dict(row)
        for row in contacts
        if isinstance(row, dict) and row.get("email")
    }
    current = by_email.get(email)
    if current is None:
        current = {
            "email": email,
            "name": name,
            "zip": zip_code,
            "source": "website_signup",
            "subscribed": True,
            "created_at": now_iso,
            "subscribed_at": now_iso,
            "unsubscribed_at": "",
            "updated_at": now_iso,
            "last_newsletter_sent_at": "",
            "send_count": 0,
            "notes": "",
        }
    else:
        if name:
            current["name"] = name
        if zip_code:
            current["zip"] = zip_code
        current["source"] = "website_signup"
        current["subscribed"] = True
        current["subscribed_at"] = str(current.get("subscribed_at") or "").strip() or now_iso
        current["unsubscribed_at"] = ""
        current["updated_at"] = now_iso
    by_email[email] = current
    # Sort contacts ascending by email — consistent with AwsCsmNewsletterService.subscribe() line 298
    contact_log["contacts"] = [by_email[k] for k in sorted(by_email.keys())]
    # dispatches array passes through unchanged
    return current


def _fnd_newsletter_request_field(field: str) -> str:
    """Extract a field from JSON body or form data."""
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return str(data.get(field) or "").strip()
    return str(request.form.get(field) or "").strip()


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
    if _as_text(environment).lower() == "production":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _get_paypal_access_token(client_id: str, client_secret: str, base_url: str) -> str:
    import urllib.parse
    import urllib.request as _urllib_request

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = _urllib_request.Request(
        f"{base_url}/v1/oauth2/token",
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with _urllib_request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    return _as_text(result.get("access_token"))


def _append_to_ndjson(path: Path, record: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        pass


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
    def portal_system_tool(tool_slug: str) -> str:
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

    @app.get("/portal/utilities/tool-exposure")
    def portal_utilities_tool_exposure() -> str:
        return _render_surface(UTILITIES_TOOL_EXPOSURE_SURFACE_ID, host_config)

    @app.get("/portal/utilities/integrations")
    def portal_utilities_integrations() -> str:
        return _render_surface(UTILITIES_INTEGRATIONS_SURFACE_ID, host_config)

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

    @app.post("/portal/api/v2/system/tools/fnd-csm")
    def portal_fnd_csm() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import run_portal_fnd_csm
        from MyCiteV2.instances._shared.runtime.runtime_platform import FND_CSM_TOOL_REQUEST_SCHEMA

        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = FND_CSM_TOOL_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_fnd_csm(
                    payload,
                    private_dir=host_config.private_dir,
                    webapps_root=host_config.webapps_root,
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/fnd-csm/actions")
    def portal_fnd_csm_actions() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import run_portal_fnd_csm_action
        from MyCiteV2.instances._shared.runtime.runtime_platform import FND_CSM_TOOL_ACTION_REQUEST_SCHEMA

        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = FND_CSM_TOOL_ACTION_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_fnd_csm_action(
                    payload,
                    private_dir=host_config.private_dir,
                    webapps_root=host_config.webapps_root,
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/cts-gis")
    def portal_cts_gis() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis

        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = CTS_GIS_TOOL_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_cts_gis(
                    payload,
                    data_dir=host_config.data_dir,
                    authority_db_file=host_config.authority_db_file,
                    private_dir=host_config.private_dir,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))
        except Exception as exc:
            _legacy = _check_legacy_maps_error(exc)
            if _legacy is not None:
                return _legacy
            raise

    @app.post("/portal/api/v2/system/tools/cts-gis/actions")
    def portal_cts_gis_actions() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis_action

        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_cts_gis_action(
                    payload,
                    data_dir=host_config.data_dir,
                    authority_db_file=host_config.authority_db_file,
                    private_dir=host_config.private_dir,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                    portal_instance_id=host_config.portal_instance_id,
                    portal_domain=host_config.portal_domain,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))
        except Exception as exc:
            _legacy = _check_legacy_maps_error(exc)
            if _legacy is not None:
                return _legacy
            raise

    @app.post("/portal/api/v2/mutations/<action>")
    def portal_mutation_action(action: str) -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
            run_datum_workbench_mutation_action,
        )
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis_action

        try:
            payload = _json_payload()
            target_authority = _nimm_target_authority(payload)
            if target_authority == "cts_gis":
                return _runtime_response(
                    run_portal_cts_gis_action(
                        _tool_payload_for_mutation(
                            action,
                            payload,
                            request_schema=CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
                        ),
                        data_dir=host_config.data_dir,
                        authority_db_file=host_config.authority_db_file,
                        private_dir=host_config.private_dir,
                        tool_exposure_policy=host_config.tool_exposure_policy,
                        portal_instance_id=host_config.portal_instance_id,
                        portal_domain=host_config.portal_domain,
                    )
                )
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
                "Mutation target_authority must be cts_gis or datum_workbench.",
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))
        except Exception as exc:
            _legacy = _check_legacy_maps_error(exc)
            if _legacy is not None:
                return _legacy
            raise

    @app.post("/portal/api/v2/system/tools/workbench-ui")
    def portal_workbench_ui() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import run_portal_workbench_ui

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

    @app.post("/__fnd/newsletter/subscribe")
    def fnd_newsletter_subscribe() -> tuple[Any, int]:
        # TODO(mos-migration): replace filesystem contact log write with MOS datum upsert
        domain = _normalize_domain(request.host)
        known = _newsletter_known_domains()
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404

        raw_email = _fnd_newsletter_request_field("email")
        name = _fnd_newsletter_request_field("name")
        zip_code = _fnd_newsletter_request_field("zip")

        email = _validate_email(raw_email)
        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400

        contact_log_path = _newsletter_contact_log_path(domain)
        try:
            contact_log = _load_contact_log(contact_log_path, domain=domain)
            now_iso = _utc_now_iso()
            _upsert_subscriber(contact_log, email=email, name=name, zip_code=zip_code, now_iso=now_iso)
            contact_log["updated_at"] = now_iso
            _write_contact_log_atomic(contact_log_path, contact_log)
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        return jsonify({"ok": True, "email": email, "subscribed": True}), 200

    @app.post("/__fnd/newsletter/unsubscribe")
    def fnd_newsletter_unsubscribe() -> tuple[Any, int]:
        # TODO(mos-migration): replace filesystem contact log write with MOS datum upsert
        domain = _normalize_domain(request.host)
        known = _newsletter_known_domains()
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
            from MyCiteV2.packages.modules.cross_domain.aws_csm_newsletter.payload_utils import (
                render_unsubscribe_token as _render_unsubscribe_token,
            )
            from MyCiteV2.packages.adapters.filesystem.aws_csm_newsletter_state import (
                FilesystemAwsCsmNewsletterStateAdapter,
            )
            state_adapter = FilesystemAwsCsmNewsletterStateAdapter(host_config.private_dir)
            signing_secret = state_adapter.runtime_secret_seed(secret_kind="signing_secret")
            expected = _render_unsubscribe_token(signing_secret, domain=domain, email=email)
            if token_value != expected:
                return jsonify({"ok": False, "error": "invalid_token"}), 403
        except Exception:
            return jsonify({"ok": False, "error": "token_validation_error"}), 500

        contact_log_path = _newsletter_contact_log_path(domain)
        try:
            contact_log = _load_contact_log(contact_log_path, domain=domain)
            now_iso = _utc_now_iso()
            contacts: list[dict[str, Any]] = []
            for row in list(contact_log.get("contacts") or []):
                current = dict(row)
                if str(current.get("email") or "").lower() == email:
                    current["subscribed"] = False
                    current["source"] = "unsubscribe_link"
                    current["unsubscribed_at"] = now_iso
                    current["updated_at"] = now_iso
                contacts.append(current)
            contact_log["contacts"] = contacts
            contact_log["updated_at"] = now_iso
            _write_contact_log_atomic(contact_log_path, contact_log)
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        return jsonify({"ok": True, "email": email, "subscribed": False}), 200

    @app.post("/__fnd/newsletter/dispatch-result")
    def fnd_newsletter_dispatch_result() -> tuple[Any, int]:
        # TODO(mos-migration): replace filesystem contact log write with MOS datum upsert
        domain = _normalize_domain(request.host)
        known = _newsletter_known_domains()
        if domain not in known:
            return jsonify({"ok": False, "error": "domain_not_configured"}), 404

        payload = _json_payload()
        callback_token = str(payload.get("callback_token") or "").strip()
        dispatch_id = str(payload.get("dispatch_id") or "").strip()
        email = _validate_email(str(payload.get("email") or ""))
        status = str(payload.get("status") or "").strip().lower()
        message_id = str(payload.get("message_id") or "").strip()
        queue_message_id = str(payload.get("queue_message_id") or "").strip()
        error_message = str(payload.get("error_message") or "").strip()

        if not email:
            return jsonify({"ok": False, "error": "invalid_email"}), 400
        if status not in {"sent", "failed"}:
            return jsonify({"ok": False, "error": "invalid_status"}), 400
        if not dispatch_id or not callback_token:
            return jsonify({"ok": False, "error": "missing_required_fields"}), 400

        # Validate dispatch callback token
        try:
            from MyCiteV2.packages.adapters.filesystem.aws_csm_newsletter_state import (
                FilesystemAwsCsmNewsletterStateAdapter,
            )
            state_adapter = FilesystemAwsCsmNewsletterStateAdapter(host_config.private_dir)
            expected_token = state_adapter.runtime_secret_seed(secret_kind="dispatch_secret")
            if callback_token != expected_token:
                return jsonify({"ok": False, "error": "invalid_callback_token"}), 403
        except Exception:
            return jsonify({"ok": False, "error": "token_validation_error"}), 500

        contact_log_path = _newsletter_contact_log_path(domain)
        try:
            contact_log = _load_contact_log(contact_log_path, domain=domain)
            now_iso = _utc_now_iso()
            contacts: dict[str, dict[str, Any]] = {
                str(item.get("email") or "").lower(): dict(item)
                for item in list(contact_log.get("contacts") or [])
                if isinstance(item, dict) and item.get("email")
            }
            updated = False
            for dispatch in list(contact_log.get("dispatches") or []):
                if str(dispatch.get("dispatch_id") or "") != dispatch_id:
                    continue
                results = list(dispatch.get("results") or [])
                for row in results:
                    if not isinstance(row, dict) or str(row.get("email") or "").lower() != email:
                        continue
                    prior = str(row.get("status") or "").lower()
                    row["status"] = status
                    if message_id:
                        row["message_id"] = message_id
                    if queue_message_id:
                        row["queue_message_id"] = queue_message_id
                    if error_message:
                        row["error"] = error_message
                    row["updated_at"] = now_iso
                    if status == "sent" and prior != "sent":
                        contact = contacts.get(email)
                        if contact is not None:
                            contact["last_newsletter_sent_at"] = now_iso
                            contact["send_count"] = int(contact.get("send_count") or 0) + 1
                            contact["updated_at"] = now_iso
                            contacts[email] = contact
                    updated = True
                    break
                dispatch["results"] = results
                break
            if not updated:
                return jsonify({"ok": False, "error": "dispatch_result_not_found"}), 404
            contact_log["contacts"] = [contacts[k] for k in sorted(contacts.keys())]
            contact_log["updated_at"] = now_iso
            _write_contact_log_atomic(contact_log_path, contact_log)
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        return jsonify({"ok": True, "domain": domain, "dispatch_id": dispatch_id, "email": email, "status": status}), 200

    # ------------------------------------------------------------------
    # FND PayPal order mediation routes (peripheral)
    # ------------------------------------------------------------------

    @app.post("/__fnd/paypal/create-order")
    def fnd_paypal_create_order() -> tuple[Any, int]:
        import urllib.request
        import urllib.error

        payload = _json_payload()
        domain = _normalize_domain(request.host)
        amount = _as_text(payload.get("amount"))
        donor_name = _as_text(payload.get("donor_name"))
        donor_email = _as_text(payload.get("donor_email"))
        designation = _as_text(payload.get("designation"))

        if not amount:
            return jsonify({"ok": False, "error": "missing_amount"}), 400

        private_dir = host_config.private_dir
        domain_profile = _load_domain_profile(private_dir, domain)
        if domain_profile is None:
            return jsonify({"ok": False, "error": "domain_profile_not_found"}), 404

        tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
        tenant_config = _load_tenant_config(private_dir, tenant_ref)
        if tenant_config is None:
            return jsonify({"ok": False, "error": "tenant_config_not_found"}), 503

        credentials = _resolve_paypal_credentials(tenant_config)
        if credentials is None:
            return jsonify({"ok": False, "error": "credentials_not_set"}), 503

        client_id, client_secret = credentials
        environment = _as_text(domain_profile.get("environment")) or "sandbox"
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
            order_body = json.dumps({
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
            }).encode()
            req = urllib.request.Request(
                f"{base_url}/v2/checkout/orders",
                data=order_body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                order_result = json.loads(resp.read().decode())
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

    @app.post("/__fnd/paypal/capture-order")
    def fnd_paypal_capture_order() -> tuple[Any, int]:
        import urllib.request
        import urllib.error

        payload = _json_payload()
        domain = _normalize_domain(request.host)
        order_id = _as_text(payload.get("order_id"))

        if not order_id:
            return jsonify({"ok": False, "error": "missing_order_id"}), 400

        private_dir = host_config.private_dir
        domain_profile = _load_domain_profile(private_dir, domain)
        if domain_profile is None:
            return jsonify({"ok": False, "error": "domain_profile_not_found"}), 404

        tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
        tenant_config = _load_tenant_config(private_dir, tenant_ref)
        if tenant_config is None:
            return jsonify({"ok": False, "error": "tenant_config_not_found"}), 503

        credentials = _resolve_paypal_credentials(tenant_config)
        if credentials is None:
            return jsonify({"ok": False, "error": "credentials_not_set"}), 503

        client_id, client_secret = credentials
        environment = _as_text(domain_profile.get("environment")) or "sandbox"
        base_url = _paypal_base_url(environment)

        try:
            access_token = _get_paypal_access_token(client_id, client_secret, base_url)
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
                capture_result = json.loads(resp.read().decode())
        except Exception as exc:
            return jsonify({"ok": False, "error": "paypal_api_error", "detail": str(exc)}), 502

        status = _as_text(capture_result.get("status"))
        capture_id = ""
        capture_amount = ""
        currency_code = ""
        purchase_units = capture_result.get("purchase_units", [])
        if purchase_units and isinstance(purchase_units, list):
            captures = purchase_units[0].get("payments", {}).get("captures", [])
            if captures and isinstance(captures, list):
                capture_id = _as_text(captures[0].get("id"))
                amount_obj = captures[0].get("amount", {})
                capture_amount = _as_text(amount_obj.get("value"))
                currency_code = _as_text(amount_obj.get("currency_code"))

        import time as _time
        orders_log = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
        _append_to_ndjson(orders_log, {
            "event": "capture_order",
            "order_id": order_id,
            "capture_id": capture_id,
            "domain": domain,
            "amount": capture_amount,
            "currency_code": currency_code,
            "status": status,
            "timestamp_ms": int(_time.time() * 1000),
        })

        return jsonify({"ok": True, "capture_id": capture_id, "status": status,
                        "amount": capture_amount, "currency_code": currency_code}), 200

    return app


__all__ = [
    "HOST_SHAPE",
    "V2_PORTAL_ERROR_SCHEMA",
    "V2_PORTAL_HEALTH_SCHEMA",
    "PORTAL_SHELL_ASSET_MANIFEST_SCHEMA",
    "V2PortalHostConfig",
    "build_shell_asset_manifest",
    "create_app",
]
