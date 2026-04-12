from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory

from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    run_admin_aws_csm_onboarding,
    run_admin_aws_csm_sandbox_read_only,
    run_admin_aws_narrow_write,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
    TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
    TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
)
from MyCiteV2.instances._shared.runtime.tenant_audit_activity_runtime import (
    run_trusted_tenant_audit_activity,
)
from MyCiteV2.instances._shared.runtime.tenant_operational_status_runtime import (
    run_trusted_tenant_operational_status,
)
from MyCiteV2.instances._shared.runtime.tenant_portal_runtime import run_trusted_tenant_portal_home
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_SHELL_REQUEST_SCHEMA,
    ADMIN_TOOL_REGISTRY_SLICE_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_SLICE_ID,
    DATUM_RESOURCE_WORKBENCH_SLICE_ID,
    INTERNAL_ADMIN_SCOPE_ID,
    build_portal_activity_dispatch_bodies,
)
from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
    TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
    build_trusted_tenant_portal_dispatch_bodies,
)
from MyCiteV2.packages.adapters.filesystem import (
    AnalyticsEventPathResolver,
    FilesystemSystemDatumStoreAdapter,
    is_live_aws_profile_file,
)
from MyCiteV2.packages.ports.datum_store import SystemDatumStoreRequest

V2_PORTAL_HEALTH_SCHEMA = "mycite.v2.portal.health.v1"
V2_PORTAL_ERROR_SCHEMA = "mycite.v2.portal.error.v1"
HOST_SHAPE = "v2_native"

TENANT_DOMAINS = {
    "fnd": "fruitfulnetworkdevelopment.com",
    "tff": "trappfamilyfarm.com",
}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


# Set on the server (e.g. systemd Environment=) so the HTML shows which build is running.
PORTAL_BUILD_ID = _as_text(os.environ.get("MYCITE_V2_PORTAL_BUILD_ID")) or "not-set"


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name) or default)


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


