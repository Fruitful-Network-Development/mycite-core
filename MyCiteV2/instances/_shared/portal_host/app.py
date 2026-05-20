from __future__ import annotations

import base64
import glob
import json
import logging
import os
import re
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
    CTS_GIS_TOOL_ACTION_REQUEST_SCHEMA,
    CTS_GIS_TOOL_REQUEST_SCHEMA,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    WORKBENCH_UI_TOOL_REQUEST_SCHEMA,
    build_tool_exposure_policy,
)
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
    build_portal_shell_state_from_query,
    build_portal_tool_registry_entries,
    requires_shell_state_machine,
)

_aws_peripheral = AwsPeripheralCloudAdapter()

V2_PORTAL_HEALTH_SCHEMA = "mycite.v2.portal.health.v1"
V2_PORTAL_ERROR_SCHEMA = "mycite.v2.portal.error.v1"
HOST_SHAPE = "v2_native"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
    try:
        import subprocess

        repo_root = Path(__file__).resolve().parents[4]
        sha = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode("ascii").strip()
        if sha:
            return f"git-{sha}"
    except Exception:
        pass
    return "not-set"


PORTAL_BUILD_ID = _default_portal_build_id()
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

    # CTS-GIS workbench projection cache (datum recognition for 413 documents).
    if config.authority_db_file is not None:
        try:
            from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
                _datum_store_for_authority_db,
                _hydrate_compiled_workbench_documents,
            )

            datum_store = _datum_store_for_authority_db(config.authority_db_file)
            if datum_store is not None:
                _hydrate_compiled_workbench_documents(
                    service_surface={},
                    datum_store=datum_store,
                    tenant_id=config.portal_instance_id,
                )
        except Exception:
            pass


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

