from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    run_admin_aws_narrow_write,
    run_admin_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.admin_runtime import run_admin_shell_entry
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_RUNTIME_ENVELOPE_SCHEMA,
    build_admin_runtime_entrypoint_catalog,
)
from MyCiteV2.packages.adapters.filesystem import is_live_aws_profile_file
from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
)

V2_ADMIN_BRIDGE_HEALTH_SCHEMA = "mycite.v2.admin.deployment_bridge.health.v1"
V2_ADMIN_BRIDGE_ERROR_SCHEMA = "mycite.v2.admin.deployment_bridge.error.v1"


@dataclass(frozen=True)
class V2AdminBridgeConfig:
    audit_storage_file: str | Path | None = None
    aws_status_file: str | Path | None = None
    aws_audit_storage_file: str | Path | None = None


@dataclass(frozen=True)
class V2AdminBridgeResult:
    payload: dict[str, Any]
    status_code: int


def _safe_error_payload(*, code: str, message: str, status_code: int) -> V2AdminBridgeResult:
    return V2AdminBridgeResult(
        payload={
            "schema": V2_ADMIN_BRIDGE_ERROR_SCHEMA,
            "ok": False,
            "error": {
                "code": str(code or "bridge_error"),
                "message": str(message or "The V2 admin bridge request could not be completed."),
            },
        },
        status_code=status_code,
    )


def _runtime_status_code(envelope: dict[str, Any]) -> int:
    error = envelope.get("error")
    if not isinstance(error, dict) or not error:
        return 200

    code = str(error.get("code") or "").strip()
    if code == "audience_not_allowed":
        return 403
    if code in {"slice_unknown", "status_snapshot_not_found"}:
        return 404
    if code in {"status_source_not_configured", "audit_log_not_configured"}:
        return 503
    return 400


def _runtime_result(envelope: dict[str, Any]) -> V2AdminBridgeResult:
    if envelope.get("schema") != ADMIN_RUNTIME_ENVELOPE_SCHEMA:
        return _safe_error_payload(
            code="invalid_runtime_envelope",
            message="The V2 runtime returned an invalid admin envelope.",
            status_code=502,
        )
    return V2AdminBridgeResult(payload=envelope, status_code=_runtime_status_code(envelope))


def run_v2_admin_bridge_entrypoint(
    *,
    entrypoint_id: str,
    request_payload: dict[str, Any] | None,
    config: V2AdminBridgeConfig | None = None,
) -> V2AdminBridgeResult:
    bridge_config = config or V2AdminBridgeConfig()

    try:
        if entrypoint_id == ADMIN_ENTRYPOINT_ID:
            return _runtime_result(
                run_admin_shell_entry(
                    request_payload,
                    audit_storage_file=bridge_config.audit_storage_file,
                )
            )
        if entrypoint_id == AWS_READ_ONLY_ENTRYPOINT_ID:
            return _runtime_result(
                run_admin_aws_read_only(
                    request_payload,
                    aws_status_file=bridge_config.aws_status_file,
                )
            )
        if entrypoint_id == AWS_NARROW_WRITE_ENTRYPOINT_ID:
            return _runtime_result(
                run_admin_aws_narrow_write(
                    request_payload,
                    aws_status_file=bridge_config.aws_status_file,
                    audit_storage_file=bridge_config.aws_audit_storage_file,
                )
            )
    except ValueError as exc:
        return _safe_error_payload(code="invalid_request", message=str(exc), status_code=400)

    return _safe_error_payload(
        code="entrypoint_not_cataloged",
        message="Requested V2 admin runtime entrypoint is not cataloged for the bridge.",
        status_code=404,
    )


def build_v2_admin_bridge_health(config: V2AdminBridgeConfig | None = None) -> dict[str, Any]:
    bridge_config = config or V2AdminBridgeConfig()
    return {
        "schema": V2_ADMIN_BRIDGE_HEALTH_SCHEMA,
        "ok": True,
        "bridge_shape": "shape_b_v1_host_to_v2_runtime",
        "runtime_catalog": [entry.to_dict() for entry in build_admin_runtime_entrypoint_catalog()],
        "configured_inputs": {
            "audit_storage_file": bridge_config.audit_storage_file is not None,
            "aws_status_file": bridge_config.aws_status_file is not None,
            "aws_live_profile_mapping": is_live_aws_profile_file(bridge_config.aws_status_file),
            "aws_audit_storage_file": bridge_config.aws_audit_storage_file is not None,
        },
    }


def register_v2_admin_bridge_routes(
    app: Any,
    *,
    config_provider: Callable[[], V2AdminBridgeConfig],
) -> None:
    from flask import jsonify, request

    def _json_payload() -> dict[str, Any]:
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}

    def _response(result: V2AdminBridgeResult) -> tuple[Any, int]:
        return jsonify(result.payload), result.status_code

    @app.get("/portal/api/v2/admin/bridge/health")
    def v2_admin_bridge_health() -> tuple[Any, int]:
        return jsonify(build_v2_admin_bridge_health(config_provider())), 200

    @app.post("/portal/api/v2/admin/shell")
    def v2_admin_bridge_shell_entry() -> tuple[Any, int]:
        return _response(
            run_v2_admin_bridge_entrypoint(
                entrypoint_id=ADMIN_ENTRYPOINT_ID,
                request_payload=_json_payload(),
                config=config_provider(),
            )
        )

    @app.post("/portal/api/v2/admin/aws/read-only")
    def v2_admin_bridge_aws_read_only() -> tuple[Any, int]:
        return _response(
            run_v2_admin_bridge_entrypoint(
                entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
                request_payload=_json_payload(),
                config=config_provider(),
            )
        )

    @app.post("/portal/api/v2/admin/aws/narrow-write")
    def v2_admin_bridge_aws_narrow_write() -> tuple[Any, int]:
        return _response(
            run_v2_admin_bridge_entrypoint(
                entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
                request_payload=_json_payload(),
                config=config_provider(),
            )
        )


__all__ = [
    "V2_ADMIN_BRIDGE_ERROR_SCHEMA",
    "V2_ADMIN_BRIDGE_HEALTH_SCHEMA",
    "V2AdminBridgeConfig",
    "V2AdminBridgeResult",
    "build_v2_admin_bridge_health",
    "register_v2_admin_bridge_routes",
    "run_v2_admin_bridge_entrypoint",
]
