from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    AWS_CSM_ONBOARDING_TOOL_REQUEST_SCHEMA,
    AWS_CSM_ONBOARDING_TOOL_SURFACE_SCHEMA,
    AWS_CSM_SANDBOX_TOOL_REQUEST_SCHEMA,
    AWS_CSM_SANDBOX_TOOL_SURFACE_SCHEMA,
    AWS_NARROW_WRITE_TOOL_REQUEST_SCHEMA,
    AWS_NARROW_WRITE_TOOL_SURFACE_SCHEMA,
    AWS_TOOL_REQUEST_SCHEMA,
    AWS_TOOL_SURFACE_SCHEMA,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    build_portal_runtime_envelope,
    build_portal_runtime_error,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.adapters.filesystem import is_live_aws_profile_file
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_ONBOARDING_TOOL_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_TOOL_ROUTE,
    AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
    AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_TOOL_ROUTE,
    AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
    AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_TOOL_ROUTE,
    AWS_NARROW_WRITE_TOOL_SURFACE_ID,
    AWS_TOOL_ENTRYPOINT_ID,
    AWS_TOOL_ROUTE,
    AWS_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    build_portal_activity_dispatch_bodies,
    build_shell_composition_payload,
    build_portal_surface_catalog,
    resolve_portal_tool_registry_entry,
)