def _validate_existing_live_profile_file(path: Path | None, *, env_name: str, required: bool) -> Path | None:
    if path is None:
        if required:
            raise ValueError(f"{env_name} is required for the V2 portal host")
        return None
    resolved = Path(path)
    if not resolved.exists():
        raise ValueError(f"{env_name} must point to an existing file: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"{env_name} must point to a file: {resolved}")
    if not is_live_aws_profile_file(resolved):
        raise ValueError(
            f"{env_name} must point to a mycite.service_tool.aws_csm.profile.v1 JSON file: {resolved}"
        )
    return resolved


def _validate_audit_sink(path: Path | None, *, env_name: str, required: bool) -> Path | None:
    if path is None:
        if required:
            raise ValueError(f"{env_name} is required for the V2 portal host")
        return None
    resolved = Path(path)
    if resolved.exists() and not resolved.is_file():
        raise ValueError(f"{env_name} must point to a file path, not a directory: {resolved}")
    parent = resolved.parent
    if not parent.exists():
        raise ValueError(f"{env_name} parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise ValueError(f"{env_name} parent must be a directory: {parent}")
    return resolved


def _current_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _unix_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _request_domain() -> str:
    host = _as_text(request.headers.get("X-Forwarded-Host") or request.headers.get("Host")).lower()
    domain = host.split(",", 1)[0].split(":", 1)[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _analytics_request_payload() -> dict[str, Any]:
    json_payload = request.get_json(silent=True)
    if isinstance(json_payload, dict):
        return json_payload
    if request.form:
        return {key: request.form.get(key) for key in sorted(request.form.keys())}
    raw = request.get_data(as_text=True) or ""
    return {"raw": raw[:8192]} if raw else {}


@dataclass(frozen=True)
class V2PortalHostConfig:
    tenant_id: str
    public_dir: Path
    private_dir: Path
    data_dir: Path
    analytics_domain: str
    analytics_webapps_root: Path
    aws_status_file: Path | None = None
    aws_csm_sandbox_status_file: Path | None = None
    aws_audit_storage_file: Path | None = None
    admin_audit_storage_file: Path | None = None

    def __post_init__(self) -> None:
        tenant_id = _as_text(self.tenant_id).lower()
        if not tenant_id:
            raise ValueError("v2_portal_host.tenant_id is required")
        domain = _as_text(self.analytics_domain).lower()
        if not domain:
            raise ValueError("v2_portal_host.analytics_domain is required")
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(
            self,
            "public_dir",
            _validate_existing_dir(Path(self.public_dir), env_name="PUBLIC_DIR"),
        )
        object.__setattr__(
            self,
            "private_dir",
            _validate_existing_dir(Path(self.private_dir), env_name="PRIVATE_DIR"),
        )
        object.__setattr__(
            self,
            "data_dir",
            _validate_existing_dir(Path(self.data_dir), env_name="DATA_DIR"),
        )
        object.__setattr__(self, "analytics_domain", domain)
        object.__setattr__(
            self,
            "analytics_webapps_root",
            _validate_existing_dir(Path(self.analytics_webapps_root), env_name="MYCITE_WEBAPPS_ROOT"),
        )
        object.__setattr__(
            self,
            "aws_status_file",
            _validate_existing_live_profile_file(
                None if self.aws_status_file is None else Path(self.aws_status_file),
                env_name="MYCITE_V2_AWS_STATUS_FILE",
                required=True,
            ),
        )
        object.__setattr__(
            self,
            "aws_csm_sandbox_status_file",
            _validate_existing_live_profile_file(
                None if self.aws_csm_sandbox_status_file is None else Path(self.aws_csm_sandbox_status_file),
                env_name="MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE",
                required=False,
            ),
        )
        object.__setattr__(
            self,
            "aws_audit_storage_file",
            _validate_audit_sink(
                None if self.aws_audit_storage_file is None else Path(self.aws_audit_storage_file),
                env_name="MYCITE_V2_AWS_AUDIT_FILE",
                required=True,
            ),
        )
        object.__setattr__(
            self,
            "admin_audit_storage_file",
            _validate_audit_sink(
                None if self.admin_audit_storage_file is None else Path(self.admin_audit_storage_file),
                env_name="MYCITE_V2_ADMIN_AUDIT_FILE",
                required=True,
            ),
        )

    @classmethod
    def from_env(cls) -> "V2PortalHostConfig":
        tenant_id = _required_env_text("PORTAL_INSTANCE_ID").lower()
        runtime_flavor = _as_text(os.environ.get("PORTAL_RUNTIME_FLAVOR")).lower()
        if runtime_flavor and runtime_flavor != tenant_id:
            raise ValueError(
                "PORTAL_RUNTIME_FLAVOR must match PORTAL_INSTANCE_ID when both are set "
                f"(got {runtime_flavor!r} vs {tenant_id!r})"
            )
        status_file = _required_env_text("MYCITE_V2_AWS_STATUS_FILE")
        sandbox_status = _as_text(os.environ.get("MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE"))
        aws_audit_file = _required_env_text("MYCITE_V2_AWS_AUDIT_FILE")
        admin_audit_file = _required_env_text("MYCITE_V2_ADMIN_AUDIT_FILE")
        return cls(
            tenant_id=tenant_id,
            public_dir=Path(_required_env_text("PUBLIC_DIR")),
            private_dir=Path(_required_env_text("PRIVATE_DIR")),
            data_dir=Path(_required_env_text("DATA_DIR")),
            analytics_domain=_required_env_text("MYCITE_ANALYTICS_DOMAIN"),
            analytics_webapps_root=Path(_required_env_text("MYCITE_WEBAPPS_ROOT")),
            aws_status_file=Path(status_file),
            aws_csm_sandbox_status_file=Path(sandbox_status) if sandbox_status else None,
            aws_audit_storage_file=Path(aws_audit_file),
            admin_audit_storage_file=Path(admin_audit_file),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "public_dir": str(self.public_dir),
            "private_dir": str(self.private_dir),
            "data_dir": str(self.data_dir),
            "analytics_domain": self.analytics_domain,
            "analytics_webapps_root": str(self.analytics_webapps_root),
        }


URL_SLUG_TO_SLICE_ID: dict[str, str] = {
    "home": ADMIN_HOME_STATUS_SLICE_ID,
    "system": ADMIN_HOME_STATUS_SLICE_ID,
    "tools": ADMIN_TOOL_REGISTRY_SLICE_ID,
    "registry": ADMIN_TOOL_REGISTRY_SLICE_ID,
    "aws": AWS_READ_ONLY_SLICE_ID,
    "aws-write": AWS_NARROW_WRITE_SLICE_ID,
    "aws-csm-sandbox": AWS_CSM_SANDBOX_SLICE_ID,
    "datum": DATUM_RESOURCE_WORKBENCH_SLICE_ID,
    "mediate_tool-aws_platform_admin": AWS_READ_ONLY_SLICE_ID,
}


def _bootstrap_request_for_slug(slug: str, tenant_id: str) -> dict[str, Any]:
    """Build the correct shell request body for a URL slug, using the same
    dispatch bodies the activity bar and control panel use."""
    slice_id = URL_SLUG_TO_SLICE_ID.get(slug, ADMIN_HOME_STATUS_SLICE_ID)
    bodies = build_portal_activity_dispatch_bodies(portal_tenant_id=tenant_id)
    return bodies.get(slice_id, {
        "schema": ADMIN_SHELL_REQUEST_SCHEMA,
        "requested_slice_id": ADMIN_HOME_STATUS_SLICE_ID,
        "tenant_scope": {"scope_id": INTERNAL_ADMIN_SCOPE_ID, "audience": "internal"},
    })


def _tenant_portal_bootstrap_request(tenant_id: str) -> dict[str, Any]:
    bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id=tenant_id)
    return bodies.get(
        BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        {
            "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
            "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            "tenant_scope": {"scope_id": tenant_id, "audience": "trusted-tenant"},
        },
    )


def _tenant_operational_status_bootstrap_request(tenant_id: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
        "tenant_scope": {"scope_id": tenant_id, "audience": "trusted-tenant"},
    }


def _tenant_audit_activity_bootstrap_request(tenant_id: str) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
        "tenant_scope": {"scope_id": tenant_id, "audience": "trusted-tenant"},
    }


def _json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _runtime_status_code(envelope: dict[str, Any]) -> int:
    error = envelope.get("error")
    if not isinstance(error, dict) or not error:
        return 200
    code = _as_text(error.get("code"))
    if code == "audience_not_allowed":
        return 403
    if code in {"slice_unknown", "status_snapshot_not_found"}:
        return 404
    if code in {
        "status_source_not_configured",
        "audit_log_not_configured",
        "publication_source_not_configured",
    }:
        return 503
    if code == "tenant_scope_mismatch":
        return 403
    return 400


def _runtime_response(envelope: dict[str, Any]) -> tuple[Any, int]:
    if envelope.get("schema") not in {
        ADMIN_RUNTIME_ENVELOPE_SCHEMA,
        TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
    }:
        return (
            jsonify(
                {
                    "schema": V2_PORTAL_ERROR_SCHEMA,
                    "ok": False,
                    "error": {
                        "code": "invalid_runtime_envelope",
                        "message": "The V2 runtime returned an invalid admin envelope.",
                    },
                }
            ),
            502,
        )
    return jsonify(envelope), _runtime_status_code(envelope)


def _required_live_aws_status_file(config: V2PortalHostConfig) -> Path | None:
    if config.aws_status_file is not None and is_live_aws_profile_file(config.aws_status_file):
        return config.aws_status_file
    return None


def _optional_sandbox_live_profile_file(config: V2PortalHostConfig) -> Path | None:
    """Separate from ``MYCITE_V2_AWS_STATUS_FILE``: optional staging/sandbox profile path."""
    p = config.aws_csm_sandbox_status_file
    if p is not None and is_live_aws_profile_file(p):
        return p
    return None


def _portal_package_static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def _build_health(config: V2PortalHostConfig) -> dict[str, Any]:
    static_dir = _portal_package_static_dir()
    portal_css = static_dir / "portal.css"
    portal_js = static_dir / "v2_portal_shell.js"
    datum_result = FilesystemSystemDatumStoreAdapter(config.data_dir).read_system_resource_workbench(
        SystemDatumStoreRequest(tenant_id=config.tenant_id)
    )
    analytics_month = _as_text(os.environ.get("MYCITE_ANALYTICS_YEAR_MONTH")) or _current_year_month()
    analytics_resolution = AnalyticsEventPathResolver(config.analytics_webapps_root).resolve_events_file(
        domain=config.analytics_domain,
        year_month=analytics_month,
    )
    aws_status_file = config.aws_status_file
    sandbox_file = config.aws_csm_sandbox_status_file
    aws_health = {
        "configured": aws_status_file is not None,
        "exists": bool(aws_status_file and aws_status_file.exists() and aws_status_file.is_file()),
        "live_profile_mapping": is_live_aws_profile_file(aws_status_file),
        "status_file": None if aws_status_file is None else str(aws_status_file),
        "audit_storage_file_configured": config.aws_audit_storage_file is not None,
        "sandbox_status_file": None if sandbox_file is None else str(sandbox_file),
        "sandbox_live_profile_mapping": is_live_aws_profile_file(sandbox_file),
    }
    datum_payload = datum_result.to_dict()
    static_ok = portal_css.is_file() and portal_js.is_file()
    health_ok = bool(datum_payload["ok"]) and bool(aws_health["live_profile_mapping"]) and static_ok

    return {
        "schema": V2_PORTAL_HEALTH_SCHEMA,
        "ok": health_ok,
        "host_shape": HOST_SHAPE,
        "tenant_id": config.tenant_id,
        "portal_static_bundle": {
            "package_static_dir": str(static_dir),
            "portal_css_present": portal_css.is_file(),
            "portal_css_size_bytes": portal_css.stat().st_size if portal_css.is_file() else 0,
            "v2_portal_shell_js_present": portal_js.is_file(),
            "static_url_path": "/portal/static",
            "static_ok": static_ok,
        },
        "state_roots": config.to_public_dict(),
        "datum_health": {
            "ok": datum_payload["ok"],
            "row_count": datum_payload["row_count"],
            "source_files": datum_payload["source_files"],
            "materialization_status": datum_payload["materialization_status"],
            "warnings": datum_payload["warnings"],
        },
        "analytics_root": analytics_resolution.to_dict(),
        "aws_config_health": aws_health,
    }


def create_app(config: V2PortalHostConfig | None = None) -> Flask:
    host_config = config or V2PortalHostConfig.from_env()
    _host_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(_host_dir / "templates"),
        static_folder=str(_host_dir / "static"),
        static_url_path="/portal/static",
    )
    app.config["MYCITE_V2_PORTAL_HOST_CONFIG"] = host_config

    @app.get("/healthz")
    @app.get("/portal/healthz")
    def healthz() -> tuple[Any, int]:
        payload = _build_health(host_config)
        return jsonify(payload), 200 if payload["ok"] else 503

    def _portal_shell_page(slug: str = "") -> str:
        return render_template(
            "portal.html",
            tenant_id=host_config.tenant_id,
            host_shape=HOST_SHAPE,
            analytics_domain=host_config.analytics_domain,
            portal_build_id=PORTAL_BUILD_ID,
            bootstrap_shell_request=_bootstrap_request_for_slug(slug, host_config.tenant_id),
            runtime_envelope_schema=ADMIN_RUNTIME_ENVELOPE_SCHEMA,
            shell_endpoint="/portal/api/v2/admin/shell",
            shell_loading_label="Loading admin shell…",
            logo_href="/portal/system",
        )

    def _tenant_portal_page() -> str:
        return render_template(
            "portal.html",
            tenant_id=host_config.tenant_id,
            host_shape=HOST_SHAPE,
            analytics_domain=host_config.analytics_domain,
            bootstrap_shell_request=_tenant_portal_bootstrap_request(host_config.tenant_id),
            portal_build_id=PORTAL_BUILD_ID,
            runtime_envelope_schema=TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
            shell_endpoint="/portal/api/v2/tenant/home",
            shell_loading_label="Loading portal home…",
            logo_href="/portal/home",
        )

    def _tenant_operational_status_page() -> str:
        return render_template(
            "portal.html",
            tenant_id=host_config.tenant_id,
            host_shape=HOST_SHAPE,
            analytics_domain=host_config.analytics_domain,
            bootstrap_shell_request=_tenant_operational_status_bootstrap_request(host_config.tenant_id),
            portal_build_id=PORTAL_BUILD_ID,
            runtime_envelope_schema=TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
            shell_endpoint="/portal/api/v2/tenant/operational-status",
            shell_loading_label="Loading operational status…",
            logo_href="/portal/status",
        )

    def _tenant_audit_activity_page() -> str:
        return render_template(
            "portal.html",
            tenant_id=host_config.tenant_id,
            host_shape=HOST_SHAPE,
            analytics_domain=host_config.analytics_domain,
            bootstrap_shell_request=_tenant_audit_activity_bootstrap_request(host_config.tenant_id),
            portal_build_id=PORTAL_BUILD_ID,
            runtime_envelope_schema=TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
            shell_endpoint="/portal/api/v2/tenant/audit-activity",
            shell_loading_label="Loading recent activity…",
            logo_href="/portal/activity",
        )

    @app.get("/portal")
    @app.get("/portal/")
    @app.get("/portal/home")
    def portal_home() -> str:
        return _tenant_portal_page()

    @app.get("/portal/status")
    def portal_status() -> str:
        return _tenant_operational_status_page()

    @app.get("/portal/activity")
    def portal_activity() -> str:
        return _tenant_audit_activity_page()

    @app.get("/portal/system")
    @app.get("/portal/system/<path:tool_slug>")
    def portal_system(tool_slug: str = "") -> str:
        slug = tool_slug.strip("/") if tool_slug else "system"
        return _portal_shell_page(slug)

    @app.post("/portal/api/v2/admin/shell")
    def admin_shell() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_admin_shell_entry(
                    _json_payload(),
                    audit_storage_file=host_config.admin_audit_storage_file,
                    portal_tenant_id=host_config.tenant_id,
                    aws_status_file=host_config.aws_status_file,
                    aws_csm_sandbox_status_file=host_config.aws_csm_sandbox_status_file,
                    data_dir=host_config.data_dir,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/tenant/home")
    def trusted_tenant_home() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_trusted_tenant_portal_home(
                    _json_payload(),
                    data_dir=host_config.data_dir,
                    public_dir=host_config.public_dir,
                    portal_tenant_id=host_config.tenant_id,
                    tenant_domain=host_config.analytics_domain,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/tenant/operational-status")
    def trusted_tenant_operational_status() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_trusted_tenant_operational_status(
                    _json_payload(),
                    audit_storage_file=host_config.aws_audit_storage_file,
                    portal_tenant_id=host_config.tenant_id,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/tenant/audit-activity")
    def trusted_tenant_audit_activity() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_trusted_tenant_audit_activity(
                    _json_payload(),
                    audit_storage_file=host_config.aws_audit_storage_file,
                    portal_tenant_id=host_config.tenant_id,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/admin/aws/read-only")
    def admin_aws_read_only() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_admin_aws_read_only(
                    _json_payload(),
                    aws_status_file=_required_live_aws_status_file(host_config),
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/admin/aws/narrow-write")
    def admin_aws_narrow_write() -> tuple[Any, int]:
        try:
            return _runtime_response(
                run_admin_aws_narrow_write(
                    _json_payload(),
                    aws_status_file=_required_live_aws_status_file(host_config),
                    audit_storage_file=host_config.aws_audit_storage_file,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/admin/aws/csm-onboarding")
    def admin_aws_csm_onboarding() -> tuple[Any, int]:
        """Trusted-tenant bounded AWS-CSM mailbox onboarding (shell registry entry ``admin.aws.csm_onboarding``)."""
        try:
            return _runtime_response(
                run_admin_aws_csm_onboarding(
                    _json_payload(),
                    aws_status_file=_required_live_aws_status_file(host_config),
                    audit_storage_file=host_config.aws_audit_storage_file,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.post("/portal/api/v2/admin/aws/csm-sandbox/read-only")
    def admin_aws_csm_sandbox_read_only() -> tuple[Any, int]:
        """Internal-audience read-only projection using ``MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE`` only."""
        sandbox_file = _optional_sandbox_live_profile_file(host_config)
        if sandbox_file is None:
            return jsonify(
                {
                    "schema": V2_PORTAL_ERROR_SCHEMA,
                    "ok": False,
                    "error": {
                        "code": "sandbox_status_not_configured",
                        "message": (
                            "Set MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE to a valid "
                            "mycite.service_tool.aws_csm.profile.v1 JSON path (independent of "
                            "MYCITE_V2_AWS_STATUS_FILE used by trusted-tenant AWS routes)."
                        ),
                    },
                }
            ), 503
        try:
            return _runtime_response(
                run_admin_aws_csm_sandbox_read_only(
                    _json_payload(),
                    aws_sandbox_status_file=sandbox_file,
                )
            )
        except ValueError as exc:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "invalid_request", "message": str(exc)}}), 400

    @app.get("/portal/api/v2/data/system/resource-workbench")
    def system_resource_workbench() -> tuple[Any, int]:
        result = FilesystemSystemDatumStoreAdapter(host_config.data_dir).read_system_resource_workbench(
            SystemDatumStoreRequest(tenant_id=host_config.tenant_id)
        )
        return jsonify(result.to_dict()), 200 if result.ok else 503

    @app.get("/__fnd/analytics.js")
    def analytics_script() -> Response:
        script = """
(() => {
  const send = () => {
    const payload = {
      path: window.location.pathname,
      title: document.title,
      referrer: document.referrer || "",
      width: window.innerWidth,
      height: window.innerHeight
    };
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/__fnd/collect", new Blob([body], { type: "application/json" }));
      return;
    }
    fetch("/__fnd/collect", { method: "POST", headers: { "Content-Type": "application/json" }, body });
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", send, { once: true });
  } else {
    send();
  }
})();
""".strip()
        return Response(script + "\n", mimetype="application/javascript")

    @app.post("/__fnd/collect")
    def analytics_collect() -> tuple[Any, int]:
        domain = _request_domain()
        year_month = _as_text(os.environ.get("MYCITE_ANALYTICS_YEAR_MONTH")) or _current_year_month()
        if not domain:
            return jsonify({"schema": V2_PORTAL_ERROR_SCHEMA, "ok": False, "error": {"code": "domain_required", "message": "Analytics domain could not be resolved."}}), 400
        payload = {
            "schema": "mycite.v2.analytics.web_event.v1",
            "received_at_unix_ms": _unix_ms(),
            "domain": domain,
            "request_id": _as_text(request.headers.get("X-Request-Id")),
            "remote_addr": _as_text(request.headers.get("X-Forwarded-For") or request.remote_addr),
            "user_agent": _as_text(request.headers.get("User-Agent")),
            "payload": _analytics_request_payload(),
        }
        resolution = AnalyticsEventPathResolver(host_config.analytics_webapps_root).append_payload(
            domain=domain,
            year_month=year_month,
            payload=payload,
        )
        return jsonify({"schema": "mycite.v2.analytics.collect.receipt.v1", "ok": True, "events_file": str(resolution.events_file), "warnings": list(resolution.warnings)}), 202

    @app.get("/<path:resource_path>")
    def public_resource(resource_path: str) -> Any:
        # Catch-all must not shadow /portal/static/* — Flask's static route loses to this
        # rule in some WSGI setups, which returned 404 for CSS/JS and broke styling.
        if resource_path.startswith("portal/static/"):
            rel = resource_path.removeprefix("portal/static/")
            if not rel or ".." in Path(rel).parts:
                abort(404)
            return send_from_directory(str(_host_dir / "static"), rel)

        if resource_path == "portal" or resource_path.startswith("portal/"):
            abort(404)
        requested = Path(resource_path)
        if requested.is_absolute() or ".." in requested.parts or not resource_path.endswith(".json"):
            abort(404)
        target = host_config.public_dir / requested
        if not target.exists() or not target.is_file():
            abort(404)
        return send_from_directory(host_config.public_dir, resource_path)

    return app
