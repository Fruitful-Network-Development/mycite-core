from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_tool_control_panel
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    AWS_CSM_ONBOARDING_TOOL_REQUEST_SCHEMA,
    AWS_CSM_ONBOARDING_TOOL_SURFACE_SCHEMA,
    AWS_CSM_SANDBOX_TOOL_REQUEST_SCHEMA,
    AWS_CSM_SANDBOX_TOOL_SURFACE_SCHEMA,
    AWS_NARROW_WRITE_TOOL_REQUEST_SCHEMA,
    AWS_NARROW_WRITE_TOOL_SURFACE_SCHEMA,
    AWS_TOOL_REQUEST_SCHEMA,
    AWS_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
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
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PortalScope,
    PortalShellState,
    build_canonical_url,
    canonical_query_for_shell_state,
    canonicalize_portal_shell_state,
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


def _normalize_request(
    payload: dict[str, Any] | None,
    *,
    expected_schema: str,
    surface_id: str,
) -> tuple[PortalScope, PortalShellState, dict[str, Any]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    if normalized_payload.get("schema") in {None, ""}:
        normalized_payload = {"schema": expected_schema, **normalized_payload}
    schema = _as_text(normalized_payload.get("schema"))
    if schema != expected_schema:
        raise ValueError(f"request.schema must be {expected_schema}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    shell_state = canonicalize_portal_shell_state(
        normalized_payload.get("shell_state"),
        active_surface_id=surface_id,
        portal_scope=portal_scope,
        seed_anchor_file=normalized_payload.get("shell_state") is None,
    )
    return portal_scope, shell_state, normalized_payload


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
    shell_state: PortalShellState,
    tool_exposure_policy: dict[str, Any] | None,
    integration_ready: bool,
    integration_name: str,
    profile_summary: dict[str, Any],
    guidance_title: str,
    requested_payload: dict[str, Any],
    tool_rows: list[dict[str, Any]],
    data_dir: str | Path | None = None,
    private_dir: str | Path | None = None,
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
        "kind": "tool_mediation_surface",
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
        "focus_subject": dict(shell_state.focus_subject or {}),
        "mediation_subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "request_contract": {
            "schema": request_schema,
            "route": route,
            "surface_id": surface_id,
        },
    }
    if _as_text(requested_payload.get("sender_address")):
        surface_payload["last_requested_sender"] = _as_text(requested_payload.get("sender_address"))
    if _as_text(requested_payload.get("mailbox") or requested_payload.get("target_mailbox")):
        surface_payload["requested_mailbox"] = _as_text(
            requested_payload.get("mailbox") or requested_payload.get("target_mailbox")
        )
    control_panel = build_tool_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=data_dir,
        public_dir=None,
        private_dir=private_dir,
        surface_id=surface_id,
        active_document=None,
        selected_datum=None,
        selected_object=None,
        tool_rows=tool_rows,
        title=title,
    )
    workbench = {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "tool_secondary_evidence",
        "title": f"{title} Evidence",
        "subtitle": "Workbench stays hidden until the tool asks for supporting evidence.",
        "visible": False,
        "surface_payload": {
            "kind": "tool_secondary_evidence",
            "surface_id": surface_id,
            "tool_status": tool_status,
        },
    }
    inspector = {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "tool_mediation_panel",
        "title": title,
        "summary": subtitle,
        "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "sections": [
            {
                "title": "Tool posture",
                "rows": [
                    {"label": "configured", "value": "yes" if tool_status["configured"] else "no"},
                    {"label": "enabled", "value": "yes" if tool_status["enabled"] else "no"},
                    {"label": "operational", "value": "yes" if tool_status["operational"] else "no"},
                ],
            },
            {
                "title": guidance_title,
                "rows": [
                    {
                        "label": item["label"],
                        "value": item["status"],
                        "detail": item["detail"],
                    }
                    for item in guidance.get("items") or []
                ],
            },
            {
                "title": "Mediation subject",
                "rows": [
                    {
                        "label": "focus",
                        "value": _as_text((shell_state.focus_subject or {}).get("id")) or portal_scope.scope_id,
                    },
                    {
                        "label": "subject",
                        "value": _as_text((shell_state.mediation_subject or shell_state.focus_subject or {}).get("id"))
                        or portal_scope.scope_id,
                    },
                ],
            },
        ],
    }
    return {
        "entrypoint_id": entrypoint_id,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": title,
        "page_subtitle": subtitle,
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "shell_state": shell_state,
        "tool_rows": tool_rows,
        "route": route,
    }


