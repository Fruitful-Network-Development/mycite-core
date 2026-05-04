from __future__ import annotations

import base64
import glob
import json
import os
import time
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_tool_control_panel
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PAYPAL_CSM_TOOL_ACTION_REQUEST_SCHEMA,
    PAYPAL_CSM_TOOL_REQUEST_SCHEMA,
    PAYPAL_CSM_TOOL_SURFACE_SCHEMA,
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    attach_region_family_contract,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
    PAYPAL_CSM_TOOL_ROUTE,
    PAYPAL_CSM_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PORTAL_SHELL_REQUEST_SCHEMA,
    PortalScope,
    PortalShellState,
    normalize_runtime_shell_surface_request_payload,
    normalize_runtime_surface_action_request_payload,
    resolve_portal_tool_registry_entry,
    canonicalize_portal_shell_state,
    build_canonical_url,
    canonical_query_for_surface_query,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_domain_profile(private_dir: str | Path, domain: str) -> dict[str, Any] | None:
    """Scan all paypal-csm.*.json files in the tool dir, match by domain field."""
    tool_dir = Path(private_dir) / "utilities" / "tools" / "paypal-csm"
    pattern = str(tool_dir / "paypal-csm.*.json")
    domain_lower = _as_text(domain).lower()
    for path in sorted(glob.glob(pattern)):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, dict) and _as_text(payload.get("domain")).lower() == domain_lower:
                return payload
        except Exception:
            continue
    return None