AWS_CSM_FAMILY_HEALTH_SCHEMA = "mycite.v2.portal.system.tools.aws.family_health.v1"
AWS_TOOL_STATUS_SCHEMA = "mycite.v2.portal.system.tools.aws.status.v1"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_json_object(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    resolved = Path(path)
    if not resolved.exists() or not resolved.is_file():
        return {}
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_portal_scope(payload: dict[str, Any] | None) -> PortalScope:
    if payload is None:
        return PortalScope()
    if isinstance(payload.get("portal_scope"), dict):
        return PortalScope.from_value(payload.get("portal_scope"))
    return PortalScope()


def _normalize_request(payload: dict[str, Any] | None, *, expected_schema: str) -> tuple[PortalScope, dict[str, Any]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": expected_schema, **normalized_payload}
    schema = _as_text(normalized_payload.get("schema"))
    if schema != expected_schema:
        raise ValueError(f"request.schema must be {expected_schema}")
    return _normalize_portal_scope(normalized_payload), normalized_payload


def _tool_state(
    *,
    tool_id: str,
    required_capabilities: tuple[str, ...],
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    integration_ready: bool,
    integration_name: str,
) -> dict[str, Any]:
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_id)
    missing_capabilities = [cap for cap in required_capabilities if cap not in portal_scope.capabilities]
    missing_integrations = [] if integration_ready else [integration_name]
    operational = bool(configured and enabled and not missing_integrations and not missing_capabilities)
    return {
        "schema": AWS_TOOL_STATUS_SCHEMA,
        "configured": configured,
        "enabled": enabled,
        "operational": operational,
        "missing_integrations": missing_integrations,
        "required_capabilities": list(required_capabilities),
        "missing_capabilities": missing_capabilities,
    }


def cached_aws_csm_family_health(
    *,
    service: object | None = None,
    portal_instance_id: str = "",
    private_dir: str | Path | None = None,
    domains: list[str] | None = None,
    dispatcher_callback_builder: object | None = None,
    inbound_callback_builder: object | None = None,
) -> dict[str, Any]:
    configured_domains = [domain for domain in list(domains or []) if _as_text(domain)]
    policy_snapshot = _load_json_object(None if private_dir is None else Path(private_dir) / "config.json")
    exposure = policy_snapshot.get("tool_exposure") if isinstance(policy_snapshot, dict) else {}
    configured = True
    enabled = True
    if isinstance(exposure, dict):
        raw_entry = exposure.get("aws_csm_onboarding")
        if isinstance(raw_entry, dict):
            configured = raw_entry.get("configured", True) is True
            enabled = raw_entry.get("enabled", configured) is True
        elif isinstance(raw_entry, bool):
            configured = True
            enabled = raw_entry
    return {
        "schema": AWS_CSM_FAMILY_HEALTH_SCHEMA,
        "status": "operational" if configured and enabled else "limited",
        "configured": configured,
        "enabled": enabled,
        "portal_instance_id": _as_text(portal_instance_id),
        "domain_count": len(configured_domains),
        "ready_domain_count": len(configured_domains) if configured and enabled else 0,
        "domains": configured_domains,
        "dispatcher_available": callable(dispatcher_callback_builder),
        "inbound_capture_available": callable(inbound_callback_builder),
    }


def describe_aws_csm_onboarding_guidance(tool_status: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for integration_name in list(tool_status.get("missing_integrations") or []):
        items.append(
            {
                "id": integration_name,
                "label": integration_name.replace("_", " "),
                "status": "missing_integration",
                "detail": "The portal does not currently have the external integration required for this surface.",
            }
        )
    for capability in list(tool_status.get("missing_capabilities") or []):
        items.append(
            {
                "id": capability,
                "label": capability.replace("_", " "),
                "status": "missing_capability",
                "detail": "This portal instance does not advertise the required routing capability.",
            }
        )
    if not items:
        items.append(
            {
                "id": "ready",
                "label": "ready",
                "status": "operational",
                "detail": "The surface is enabled and its prerequisites are satisfied.",
            }
        )
    return {
        "recommended_action": "open_workflow" if tool_status.get("operational") else "configure_dependencies",
        "items": items,
    }


def _profile_summary(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"configured": False, "live_profile_mapping": False, "path": ""}
    resolved = Path(path)
    payload = _load_json_object(resolved)
    return {
        "configured": True,
        "live_profile_mapping": is_live_aws_profile_file(resolved),
        "path": str(resolved),
        "schema": _as_text(payload.get("schema")),
        "profile_name": _as_text(payload.get("profile_name") or payload.get("profile") or payload.get("name")),
        "status": _as_text(payload.get("status") or payload.get("operational_status")),
    }


def _tool_bundle(
    *,
    surface_id: str,
    surface_schema: str,
    entrypoint_id: str,
    request_schema: str,
    route: str,
    title: str,
    subtitle: str,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    integration_ready: bool,
    integration_name: str,
    profile_summary: dict[str, Any],
    guidance_title: str,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=surface_id)
    if tool_entry is None:
        raise ValueError(f"Unknown tool surface: {surface_id}")
    tool_status = _tool_state(
        tool_id=tool_entry.tool_id,
        required_capabilities=tool_entry.required_capabilities,
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        integration_ready=integration_ready,
        integration_name=integration_name,
    )
    guidance = describe_aws_csm_onboarding_guidance(tool_status)
    surface_payload = {
        "schema": surface_schema,
        "kind": "tool_status_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": surface_id,
        "entrypoint_id": entrypoint_id,
        "title": title,
        "subtitle": subtitle,
        "tool": {
            "tool_id": tool_entry.tool_id,
            "label": tool_entry.label,
            "summary": tool_entry.summary,
            **tool_status,
        },
        "profile_summary": profile_summary,
        "guidance": guidance,
        "request_contract": {
            "schema": request_schema,
            "route": route,
            "surface_id": surface_id,
        },
    }
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_status_surface",
        "title": title,
        "subtitle": subtitle,
        "visible": True,
        "surface_payload": surface_payload,
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": title,
        "summary": subtitle,
        "sections": [
            {
                "title": guidance_title,
                "rows": guidance.get("items") or [],
            }
        ],
    }
    return {
        "entrypoint_id": entrypoint_id,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": title,
        "page_subtitle": subtitle,
        "surface_payload": surface_payload,
        "workbench": workbench,
        "inspector": inspector,
    }


def build_portal_aws_surface_bundle(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aws_profile = _profile_summary(aws_status_file)
    sandbox_profile = _profile_summary(aws_csm_sandbox_status_file)
    if surface_id == AWS_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_TOOL_REQUEST_SCHEMA,
            route="/portal/api/v2/system/tools/aws",
            title="AWS-CSM",
            subtitle="Service visibility and integration readiness.",
            portal_scope=portal_scope,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(aws_profile.get("live_profile_mapping")),
            integration_name="aws_status_file",
            profile_summary=aws_profile,
            guidance_title="AWS prerequisites",
        )
    if surface_id == AWS_NARROW_WRITE_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_NARROW_WRITE_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_NARROW_WRITE_TOOL_REQUEST_SCHEMA,
            route="/portal/api/v2/system/tools/aws-narrow-write",
            title="AWS Narrow Write",
            subtitle="Bounded sender selection with shared shell posture.",
            portal_scope=portal_scope,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(aws_profile.get("live_profile_mapping")),
            integration_name="aws_status_file",
            profile_summary=aws_profile,
            guidance_title="Write-path prerequisites",
        )
    if surface_id == AWS_CSM_SANDBOX_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_CSM_SANDBOX_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_CSM_SANDBOX_TOOL_REQUEST_SCHEMA,
            route="/portal/api/v2/system/tools/aws-csm-sandbox",
            title="AWS Sandbox",
            subtitle="Non-production visibility for sandbox projection inputs.",
            portal_scope=portal_scope,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(sandbox_profile.get("live_profile_mapping")),
            integration_name="aws_csm_sandbox_status_file",
            profile_summary=sandbox_profile,
            guidance_title="Sandbox prerequisites",
        )
    if surface_id == AWS_CSM_ONBOARDING_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_CSM_ONBOARDING_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_CSM_ONBOARDING_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_CSM_ONBOARDING_TOOL_REQUEST_SCHEMA,
            route="/portal/api/v2/system/tools/aws-csm-onboarding",
            title="AWS Onboarding",
            subtitle="FND-routed onboarding workflow exposed by capability and configuration.",
            portal_scope=portal_scope,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(aws_profile.get("live_profile_mapping")),
            integration_name="aws_status_file",
            profile_summary=aws_profile,
            guidance_title="Routing prerequisites",
        )
    raise ValueError(f"Unsupported AWS surface: {surface_id}")


