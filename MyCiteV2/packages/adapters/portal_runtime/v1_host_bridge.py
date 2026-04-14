"""Historical V1-to-V2 bridge utilities for the neutral portal shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import (
    run_portal_aws_csm_sandbox,
    run_portal_aws_narrow_write,
    run_portal_aws_read_only,
)
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    build_portal_runtime_entrypoint_catalog,
)
from MyCiteV2.packages.adapters.filesystem import is_live_aws_profile_file
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID,
    AWS_TOOL_ENTRYPOINT_ID,
    PORTAL_SHELL_ENTRYPOINT_ID,
)

V2_BRIDGE_HEALTH_SCHEMA = "mycite.v2.portal.deployment_bridge.health.v1"
V2_BRIDGE_ERROR_SCHEMA = "mycite.v2.portal.deployment_bridge.error.v1"


@dataclass(frozen=True)
class V2BridgeConfig:
    portal_instance_id: str = "fnd"
    portal_domain: str = ""
    portal_audit_storage_file: str | Path | None = None
    aws_status_file: str | Path | None = None
    aws_csm_sandbox_status_file: str | Path | None = None
    aws_audit_storage_file: str | Path | None = None


@dataclass(frozen=True)
class V2BridgeResult:
    payload: dict[str, Any]
    status_code: int


def _safe_error_payload(*, code: str, message: str, status_code: int) -> V2BridgeResult:
    return V2BridgeResult(
        payload={
            "schema": V2_BRIDGE_ERROR_SCHEMA,
            "ok": False,
            "error": {
                "code": str(code or "bridge_error"),
                "message": str(message or "The V2 bridge request could not be completed."),
            },
        },
        status_code=status_code,
    )


def _runtime_result(envelope: dict[str, Any]) -> V2BridgeResult:
    if envelope.get("schema") != PORTAL_RUNTIME_ENVELOPE_SCHEMA:
        return _safe_error_payload(
            code="invalid_runtime_envelope",
            message="The V2 runtime returned an invalid portal envelope.",
            status_code=502,
        )
    error = envelope.get("error")
    if not isinstance(error, dict) or not error:
        return V2BridgeResult(payload=envelope, status_code=200)
    code = str(error.get("code") or "").strip()
    if code == "surface_unknown":
        return V2BridgeResult(payload=envelope, status_code=404)
    return V2BridgeResult(payload=envelope, status_code=400)


def run_v2_bridge_entrypoint(
    *,
    entrypoint_id: str,
    request_payload: dict[str, Any] | None,
    config: V2BridgeConfig | None = None,
) -> V2BridgeResult:
    bridge_config = config or V2BridgeConfig()
    try:
        if entrypoint_id == PORTAL_SHELL_ENTRYPOINT_ID:
            return _runtime_result(
                run_portal_shell_entry(
                    request_payload,
                    portal_instance_id=bridge_config.portal_instance_id,
                    portal_domain=bridge_config.portal_domain,
                    audit_storage_file=bridge_config.portal_audit_storage_file,
                )
            )
        if entrypoint_id == AWS_TOOL_ENTRYPOINT_ID:
            return _runtime_result(
                run_portal_aws_read_only(
                    request_payload,
                    aws_status_file=bridge_config.aws_status_file,
                )
            )
        if entrypoint_id == AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID:
            return _runtime_result(
                run_portal_aws_narrow_write(
                    request_payload,
                    aws_status_file=bridge_config.aws_status_file,
                    audit_storage_file=bridge_config.aws_audit_storage_file,
                )
            )
        if entrypoint_id == AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID:
            return _runtime_result(
                run_portal_aws_csm_sandbox(
                    request_payload,
                    aws_sandbox_status_file=bridge_config.aws_csm_sandbox_status_file,
                )
            )
    except ValueError as exc:
        return _safe_error_payload(code="invalid_request", message=str(exc), status_code=400)

    return _safe_error_payload(
        code="entrypoint_not_cataloged",
        message="Requested V2 runtime entrypoint is not cataloged for the bridge.",
        status_code=404,
    )


def build_v2_bridge_health(config: V2BridgeConfig | None = None) -> dict[str, Any]:
    bridge_config = config or V2BridgeConfig()
    return {
        "schema": V2_BRIDGE_HEALTH_SCHEMA,
        "ok": True,
        "bridge_shape": "shape_b_v1_host_to_v2_runtime",
        "runtime_catalog": [entry.to_dict() for entry in build_portal_runtime_entrypoint_catalog()],
        "configured_inputs": {
            "portal_audit_storage_file": bridge_config.portal_audit_storage_file is not None,
            "aws_status_file": bridge_config.aws_status_file is not None,
            "aws_live_profile_mapping": is_live_aws_profile_file(bridge_config.aws_status_file),
            "aws_audit_storage_file": bridge_config.aws_audit_storage_file is not None,
            "aws_csm_sandbox_status_file": bridge_config.aws_csm_sandbox_status_file is not None,
            "aws_csm_sandbox_live_profile_mapping": is_live_aws_profile_file(
                bridge_config.aws_csm_sandbox_status_file
            ),
        },
    }


def register_v2_bridge_routes(
    app: Any,
    *,
    config_provider: Callable[[], V2BridgeConfig],
) -> None:
    from flask import jsonify, request

    def _json_payload() -> dict[str, Any]:
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}

    def _response(result: V2BridgeResult) -> tuple[Any, int]:
        return jsonify(result.payload), result.status_code

    @app.get("/portal/api/v2/bridge/health")
    def v2_bridge_health() -> tuple[Any, int]:
        return jsonify(build_v2_bridge_health(config_provider())), 200

    @app.post("/portal/api/v2/bridge/shell")
    def v2_bridge_shell() -> tuple[Any, int]:
        return _response(
            run_v2_bridge_entrypoint(
                entrypoint_id=PORTAL_SHELL_ENTRYPOINT_ID,
                request_payload=_json_payload(),
                config=config_provider(),
            )
        )


__all__ = [
    "V2_BRIDGE_ERROR_SCHEMA",
    "V2_BRIDGE_HEALTH_SCHEMA",
    "V2BridgeConfig",
    "V2BridgeResult",
    "build_v2_bridge_health",
    "register_v2_bridge_routes",
    "run_v2_bridge_entrypoint",
]