def _load_tenant_config(private_dir: str | Path, tenant_ref: str) -> dict[str, Any] | None:
    """Read tenants/{tenant_ref}.json from the paypal-csm tool dir."""
    tenant_path = (
        Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "tenants" / f"{tenant_ref}.json"
    )
    if not tenant_path.exists():
        return None
    try:
        payload = json.loads(tenant_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _load_fnd_config(private_dir: str | Path) -> dict[str, Any]:
    """Read fnd.json from the paypal-csm tool dir."""
    fnd_path = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "fnd.json"
    if not fnd_path.exists():
        return {}
    try:
        payload = json.loads(fnd_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _resolve_credentials(tenant_config: dict[str, Any]) -> tuple[str, str] | None:
    """
    Resolve PayPal credentials from env vars based on credentials_ref in tenant_config.

    For credentials_ref == "1" or "set-locally-in-state-or-runtime":
        uses PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET

    Otherwise uses PAYPAL_CLIENT_ID_{REF.upper()} and PAYPAL_CLIENT_SECRET_{REF.upper()}
    """
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
    """Obtain a PayPal access token via client_credentials grant."""
    import urllib.request
    import urllib.parse

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


def _append_to_ndjson(path: Path, record: dict[str, Any]) -> None:
    """Append a JSON record as a new line to an NDJSON file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        pass


def build_portal_paypal_csm_surface_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    domain_profile: dict[str, Any] | None,
    tenant_config: dict[str, Any] | None,
    fnd_config: dict[str, Any],
    credentials_ready: bool,
    tool_exposure_policy: dict[str, Any] | None = None,
    private_dir: str | Path | None = None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=PAYPAL_CSM_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("PayPal-CSM tool surface is not registered")

    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    domain_profile_present = domain_profile is not None
    missing_capabilities = [
        capability for capability in tool_entry.required_capabilities
        if capability not in portal_scope.capabilities
    ]
    operational = bool(
        configured and enabled and domain_profile_present and credentials_ready and not missing_capabilities
    )

    profile_summary: dict[str, Any] = {}
    if domain_profile:
        profile_summary = {
            "domain": _as_text(domain_profile.get("domain")),
            "environment": _as_text(domain_profile.get("environment")),
            "brand_name": _as_text(domain_profile.get("brand_name")),
            "tenant_ref": _as_text(domain_profile.get("tenant_ref")),
            "configured": bool(domain_profile.get("configured")),
        }

    tenant_summary: dict[str, Any] = {}
    if tenant_config:
        tenant_summary = {
            "environment": _as_text(tenant_config.get("environment")),
            "brand_name": _as_text(tenant_config.get("brand_name", "")),
        }

    surface_payload = {
        "schema": PAYPAL_CSM_TOOL_SURFACE_SCHEMA,
        "kind": "tool_mediation_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
        "entrypoint_id": PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
        "title": "PayPal-CSM",
        "subtitle": "PayPal order mediation and donation profile management.",
        "tool": {
            "tool_id": tool_entry.tool_id,
            "label": tool_entry.label,
            "summary": tool_entry.summary,
            "configured": configured,
            "enabled": enabled,
            "operational": operational,
            "required_capabilities": list(tool_entry.required_capabilities),
            "missing_capabilities": missing_capabilities,
        },
        "domain_profile": profile_summary,
        "tenant_summary": tenant_summary,
        "credentials_ready": credentials_ready,
        "fnd_environment": _as_text(fnd_config.get("environment")),
        "focus_subject": dict(shell_state.focus_subject or {}),
        "mediation_subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
        "request_contract": {
            "schema": PAYPAL_CSM_TOOL_REQUEST_SCHEMA,
            "route": PAYPAL_CSM_TOOL_ROUTE,
            "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
        },
    }

    control_panel = build_tool_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        data_dir=None,
        public_dir=None,
        private_dir=private_dir,
        surface_id=PAYPAL_CSM_TOOL_SURFACE_ID,
        active_document=None,
        selected_datum=None,
        selected_object=None,
        tool_rows=[],
        title="PayPal-CSM",
    )

    workbench = attach_region_family_contract(
        {
            "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
            "kind": "surface_payload",
            "title": "PayPal-CSM Workspace",
            "subtitle": "Domain profile and order status visible when credentials are ready.",
            "visible": domain_profile_present and credentials_ready,
            "surface_payload": {
                "kind": "surface_payload",
                "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
                "domain_profile": profile_summary,
                "tenant_summary": tenant_summary,
                "credentials_ready": credentials_ready,
            },
        },
        family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
        surface_id=PAYPAL_CSM_TOOL_SURFACE_ID,
    )

    inspector_sections = [
        {
            "title": "Domain Profile",
            "rows": [
                {"label": "domain", "value": profile_summary.get("domain", "not loaded")},
                {"label": "environment", "value": profile_summary.get("environment", "—")},
                {"label": "brand_name", "value": profile_summary.get("brand_name", "—")},
                {"label": "tenant_ref", "value": profile_summary.get("tenant_ref", "—")},
                {"label": "configured", "value": "yes" if profile_summary.get("configured") else "no"},
            ],
        },
        {
            "title": "Credentials",
            "rows": [
                {
                    "label": "credentials_ready",
                    "value": "yes" if credentials_ready else "no",
                    "detail": "Resolved from PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET env vars.",
                },
            ],
        },
        {
            "title": "Prerequisites",
            "rows": [
                {
                    "label": "fnd_peripheral_routing",
                    "value": "available" if "fnd_peripheral_routing" in portal_scope.capabilities else "missing",
                    "detail": "FND routing capability is required for order mediation endpoints.",
                },
            ],
        },
    ]

    inspector = attach_region_family_contract(
        {
            "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
            "kind": "summary_panel",
            "title": "PayPal-CSM",
            "summary": "PayPal order mediation and donation profile.",
            "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
            "sections": inspector_sections,
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=PAYPAL_CSM_TOOL_SURFACE_ID,
    )

    return {
        "entrypoint_id": PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": "PayPal-CSM",
        "page_subtitle": "PayPal order mediation and donation profile management.",
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "inspector": inspector,
        "shell_state": shell_state,
        "route": PAYPAL_CSM_TOOL_ROUTE,
    }


def run_portal_paypal_csm(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    portal_instance_id: str | None = None,
    portal_domain: str = "",
) -> dict[str, Any]:
    portal_scope, shell_state, _ = normalize_runtime_shell_surface_request_payload(
        request_payload,
        expected_schema=PAYPAL_CSM_TOOL_REQUEST_SCHEMA,
        surface_id=PAYPAL_CSM_TOOL_SURFACE_ID,
    )
    resolved_portal_instance_id = _as_text(portal_instance_id) or portal_scope.scope_id
    if not portal_scope.scope_id:
        portal_scope = PortalScope(scope_id=resolved_portal_instance_id, capabilities=portal_scope.capabilities)

    domain_profile: dict[str, Any] | None = None
    tenant_config: dict[str, Any] | None = None
    fnd_config: dict[str, Any] = {}
    credentials_ready = False

    if private_dir is not None:
        domain_profile = _load_domain_profile(private_dir, "cuyahogavalleycountrysideconservancy.org")
        if domain_profile:
            tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
            tenant_config = _load_tenant_config(private_dir, tenant_ref)
        fnd_config = _load_fnd_config(private_dir)
        if tenant_config:
            credentials_ready = _resolve_credentials(tenant_config) is not None

    bundle = build_portal_paypal_csm_surface_bundle(
        portal_scope=portal_scope,
        shell_state=shell_state,
        domain_profile=domain_profile,
        tenant_config=tenant_config,
        fnd_config=fnd_config,
        credentials_ready=credentials_ready,
        tool_exposure_policy=tool_exposure_policy,
        private_dir=private_dir,
    )

    canonical_query = canonical_query_for_surface_query(None, surface_id=PAYPAL_CSM_TOOL_SURFACE_ID)
    canonical_url = build_canonical_url(surface_id=PAYPAL_CSM_TOOL_SURFACE_ID, query=canonical_query)

    shell_request = {
        "schema": PORTAL_SHELL_REQUEST_SCHEMA,
        "requested_surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
        "portal_scope": portal_scope.to_dict(),
        "shell_state": shell_state.to_dict(),
    }
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=resolved_portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
    )


def run_portal_paypal_csm_action(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    audit_storage_file: Path | None = None,
) -> dict[str, Any]:
    """Entry point for POST action requests to the PayPal-CSM tool surface."""
    import urllib.request
    import urllib.error

    portal_scope, normalized_payload, surface_query, shell_state_dict, action_kind, action_payload = (
        normalize_runtime_surface_action_request_payload(
            request_payload,
            expected_schema=PAYPAL_CSM_TOOL_ACTION_REQUEST_SCHEMA,
            surface_id=PAYPAL_CSM_TOOL_SURFACE_ID,
        )
    )

    from MyCiteV2.instances._shared.runtime.runtime_platform import build_portal_runtime_error

    def _error_envelope(code: str, message: str) -> dict[str, Any]:
        from MyCiteV2.instances._shared.runtime.runtime_platform import (
            PORTAL_RUNTIME_ENVELOPE_SCHEMA,
            PORTAL_SHELL_STATE_SCHEMA,
        )
        return {
            "schema": PORTAL_RUNTIME_ENVELOPE_SCHEMA,
            "portal_scope": portal_scope.to_dict(),
            "requested_surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "entrypoint_id": PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
            "read_write_posture": "write",
            "reducer_owned": False,
            "canonical_route": PAYPAL_CSM_TOOL_ROUTE,
            "canonical_query": {},
            "canonical_url": PAYPAL_CSM_TOOL_ROUTE,
            "shell_state": {"schema": PORTAL_SHELL_STATE_SCHEMA},
            "surface_payload": {
                "schema": PAYPAL_CSM_TOOL_SURFACE_SCHEMA,
                "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            },
            "shell_composition": {},
            "warnings": [],
            "error": build_portal_runtime_error(code=code, message=message),
        }

    if not action_kind:
        return _error_envelope("missing_action_kind", "action_kind is required")

    if private_dir is None:
        return _error_envelope("no_private_dir", "private_dir is required for PayPal actions")

    # Load state
    request_domain = _as_text(action_payload.get("domain")) or "cuyahogavalleycountrysideconservancy.org"
    domain_profile = _load_domain_profile(private_dir, request_domain)
    if domain_profile is None:
        return _error_envelope("domain_profile_not_found", f"No domain profile found for domain: {request_domain}")

    tenant_ref = _as_text(domain_profile.get("tenant_ref")) or "1"
    tenant_config = _load_tenant_config(private_dir, tenant_ref)
    if tenant_config is None:
        return _error_envelope("tenant_config_not_found", f"Tenant config not found for ref: {tenant_ref}")

    credentials = _resolve_credentials(tenant_config)
    if credentials is None:
        return _error_envelope("credentials_not_set", "PayPal credentials are not set in environment variables")

    client_id, client_secret = credentials
    environment = _as_text(domain_profile.get("environment")) or "sandbox"
    base_url = _paypal_base_url(environment)

    # NDJSON log path
    orders_log = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"

    if action_kind == "refresh_profile":
        return _error_envelope("ok", "") if False else {
            "schema": "mycite.v2.portal.runtime.envelope.v1",
            "portal_scope": portal_scope.to_dict(),
            "requested_surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "entrypoint_id": PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
            "read_write_posture": "write",
            "reducer_owned": False,
            "canonical_route": PAYPAL_CSM_TOOL_ROUTE,
            "canonical_query": {},
            "canonical_url": PAYPAL_CSM_TOOL_ROUTE,
            "shell_state": {"schema": "mycite.v2.portal.shell.state.v1"},
            "surface_payload": {
                "schema": PAYPAL_CSM_TOOL_SURFACE_SCHEMA,
                "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
                "action_result": {
                    "action_kind": "refresh_profile",
                    "domain": request_domain,
                    "environment": environment,
                    "configured": bool(domain_profile.get("configured")),
                },
            },
            "shell_composition": {},
            "warnings": [],
            "error": None,
        }

    if action_kind == "create_order":
        amount = _as_text(action_payload.get("amount"))
        if not amount:
            return _error_envelope("missing_amount", "amount is required for create_order")
        checkout_ctx = domain_profile.get("checkout_context", {})
        donation_defaults = domain_profile.get("donation_defaults", {})
        brand_name = _as_text(domain_profile.get("brand_name"))
        custom_id_prefix = _as_text(donation_defaults.get("custom_id_prefix")) or "donation"
        item_description = _as_text(donation_defaults.get("item_description"))
        return_url = _as_text(checkout_ctx.get("return_url"))
        cancel_url = _as_text(checkout_ctx.get("cancel_url"))
        currency_code = _as_text(checkout_ctx.get("currency_code")) or "USD"
        timestamp_ms = int(time.time() * 1000)
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
            return _error_envelope("paypal_create_order_error", str(exc))

        order_id = _as_text(order_result.get("id"))
        approval_url = ""
        for link in order_result.get("links", []):
            if isinstance(link, dict) and _as_text(link.get("rel")) == "approve":
                approval_url = _as_text(link.get("href"))
                break

        _append_to_ndjson(orders_log, {
            "event": "create_order",
            "order_id": order_id,
            "custom_id": custom_id,
            "domain": request_domain,
            "amount": amount,
            "currency_code": currency_code,
            "status": _as_text(order_result.get("status")),
            "approval_url": approval_url,
            "timestamp_ms": timestamp_ms,
        })

        return {
            "schema": "mycite.v2.portal.runtime.envelope.v1",
            "portal_scope": portal_scope.to_dict(),
            "requested_surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "entrypoint_id": PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
            "read_write_posture": "write",
            "reducer_owned": False,
            "canonical_route": PAYPAL_CSM_TOOL_ROUTE,
            "canonical_query": {},
            "canonical_url": PAYPAL_CSM_TOOL_ROUTE,
            "shell_state": {"schema": "mycite.v2.portal.shell.state.v1"},
            "surface_payload": {
                "schema": PAYPAL_CSM_TOOL_SURFACE_SCHEMA,
                "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
                "action_result": {
                    "action_kind": "create_order",
                    "order_id": order_id,
                    "approval_url": approval_url,
                    "status": _as_text(order_result.get("status")),
                },
            },
            "shell_composition": {},
            "warnings": [],
            "error": None,
        }

    if action_kind == "capture_order":
        order_id = _as_text(action_payload.get("order_id"))
        if not order_id:
            return _error_envelope("missing_order_id", "order_id is required for capture_order")

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
            return _error_envelope("paypal_capture_order_error", str(exc))

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

        _append_to_ndjson(orders_log, {
            "event": "capture_order",
            "order_id": order_id,
            "capture_id": capture_id,
            "domain": request_domain,
            "amount": capture_amount,
            "currency_code": currency_code,
            "status": status,
            "timestamp_ms": int(time.time() * 1000),
        })

        return {
            "schema": "mycite.v2.portal.runtime.envelope.v1",
            "portal_scope": portal_scope.to_dict(),
            "requested_surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
            "entrypoint_id": PAYPAL_CSM_TOOL_ENTRYPOINT_ID,
            "read_write_posture": "write",
            "reducer_owned": False,
            "canonical_route": PAYPAL_CSM_TOOL_ROUTE,
            "canonical_query": {},
            "canonical_url": PAYPAL_CSM_TOOL_ROUTE,
            "shell_state": {"schema": "mycite.v2.portal.shell.state.v1"},
            "surface_payload": {
                "schema": PAYPAL_CSM_TOOL_SURFACE_SCHEMA,
                "surface_id": PAYPAL_CSM_TOOL_SURFACE_ID,
                "action_result": {
                    "action_kind": "capture_order",
                    "order_id": order_id,
                    "capture_id": capture_id,
                    "status": status,
                    "amount": capture_amount,
                    "currency_code": currency_code,
                },
            },
            "shell_composition": {},
            "warnings": [],
            "error": None,
        }

    return _error_envelope("unknown_action_kind", f"Unsupported action_kind: {action_kind}")


__all__ = [
    "build_portal_paypal_csm_surface_bundle",
    "run_portal_paypal_csm",
    "run_portal_paypal_csm_action",
]
