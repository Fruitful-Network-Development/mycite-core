from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
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

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import run_portal_aws_csm
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import (
    LegacyMapsAliasUnsupportedError,
    run_portal_cts_gis,
)
from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import run_portal_fnd_ebi
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
    run_portal_shell_entry,
    run_system_profile_basics_action,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    AWS_CSM_TOOL_REQUEST_SCHEMA,
    CTS_GIS_TOOL_REQUEST_SCHEMA,
    FND_EBI_TOOL_REQUEST_SCHEMA,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    build_tool_exposure_policy,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
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
PORTAL_SHELL_MODULE_FILES = (
    "v2_portal_shell_region_renderers.js",
    "v2_portal_tool_surface_adapter.js",
    "v2_portal_aws_workspace.js",
    "v2_portal_system_workspace.js",
    "v2_portal_network_workspace.js",
    "v2_portal_workbench_renderers.js",
    "v2_portal_inspector_renderers.js",
    "v2_portal_shell_core.js",
    "v2_portal_shell_watchdog.js",
)


def _static_asset_descriptor(filename: str, *, build_id: str, asset_id: str) -> dict[str, str]:
    path = f"/portal/static/{filename}"
    suffix = f"?v={build_id}" if build_id else ""
    return {
        "asset_id": asset_id,
        "file": filename,
        "path": path,
        "url": f"{path}{suffix}",
    }


def build_shell_asset_manifest(build_id: str = PORTAL_BUILD_ID) -> dict[str, Any]:
    safe_build_id = _as_text(build_id)
    return {
        "schema": PORTAL_SHELL_ASSET_MANIFEST_SCHEMA,
        "build_id": safe_build_id,
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
            "shell_modules": [
                _static_asset_descriptor(
                    filename,
                    build_id=safe_build_id,
                    asset_id=filename.rsplit(".", 1)[0],
                )
                for filename in PORTAL_SHELL_MODULE_FILES
            ],
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
        capabilities.extend(["fnd_peripheral_routing", "hosted_site_visibility"])
    return capabilities


def _bootstrap_request(surface_id: str, *, portal_instance_id: str, query_params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    portal_scope = PortalScope(
        scope_id=portal_instance_id,
        capabilities=_default_capabilities(portal_instance_id),
    )
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
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "portal_instance_id": self.portal_instance_id,
            "portal_domain": self.portal_domain,
            "public_dir": str(self.public_dir),
            "private_dir": str(self.private_dir),
            "data_dir": str(self.data_dir),
            "webapps_root": str(self.webapps_root),
        }


TOOL_SLUG_TO_SURFACE_ID = {
    "aws-csm": AWS_CSM_TOOL_SURFACE_ID,
    "cts-gis": CTS_GIS_TOOL_SURFACE_ID,
    "fnd-ebi": FND_EBI_TOOL_SURFACE_ID,
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
    if code in {"data_dir_not_configured"}:
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
    }


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
        if tool_slug in {"aws", "aws-narrow-write", "aws-csm-sandbox", "aws-csm-onboarding"}:
            return redirect("/portal/system/tools/aws-csm", code=302)
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
                )
            )
        except LegacyMapsAliasUnsupportedError as exc:
            return _error_response(exc.code, str(exc), status_code=400)
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

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
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/aws-csm")
    def portal_aws_csm() -> tuple[Any, int]:
        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = AWS_CSM_TOOL_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_aws_csm(
                    payload,
                    private_dir=host_config.private_dir,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/cts-gis")
    def portal_cts_gis() -> tuple[Any, int]:
        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = CTS_GIS_TOOL_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_cts_gis(
                    payload,
                    data_dir=host_config.data_dir,
                    private_dir=host_config.private_dir,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                )
            )
        except LegacyMapsAliasUnsupportedError as exc:
            return _error_response(exc.code, str(exc), status_code=400)
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

    @app.post("/portal/api/v2/system/tools/fnd-ebi")
    def portal_fnd_ebi() -> tuple[Any, int]:
        try:
            payload = _json_payload()
            if "schema" not in payload:
                payload["schema"] = FND_EBI_TOOL_REQUEST_SCHEMA
            return _runtime_response(
                run_portal_fnd_ebi(
                    payload,
                    webapps_root=host_config.webapps_root,
                    tool_exposure_policy=host_config.tool_exposure_policy,
                )
            )
        except ValueError as exc:
            return _error_response("invalid_request", str(exc))

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