def _tool_activity_items(portal_instance_id: str, active_surface_id: str) -> list[dict[str, Any]]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_instance_id=portal_instance_id)
    items: list[dict[str, Any]] = []
    for entry in build_portal_surface_catalog():
        if entry.surface_id not in {
            SYSTEM_ROOT_SURFACE_ID,
            NETWORK_ROOT_SURFACE_ID,
            UTILITIES_ROOT_SURFACE_ID,
            active_surface_id,
        }:
            continue
        items.append(
            {
                "item_id": entry.surface_id,
                "label": entry.label,
                "icon_id": "aws" if entry.surface_id == active_surface_id else entry.root_surface_id.split(".", 1)[0],
                "href": entry.route,
                "active": entry.surface_id == active_surface_id,
                "nav_kind": "surface",
                "nav_behavior": "dispatch",
                "shell_request": dispatch_bodies.get(entry.surface_id),
            }
        )
    return items


def _tool_control_panel(
    *,
    portal_instance_id: str,
    active_surface_id: str,
) -> dict[str, Any]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(portal_instance_id=portal_instance_id)
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "system_control_panel",
        "title": "System Surfaces",
        "sections": [
            {
                "title": "Visible Roots",
                "entries": [
                    {
                        "label": "System",
                        "href": "/portal/system",
                        "active": active_surface_id == SYSTEM_ROOT_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(SYSTEM_ROOT_SURFACE_ID),
                    },
                    {
                        "label": "Network",
                        "href": "/portal/network",
                        "active": active_surface_id == NETWORK_ROOT_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(NETWORK_ROOT_SURFACE_ID),
                    },
                    {
                        "label": "Utilities",
                        "href": "/portal/utilities",
                        "active": active_surface_id == UTILITIES_ROOT_SURFACE_ID,
                        "shell_request": dispatch_bodies.get(UTILITIES_ROOT_SURFACE_ID),
                    },
                ],
            }
        ],
    }