def build_portal_aws_surface_bundle(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    aws_status_file: str | Path | None,
    aws_csm_sandbox_status_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    tool_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    aws_profile = _profile_summary(aws_status_file)
    sandbox_profile = _profile_summary(aws_csm_sandbox_status_file)
    rows = list(tool_rows or [])
    if surface_id == AWS_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_TOOL_REQUEST_SCHEMA,
            route=AWS_TOOL_ROUTE,
            title="AWS-CSM",
            subtitle="Service visibility and integration readiness.",
            portal_scope=portal_scope,
            shell_state=shell_state,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(aws_profile.get("live_profile_mapping")),
            integration_name="aws_status_file",
            profile_summary=aws_profile,
            guidance_title="AWS prerequisites",
            requested_payload={},
            tool_rows=rows,
            data_dir=data_dir,
            private_dir=private_dir,
        )
    if surface_id == AWS_NARROW_WRITE_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_NARROW_WRITE_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_NARROW_WRITE_TOOL_REQUEST_SCHEMA,
            route=AWS_NARROW_WRITE_TOOL_ROUTE,
            title="AWS Narrow Write",
            subtitle="Bounded sender selection with interface-led mediation posture.",
            portal_scope=portal_scope,
            shell_state=shell_state,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(aws_profile.get("live_profile_mapping")),
            integration_name="aws_status_file",
            profile_summary=aws_profile,
            guidance_title="Write-path prerequisites",
            requested_payload={},
            tool_rows=rows,
            data_dir=data_dir,
            private_dir=private_dir,
        )
    if surface_id == AWS_CSM_SANDBOX_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_CSM_SANDBOX_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_CSM_SANDBOX_TOOL_REQUEST_SCHEMA,
            route=AWS_CSM_SANDBOX_TOOL_ROUTE,
            title="AWS Sandbox",
            subtitle="Non-production visibility for sandbox projection inputs.",
            portal_scope=portal_scope,
            shell_state=shell_state,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(sandbox_profile.get("live_profile_mapping")),
            integration_name="aws_csm_sandbox_status_file",
            profile_summary=sandbox_profile,
            guidance_title="Sandbox prerequisites",
            requested_payload={},
            tool_rows=rows,
            data_dir=data_dir,
            private_dir=private_dir,
        )
    if surface_id == AWS_CSM_ONBOARDING_TOOL_SURFACE_ID:
        return _tool_bundle(
            surface_id=surface_id,
            surface_schema=AWS_CSM_ONBOARDING_TOOL_SURFACE_SCHEMA,
            entrypoint_id=AWS_CSM_ONBOARDING_TOOL_ENTRYPOINT_ID,
            request_schema=AWS_CSM_ONBOARDING_TOOL_REQUEST_SCHEMA,
            route=AWS_CSM_ONBOARDING_TOOL_ROUTE,
            title="AWS Onboarding",
            subtitle="FND-routed onboarding workflow exposed by capability and configuration.",
            portal_scope=portal_scope,
            shell_state=shell_state,
            tool_exposure_policy=tool_exposure_policy,
            integration_ready=bool(aws_profile.get("live_profile_mapping")),
            integration_name="aws_status_file",
            profile_summary=aws_profile,
            guidance_title="Routing prerequisites",
            requested_payload={},
            tool_rows=rows,
            data_dir=data_dir,
            private_dir=private_dir,
        )
    raise ValueError(f"Unsupported AWS surface: {surface_id}")


def _bundle_to_envelope(
    *,
    bundle: dict[str, Any],
    portal_scope: PortalScope,
    surface_id: str,
) -> dict[str, Any]:
    shell_state = bundle["shell_state"]
    canonical_query = canonical_query_for_shell_state(shell_state, surface_id=surface_id)
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=surface_id,
        surface_id=surface_id,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=True,
        canonical_route=bundle["route"],
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=surface_id, query=canonical_query),
        shell_state=shell_state.to_dict(),
        surface_payload=bundle["surface_payload"],
        shell_composition={},
        warnings=[],
        error=None,
    )


def run_portal_aws_read_only(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, _ = _normalize_request(
        request_payload,
        expected_schema=AWS_TOOL_REQUEST_SCHEMA,
        surface_id=AWS_TOOL_SURFACE_ID,
    )
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        aws_status_file=aws_status_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, surface_id=AWS_TOOL_SURFACE_ID)


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
    shell_state = canonicalize_portal_shell_state(
        None,
        active_surface_id=AWS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        seed_anchor_file=True,
    )
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        aws_status_file=None,
        tool_exposure_policy=tool_exposure_policy,
    )
    bundle["surface_payload"]["newsletter_state"] = {
        "configured": private_dir is not None,
        "operational": private_dir is not None,
        "private_dir": str(private_dir) if private_dir is not None else "",
    }
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, surface_id=AWS_TOOL_SURFACE_ID)


def run_portal_aws_csm_sandbox(
    request_payload: dict[str, Any] | None,
    *,
    aws_sandbox_status_file: str | Path | None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, _ = _normalize_request(
        request_payload,
        expected_schema=AWS_CSM_SANDBOX_TOOL_REQUEST_SCHEMA,
        surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
    )
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        aws_status_file=None,
        aws_csm_sandbox_status_file=aws_sandbox_status_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID)


def run_portal_aws_narrow_write(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    audit_storage_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, payload = _normalize_request(
        request_payload,
        expected_schema=AWS_NARROW_WRITE_TOOL_REQUEST_SCHEMA,
        surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID,
    )
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        aws_status_file=aws_status_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    bundle["surface_payload"]["last_requested_sender"] = _as_text(payload.get("sender_address"))
    bundle["surface_payload"]["audit_storage_configured"] = audit_storage_file is not None
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID)


def run_portal_aws_csm_onboarding(
    request_payload: dict[str, Any] | None,
    *,
    aws_status_file: str | Path | None,
    audit_storage_file: str | Path | None = None,
    private_dir: str | Path | None = None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, shell_state, payload = _normalize_request(
        request_payload,
        expected_schema=AWS_CSM_ONBOARDING_TOOL_REQUEST_SCHEMA,
        surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
    )
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        aws_status_file=aws_status_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    bundle["surface_payload"]["requested_mailbox"] = _as_text(payload.get("mailbox") or payload.get("target_mailbox"))
    bundle["surface_payload"]["audit_storage_configured"] = audit_storage_file is not None
    bundle["surface_payload"]["private_dir_configured"] = private_dir is not None
    return _bundle_to_envelope(bundle=bundle, portal_scope=portal_scope, surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID)


__all__ = [
    "AWS_CSM_FAMILY_HEALTH_SCHEMA",
    "AWS_TOOL_STATUS_SCHEMA",
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