_CONTACT_LOG_SCHEMA = "mycite.webapp.contact_log.v1"

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

    Newsletter state lives in JSON under
    ``<private>/utilities/tools/newsletter/`` per the peripheral
    architecture: extensions read grantee/extension JSON files, no MOS
    authority is consulted.
    """
    from MyCiteV2.packages.adapters.filesystem import (
        FilesystemNewsletterStateAdapter,
    )

    return FilesystemNewsletterStateAdapter(host_config.private_dir)


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
    # Sort contacts ascending by email — consistent with NewsletterService.subscribe() line 298
    contact_log["contacts"] = [by_email[k] for k in sorted(by_email.keys())]
    # dispatches array passes through unchanged
    return current


def _fnd_newsletter_request_field(field: str) -> str:
    """Extract a field from JSON body or form data."""
    data = request.get_json(silent=True)
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
        from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
            _load_grantee_profiles,
        )

        for grantee in _load_grantee_profiles(private_dir):
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


def _send_donation_receipt_email(
    *,
    private_dir: Path,
    domain: str,
    donor_email: str,
    donor_name: str,
    amount: str,
    currency_code: str,
    capture_id: str,
    receipt_path: Path,
) -> str:
    """Email the tax-exempt receipt PDF to the donor via SES send_raw_email.

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

    from email.message import EmailMessage

    display_amount = f"{amount} {currency_code}".strip()
    org_label = _as_text(grantee.get("label")) if grantee else ""
    body_text = (
        f"Thank you{(', ' + donor_name) if donor_name else ''}, for your"
        f" {display_amount} contribution to {org_label or domain}.\n\n"
        f"Capture ID: {capture_id}\n\n"
        f"Attached is our blanket sales-tax-exempt certificate for your records.\n"
        f"No goods or services were provided in exchange for this contribution.\n"
    )
    from_address = _as_text(aws_cfg.get("from_address")) or ses_identity
    from_name = _as_text(aws_cfg.get("from_name"))
    msg = EmailMessage()
    msg["Subject"] = f"Donation receipt — {org_label or domain}"
    msg["From"] = f'"{from_name}" <{from_address}>' if from_name else from_address
    msg["To"] = donor_email
    reply_to = _as_text(aws_cfg.get("reply_to"))
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body_text)
    try:
        pdf_bytes = receipt_path.read_bytes()
    except OSError as exc:
        _log.error(
            "donation_receipt_pdf_unreadable",
            extra={"domain": domain, "capture_id": capture_id, "path": str(receipt_path), "err": str(exc)},
        )
        return "failed"
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=receipt_path.name,
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
    def portal_system_tool(tool_slug: str) -> Any:
        # Phase 2 (portal_tool_surface_contract.md): the FND-CSM tool surface
        # is being retired. Its content now lives under Utilities → Tool Exposure
        # as four extensions (ext_aws_email, ext_analytics, ext_newsletter,
        # ext_paypal). Redirect legacy bookmarks until Phase 3 deletes the
        # surface entry entirely.
        if tool_slug == "fnd-csm":
            return redirect("/portal/utilities/tool-exposure", code=302)
        # Plan v2: the dedicated tool surfaces collapse into the unified
        # workbench at /portal/system. Old bookmarks 302 to the new shape:
        #   - workbench-ui → /portal/system (system sandbox)
        #   - agro-erp     → /portal/system?sandbox=agro_erp
        #   - cts-gis      → /portal/system?tool=cts_gis
        if tool_slug == "workbench-ui":
            return redirect("/portal/system", code=302)
        if tool_slug == "agro-erp":
            return redirect("/portal/system?sandbox=agro_erp", code=302)
        if tool_slug == "cts-gis":
            return redirect("/portal/system?tool=cts_gis", code=302)
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
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
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
                    authority_db_file=host_config.authority_db_file,
                    data_dir=host_config.data_dir,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/fnd-csm/actions")
    def portal_fnd_csm_actions() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
            run_portal_fnd_csm_action,
        )
        from MyCiteV2.instances._shared.runtime.runtime_platform import (
            FND_CSM_TOOL_ACTION_REQUEST_SCHEMA,
        )

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
                    authority_db_file=host_config.authority_db_file,
                    data_dir=host_config.data_dir,
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
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
            run_portal_cts_gis_action,
        )

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
        from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
            run_portal_cts_gis_action,
        )
        from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
            run_datum_workbench_mutation_action,
        )

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
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
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
            from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
                _load_grantee_profiles,
            )

            for grantee in _load_grantee_profiles(host_config.private_dir):
                domains = [str(d).lower() for d in (grantee.get("domains") or [])]
                if domain.lower() in domains:
                    return grantee
        except Exception:
            pass
        return {}

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
          - ``"pending"`` if forwarding is not configured (no
            forward_to_email or no aws_ses identity)
          - ``"failed"`` on SES failure (the operator can retry from
            the extension tab)
        """
        connect_cfg = grantee.get("connect") if isinstance(grantee.get("connect"), dict) else {}
        aws_cfg = grantee.get("aws_ses") if isinstance(grantee.get("aws_ses"), dict) else {}
        forward_to = _as_text(connect_cfg.get("forward_to_email"))
        ses_identity = _as_text(aws_cfg.get("identity"))
        if not forward_to or not ses_identity:
            return "pending"
        display_subject = subject or f"Connect message from {visitor_email}"
        body_text = (
            f"From: {visitor_name or visitor_email} <{visitor_email}>\n"
            f"Domain: {domain}\n"
            f"Subject: {display_subject}\n\n"
            f"{message}\n"
        )
        try:
            _aws_peripheral.send_email(
                aws_ses_profile=aws_cfg,
                to=[forward_to],
                subject=f"[Connect] {display_subject}",
                body_text=body_text,
                reply_to=[visitor_email] if visitor_email else None,
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
        subject = _fnd_newsletter_request_field("subject")
        display_name = " ".join(t for t in (first_name, last_name) if t) or email

        # Attempt SES forward first so the persisted row reflects the
        # actual delivery outcome. If forwarding isn't configured we
        # still persist with forward_status=pending — the operator can
        # see the queue in the Connect extension tab and retry later.
        grantee = _resolve_grantee_for_domain(domain)
        forward_status = _ses_forward_connect_message(
            grantee=grantee,
            domain=domain,
            visitor_email=email,
            visitor_name=display_name,
            subject=subject,
            message=message,
        )

        try:
            from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                run_datum_workbench_mutation_action,
            )

            result = run_datum_workbench_mutation_action(
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
                    "subject": subject,
                    "message": message,
                    "forward_status": forward_status,
                },
                authority_db_file=host_config.authority_db_file,
                portal_instance_id=host_config.portal_instance_id,
            )
        except Exception:
            return _connect_response(
                is_json_request, ok=False, status=500,
                error="storage_error", forward_status=forward_status,
            )

        if not result.get("ok"):
            return _connect_response(
                is_json_request, ok=False, status=500,
                error="storage_error", forward_status=forward_status,
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
            )
        except Exception:
            return jsonify({"ok": False, "error": "storage_error"}), 500

        if not result.get("ok"):
            return jsonify({"ok": False, "error": "storage_error"}), 500
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

    @app.post("/__fnd/email/admin/suspend")
    def fnd_email_admin_suspend() -> tuple[Any, int]:
        payload = _json_payload()
        profile_id = _as_text(payload.get("profile_id"))
        suspended = bool(payload.get("suspended"))

        if not profile_id:
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
    # FND Email admin route — resend handoff email (2026-05-18)
    # ------------------------------------------------------------------
    # Re-dispatches the SMTP-credentials handoff email for an operator
    # mailbox that has not yet onboarded (lifecycle still ``draft`` and
    # ``handoff_status == instruction_sent``). The send_handoff_email
    # action is declared in the Nimm mutation contract, but the apply
    # route (/portal/api/v2/mutations/<action>) only dispatches to
    # cts_gis / datum_workbench target authorities today — so this
    # sibling route gives the email-admin extension a direct entry
    # point that matches the Suspend route's shape.

    @app.post("/__fnd/email/admin/resend-handoff")
    def fnd_email_admin_resend_handoff() -> tuple[Any, int]:
        payload = _json_payload()
        profile_id = _as_text(payload.get("profile_id"))

        if not profile_id:
            return jsonify({"ok": False, "error": "missing_profile_id"}), 400
        if host_config.private_dir is None:
            return jsonify({"ok": False, "error": "private_dir_not_configured"}), 500

        try:
            from MyCiteV2.packages.adapters.event_transport import (
                AwsEc2RoleOnboardingCloudAdapter,
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

        adapter = AwsEc2RoleOnboardingCloudAdapter()
        try:
            result = adapter.send_handoff_email(current)
        except (ValueError, RuntimeError) as exc:
            return jsonify(
                {"ok": False, "error": "send_failed", "detail": str(exc)}
            ), 502
        except Exception as exc:
            return jsonify(
                {"ok": False, "error": "send_failed", "detail": str(exc)}
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
    # FND Analytics admin route (Phase 14d.4)
    # ------------------------------------------------------------------
    # The Analytics extension card surfaces a Refresh button that POSTs
    # here. The handler re-runs ``_aggregate_for_domain`` from
    # ``MyCiteV2.scripts.sync_fnd_analytics_summary`` for the requested
    # domain and persists the result through
    # ``MosDatumAnalyticsSummaryAdapter.save_summary``. Returns the new
    # counts so the client can refresh the card without a full page
    # reload (the workbench renderer triggers a shell reload regardless).

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

    @app.post("/__fnd/analytics/event")
    def fnd_analytics_event() -> tuple[Any, int]:
        from MyCiteV2.packages.adapters.filesystem import AnalyticsEventPathResolver
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
            year_month = received_at_utc[:7]
            # Canonical analytics root: <private>/utilities/tools/analytics.
            # The resolver falls back to MYCITE_ANALYTICS_ROOT env / default
            # when no explicit root is provided, but we wire it explicitly
            # from host_config so smoke tests can boot against a tempdir.
            analytics_root = None
            if host_config.private_dir is not None:
                analytics_root = (
                    Path(host_config.private_dir) / "utilities" / "tools" / "analytics"
                )
            resolver = AnalyticsEventPathResolver(analytics_root=analytics_root)
            resolver.append_payload(
                domain=domain, year_month=year_month, payload=event.to_dict()
            )
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
        from MyCiteV2.packages.adapters.filesystem import AnalyticsEventPathResolver

        payload = _json_payload()
        domain = _normalize_domain(_as_text(payload.get("domain")))
        if not domain:
            return jsonify({"ok": False, "error": "missing_domain"}), 400
        if host_config.authority_db_file is None:
            return jsonify({"ok": False, "error": "authority_db_not_configured"}), 500

        analytics_root = None
        if host_config.private_dir is not None:
            analytics_root = (
                Path(host_config.private_dir) / "utilities" / "tools" / "analytics"
            )
        resolver = AnalyticsEventPathResolver(analytics_root=analytics_root)
        if not resolver.iter_domain_event_files(domain):
            return jsonify({"ok": False, "error": "no_events_directory"}), 404

        try:
            from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
                MosDatumAnalyticsSummaryAdapter,
            )
            from MyCiteV2.scripts.sync_fnd_analytics_summary import (
                DEFAULT_WINDOW_MONTHS,
                _aggregate_for_domain,
            )
        except Exception:
            return jsonify({"ok": False, "error": "module_load_failed"}), 500

        try:
            window_months = int(payload.get("window_months") or DEFAULT_WINDOW_MONTHS)
        except (TypeError, ValueError):
            window_months = DEFAULT_WINDOW_MONTHS

        try:
            counts, recent = _aggregate_for_domain(
                resolver=resolver,
                domain=domain,
                window_months=window_months,
            )
            adapter = MosDatumAnalyticsSummaryAdapter(
                authority_db_file=host_config.authority_db_file,
                tenant_id=host_config.portal_instance_id or "fnd",
            )
            adapter.save_summary(
                domain=domain,
                window_months=window_months,
                counts=counts,
                recent_events=recent,
            )
        except Exception:
            return jsonify({"ok": False, "error": "refresh_failed"}), 500

        return jsonify(
            {
                "ok": True,
                "domain": domain,
                "window_months": window_months,
                "counts": counts,
                "recent_events_captured": len(recent),
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
        if host_config.authority_db_file is not None:
            try:
                from MyCiteV2.packages.adapters.sql.fnd_paypal import (
                    MosDatumPayPalOrdersAdapter,
                )

                adapter = MosDatumPayPalOrdersAdapter(
                    authority_db_file=host_config.authority_db_file,
                    tenant_id=host_config.portal_instance_id or "fnd",
                )
                orders = adapter.load_orders(domain=domain) or []
            except Exception:
                orders = []

        # Filesystem fallback (mirrors the extension renderer).
        if not orders and host_config.private_dir is not None:
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

    @app.post("/__fnd/paypal/capture-order")
    def fnd_paypal_capture_order() -> tuple[Any, int]:
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

        credentials = _resolve_paypal_credentials_for_domain(private_dir, domain, tenant_config)
        if credentials is None:
            return jsonify({"ok": False, "error": "credentials_not_set"}), 503

        client_id, client_secret, resolved_env = credentials
        environment = resolved_env or _as_text(domain_profile.get("environment")) or "sandbox"
        base_url = _paypal_base_url(environment)

        try:
            access_token = _get_paypal_access_token(client_id, client_secret, base_url)
            capture_result = _capture_paypal_order(
                access_token=access_token,
                base_url=base_url,
                order_id=order_id,
            )
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

        response: dict[str, Any] = {
            "ok": True,
            "capture_id": capture_id,
            "status": status,
            "amount": capture_amount,
            "currency_code": currency_code,
        }

        # Receipt fulfillment (best-effort): when the capture is COMPLETED and
        # the domain has a configured receipt artifact, expose a download URL
        # and try to email the donor a copy. Email failures are logged but
        # never fail the capture response.
        if status.upper() == "COMPLETED":
            receipt_path = _resolve_receipt_artifact(private_dir, domain)
            if receipt_path is not None:
                response["receipt_document_url"] = (
                    f"/__fnd/donation/receipt-document?domain={urllib.parse.quote(domain, safe='')}"
                )
                create_entry = _find_create_order_entry(orders_log, order_id)
                donor_email = _as_text(create_entry.get("donor_email")) if create_entry else ""
                donor_name = _as_text(create_entry.get("donor_name")) if create_entry else ""
                email_status = _send_donation_receipt_email(
                    private_dir=private_dir,
                    domain=domain,
                    donor_email=donor_email,
                    donor_name=donor_name,
                    amount=capture_amount,
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
                response["receipt_email_status"] = email_status

        return jsonify(response), 200

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
    # ------------------------------------------------------------------

    def _tolling_parse_date(value: str) -> date | None:
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    def _tolling_default_window() -> tuple[date, date]:
        today = datetime.now(UTC).date()
        # AWS Cost Explorer convention: end-exclusive. Default to
        # current month-to-date (start = first of month, end = today).
        return today.replace(day=1), today

    @app.get("/__fnd/tolling/itemize")
    def fnd_tolling_itemize() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            bandwidth_share_for_grantee,
            domains_for_grantee,
            resolve_grantee_from_headers,
        )
        from MyCiteV2.packages.peripherals.aws.contracts import CostBreakdown

        requested_msn = _as_text(request.args.get("grantee"))
        from_raw = _as_text(request.args.get("from"))
        to_raw = _as_text(request.args.get("to"))

        # Scope guard: if oauth2-proxy headers are present, the caller
        # must match the `?grantee=` argument. If no auth headers
        # (operator tooling / development), allow any `?grantee=`.
        caller = resolve_grantee_from_headers(request.headers)
        if caller is not None:
            caller_msn = _as_text(caller.get("msn_id"))
            if requested_msn and requested_msn != caller_msn:
                return jsonify({"ok": False, "error": "scope_mismatch"}), 403
            if not requested_msn:
                requested_msn = caller_msn

        if not requested_msn:
            return jsonify({"ok": False, "error": "missing_grantee"}), 400

        start_d = _tolling_parse_date(from_raw) if from_raw else None
        end_d = _tolling_parse_date(to_raw) if to_raw else None
        if start_d is None or end_d is None:
            default_start, default_end = _tolling_default_window()
            start_d = start_d or default_start
            end_d = end_d or default_end

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
        }), 200

    @app.get("/__fnd/tolling/overview")
    def fnd_tolling_overview() -> tuple[Any, int]:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            bandwidth_share_by_domain,
            load_grantee_directory,
        )

        from_raw = _as_text(request.args.get("from"))
        to_raw = _as_text(request.args.get("to"))
        start_d = _tolling_parse_date(from_raw) if from_raw else None
        end_d = _tolling_parse_date(to_raw) if to_raw else None
        if start_d is None or end_d is None:
            default_start, default_end = _tolling_default_window()
            start_d = start_d or default_start
            end_d = end_d or default_end

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

    @app.get("/__fnd/tolling/whoami")
    def fnd_tolling_whoami() -> tuple[Any, int]:
        """Resolve the caller's grantee identity from oauth2-proxy
        headers. Used by the per-client dashboard JS to learn the
        active grantee_id before fetching itemize. 200 with empty
        grantee when unauthenticated."""
        from MyCiteV2.instances._shared.runtime.utilities_extensions.tolling import (
            resolve_grantee_from_headers,
        )

        caller = resolve_grantee_from_headers(request.headers)
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