def _bundle_to_envelope(
    *,
    bundle: dict[str, Any],
    portal_scope: PortalScope,
    requested_surface_id: str,
) -> dict[str, Any]:
    composition = build_shell_composition_payload(
        active_surface_id=requested_surface_id,
        portal_instance_id=portal_scope.scope_id,
        page_title=bundle["page_title"],
        page_subtitle=bundle["page_subtitle"],
        activity_items=_tool_activity_items(portal_scope.scope_id, requested_surface_id),
        control_panel=_tool_control_panel(portal_instance_id=portal_scope.scope_id, active_surface_id=requested_surface_id),
        workbench=bundle["workbench"],
        inspector=bundle["inspector"],
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=requested_surface_id,
        surface_id=requested_surface_id,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        shell_state={
            "schema": "mycite.v2.portal.shell.state.v1",
            "requested_surface_id": requested_surface_id,
            "active_surface_id": requested_surface_id,
            "selection_status": "available",
            "allowed": True,
            "reason_code": "",
            "reason_message": "",
        },
        surface_payload=bundle["surface_payload"],
        shell_composition=composition,
        warnings=[],
        error=None,
    )


def run_portal_aws_read_only(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, _ = _normalize_request(request_payload, expected_schema=AWS_TOOL_REQUEST_SCHEMA)
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        aws_status_file=aws_status_file,
        tool_exposure_policy=tool_exposure_policy,
    )
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, requested_surface_id=AWS_TOOL_SURFACE_ID)


def run_portal_aws_csm_family_home(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_portal_aws_read_only(
        request_payload,
        aws_status_file=aws_status_file,
        tool_exposure_policy=tool_exposure_policy,
    )


def run_portal_aws_csm_newsletter(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope = PortalScope()
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        aws_status_file=None,
        tool_exposure_policy=tool_exposure_policy,
    )
    bundle["surface_payload"]["newsletter_state"] = {
        "configured": private_dir is not None,
        "operational": private_dir is not None,
        "private_dir": str(private_dir) if private_dir is not None else "",
    }
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, requested_surface_id=AWS_TOOL_SURFACE_ID)


def run_portal_aws_csm_sandbox(
    request_payload: dict[str, Any] | None,
    *,
    aws_sandbox_status_file: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, _ = _normalize_request(request_payload, expected_schema=AWS_CSM_SANDBOX_TOOL_REQUEST_SCHEMA)
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        aws_status_file=None,
        aws_csm_sandbox_status_file=aws_sandbox_status_file,
        tool_exposure_policy=tool_exposure_policy,
    )
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, requested_surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID)


def run_portal_aws_narrow_write(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    audit_storage_file: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, payload = _normalize_request(request_payload, expected_schema=AWS_NARROW_WRITE_TOOL_REQUEST_SCHEMA)
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        aws_status_file=aws_status_file,
        tool_exposure_policy=tool_exposure_policy,
    )
    bundle["surface_payload"]["last_requested_sender"] = _as_text(payload.get("sender_address"))
    bundle["surface_payload"]["audit_storage_configured"] = audit_storage_file is not None
    return _bundle_to_envelope(
        bundle=bundle,
        portal_scope=portal_scope,
        requested_surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID,
    )


def run_portal_aws_csm_onboarding(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    audit_storage_file: str | Path | None = None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, payload = _normalize_request(request_payload, expected_schema=AWS_CSM_ONBOARDING_TOOL_REQUEST_SCHEMA)
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        aws_status_file=aws_status_file,
        tool_exposure_policy=tool_exposure_policy,
    )
    bundle["surface_payload"]["requested_mailbox"] = _as_text(payload.get("mailbox") or payload.get("target_mailbox"))
    bundle["surface_payload"]["audit_storage_configured"] = audit_storage_file is not None
    bundle["surface_payload"]["private_dir_configured"] = private_dir is not None
    return _bundle_to_envelope(
        bundle=bundle,
        portal_scope=portal_scope,
        requested_surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
    )


__all__ = [
    "AWS_CSM_FAMILY_HEALTH_SCHEMA",
    "AWS_TOOL_STATUS_SCHEMA",
    "PORTAL_RUNTIME_ENVELOPE_SCHEMA",
    "build_portal_aws_surface_bundle",
    "cached_aws_csm_family_health",
    "describe_aws_csm_onboarding_guidance",
    "run_portal_aws_csm_family_home",
    "run_portal_aws_csm_newsletter",
    "run_portal_aws_csm_onboarding",
    "run_portal_aws_csm_sandbox",
    "run_portal_aws_narrow_write",
    "run_portal_aws_read_only",
]
