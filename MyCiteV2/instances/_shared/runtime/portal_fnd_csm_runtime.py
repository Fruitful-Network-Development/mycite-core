"""FND-CSM: Fruitful Network Development — Dispensed Service Management tool runtime.

Provides grantee-aware service management across four tabs:
  Email      — domain mailbox and IAM role status (from AWS-CSM profiles)
  Analytics  — page-view and event aggregates from the webapps analytics folder
  Newsletter — contact list editing and newsletter sender assignment
  PayPal     — webhook configuration and recent donation orders

Grantee profiles are the sole source of domain/user truth:
  {private_dir}/utilities/tools/fnd-csm/grantee.{fnd_msn}.{grantee_msn}.json
  Schema: mycite.v2.grantee.profile.v1
  Fields: msn_id, label, short_name, domains[], users[]
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_unified_control_panel
from MyCiteV2.instances._shared.runtime.portal_workbench import build_datum_file_workbench
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    attach_region_family_contract,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_CSM_TOOL_ENTRYPOINT_ID,
    FND_CSM_TOOL_ROUTE,
    FND_CSM_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
    PORTAL_SHELL_REQUEST_SCHEMA,
    PortalScope,
    PortalShellState,
    resolve_portal_tool_registry_entry,
)
from MyCiteV2.packages.adapters.filesystem import FilesystemAwsCsmToolProfileStore
from MyCiteV2.packages.core.grantee import (
    GRANTEE_PROFILE_SCHEMA,
    load_grantee_profile,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_templates import (
    TemplateRegistry,
    recognize_archetype_in_registry,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.packages.state_machine.nimm.mediate_handlers import (
    build_characteristic_set_component_frame,
    build_component_group_frame,
    build_listing_component_frame,
)

FND_CSM_TOOL_SURFACE_SCHEMA = "mycite.v2.portal.system.tools.fnd_csm.surface.v1"
FND_CSM_TOOL_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.fnd_csm.request.v1"
FND_CSM_TOOL_ACTION_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.fnd_csm.action.request.v1"
GRANTEE_PROFILE_SCHEMA = "mycite.v2.grantee.profile.v1"

# Phase 12g (full split): helpers + builders moved under utilities_extensions/.
# Imported back here for the legacy build_portal_fnd_csm_surface_bundle path
# (FND-CSM preservation invariant). New callers should target the per-extension
# files directly.
from MyCiteV2.instances._shared.runtime.utilities_extensions import (  # noqa: E402
    _build_analytics_extension_payload,
    _build_email_extension_payload,
    _build_newsletter_extension_payload,
    _build_paypal_extension_payload,
    _hydrate_paypal_from_sidecar,
)
from MyCiteV2.instances._shared.runtime.utilities_extensions._shared import (  # noqa: E402
    _as_dict,
    _as_list,
    _as_text,
    _grantee_edit_link,
    _mask_secret,
)


def _load_grantee_profiles(private_dir: str | Path | None) -> list[dict[str, Any]]:
    """Glob and parse all grantee profile JSON files from the fnd-csm tool directory.

    Phase 8 (grantee_profile_contract.md): delegates parsing + validation to
    `load_grantee_profile`. When a grantee JSON lacks the inline `paypal`
    sub-config and a legacy sidecar file exists, hydrates the in-memory
    profile from the sidecar so the Utilities extensions see the webhook URL.
    The on-disk grantee JSON is never written back here; the migration is
    one-shot once an operator edits the profile through the Phase 9 form.

    Returns dicts (not GranteeProfile instances) so the existing call sites
    in this runtime (which read `grantee.get("domains")`, etc.) keep working
    unchanged. Sub-configs surface as nested dicts when present.
    """
    if private_dir is None:
        return []
    base = Path(private_dir)
    pattern = str(base / "utilities" / "tools" / "fnd-csm" / "grantee.*.json")
    profiles: list[dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        try:
            profile = load_grantee_profile(path)
        except (FileNotFoundError, ValueError):
            continue
        if profile.paypal is None:
            sidecar_paypal = _hydrate_paypal_from_sidecar(base, profile.msn_id)
            if sidecar_paypal is not None:
                profile = profile.with_paypal(sidecar_paypal)
        profiles.append(profile.to_dict())
    return sorted(profiles, key=lambda p: _as_text(p.get("label")).lower())


def _resolve_selected_grantee(
    grantees: list[dict[str, Any]],
    tool_state: dict[str, Any],
) -> dict[str, Any]:
    selected_msn = _as_text(tool_state.get("selected_grantee_msn"))
    if selected_msn:
        for g in grantees:
            if _as_text(g.get("msn_id")) == selected_msn:
                return g
    return grantees[0] if grantees else {}


def _resolve_selected_domain(
    grantee: dict[str, Any],
    tool_state: dict[str, Any],
) -> str:
    domains = _as_list(grantee.get("domains"))
    selected = _as_text(tool_state.get("selected_domain"))
    if selected and selected in domains:
        return selected
    return domains[0] if domains else ""



# ---------------------------------------------------------------------------
# Tool state normalization
# ---------------------------------------------------------------------------

def _normalize_fnd_csm_tool_state(request_payload: dict[str, Any]) -> dict[str, Any]:
    tool_state = _as_dict(request_payload.get("tool_state"))
    return {
        "selected_grantee_msn": _as_text(tool_state.get("selected_grantee_msn")),
        "selected_domain": _as_text(tool_state.get("selected_domain")),
        "active_tab": _as_text(tool_state.get("active_tab")) or "email",
        "engaged_frame_id": _as_text(tool_state.get("engaged_frame_id")),
    }


# ---------------------------------------------------------------------------
# Action handler
# ---------------------------------------------------------------------------

def _apply_fnd_csm_action(
    *,
    action_kind: str,
    action_payload: dict[str, Any],
    tool_state: dict[str, Any],
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (next_tool_state, action_result)."""
    next_state = dict(tool_state)
    result: dict[str, Any] = {"action_kind": action_kind, "status": "accepted", "message": ""}

    if action_kind == "select_grantee":
        msn = _as_text(action_payload.get("msn_id"))
        next_state["selected_grantee_msn"] = msn
        next_state["selected_domain"] = ""
        result["message"] = f"Grantee selected: {msn}"

    elif action_kind == "select_domain":
        domain = _as_text(action_payload.get("domain")).lower()
        next_state["selected_domain"] = domain
        result["message"] = f"Domain selected: {domain}"

    elif action_kind == "select_tab":
        tab = _as_text(action_payload.get("tab_id"))
        next_state["active_tab"] = tab
        result["message"] = f"Tab selected: {tab}"

    elif action_kind == "engage_component_frame":
        frame_id = _as_text(action_payload.get("frame_id"))
        if frame_id:
            next_state["engaged_frame_id"] = frame_id
            result["message"] = f"Frame {frame_id} queued for re-render"
        else:
            result["status"] = "rejected"
            result["message"] = "frame_id is required"

    elif action_kind == "assign_newsletter_sender":
        domain = _as_text(action_payload.get("domain")).lower()
        sender = _as_text(action_payload.get("sender_address")).lower()
        if not domain or not sender:
            result["status"] = "rejected"
            result["message"] = "domain and sender_address are required"
        elif private_dir is None:
            result["status"] = "rejected"
            result["message"] = "private_dir is not configured"
        else:
            try:
                from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                    run_datum_workbench_mutation_action,
                )

                mutation_result = run_datum_workbench_mutation_action(
                    "apply",
                    {
                        "target_authority": "aws_csm_newsletter_profile",
                        "operation": "assign_sender",
                        "domain": domain,
                        "sender_address": sender,
                        "private_dir": str(private_dir),
                    },
                    authority_db_file=authority_db_file,
                    portal_instance_id=portal_instance_id or "fnd",
                )
                if not mutation_result.get("ok"):
                    err = mutation_result.get("error") or {}
                    result["status"] = "error"
                    result["message"] = _as_text(err.get("message") or "assign_sender_failed")
                else:
                    result["message"] = f"Newsletter sender for {domain} set to {sender}"
                    result["nimm_envelope"] = mutation_result.get("nimm_envelope")
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)

    elif action_kind == "update_contact_subscription":
        domain = _as_text(action_payload.get("domain")).lower()
        email = _as_text(action_payload.get("email")).lower()
        subscribed = bool(action_payload.get("subscribed"))
        if not domain or not email:
            result["status"] = "rejected"
            result["message"] = "domain and email are required"
        elif authority_db_file is None:
            result["status"] = "rejected"
            result["message"] = "authority_db_file is required for contact_log mutations"
        else:
            try:
                from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                    run_datum_workbench_mutation_action,
                )

                mutation_result = run_datum_workbench_mutation_action(
                    "apply",
                    {
                        "target_authority": "aws_csm_newsletter_contact_log",
                        "operation": "update_subscription",
                        "domain": domain,
                        "email": email,
                        "subscribed": subscribed,
                    },
                    authority_db_file=authority_db_file,
                    portal_instance_id=portal_instance_id or "fnd",
                )
                preview = mutation_result.get("preview") or {}
                if not mutation_result.get("ok"):
                    err = mutation_result.get("error") or {}
                    result["status"] = "error"
                    result["message"] = _as_text(err.get("message") or "update_subscription_failed")
                elif preview.get("matched"):
                    status_word = "subscribed" if subscribed else "unsubscribed"
                    result["message"] = f"{email} {status_word}"
                    result["nimm_envelope"] = mutation_result.get("nimm_envelope")
                else:
                    result["status"] = "rejected"
                    result["message"] = f"Contact not found: {email}"
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)

    elif action_kind == "refresh_inbound_status":
        # Re-sync the ses-forwarder FORWARD_TO_MAP_JSON env + per-domain
        # receipt-rule wiring from current operator-profile state. The
        # service-layer hook in
        # MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/service.py
        # also calls the same adapter method on every inbound-touching
        # onboarding action; this passthrough lets operators trigger a
        # one-shot reconciliation directly from the FND-CSM Email tab
        # without needing the service to be wired into the runtime yet.
        if private_dir is None:
            result["status"] = "rejected"
            result["message"] = "private_dir is not configured"
        else:
            try:
                from MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud import (
                    AwsEc2RoleOnboardingCloudAdapter,
                )
                from MyCiteV2.packages.adapters.filesystem.aws_csm_tool_profile_store import (
                    FilesystemAwsCsmToolProfileStore,
                )

                tool_root = Path(private_dir) / "utilities" / "tools" / "aws-csm"
                store = FilesystemAwsCsmToolProfileStore(tool_root)
                adapter = AwsEc2RoleOnboardingCloudAdapter()
                profiles = store.list_profiles(tenant_scope_id=None)
                forwarding_sync = adapter.sync_operator_forwarding_routes(
                    profiles=list(profiles or []),
                )
                result["forwarding_sync"] = forwarding_sync
                result["message"] = (
                    f"FORWARD_TO_MAP_JSON synced: "
                    f"{forwarding_sync.get('route_count', 0)} routes, "
                    f"route_changed={forwarding_sync.get('route_changed', False)}, "
                    f"domains_wired={forwarding_sync.get('domains_wired') or []}"
                )
            except Exception as exc:
                result["status"] = "error"
                result["message"] = f"forwarding sync failed: {exc}"

    elif action_kind == "save_paypal_webhook":
        msn_id = _as_text(action_payload.get("msn_id"))
        webhook_url = _as_text(action_payload.get("webhook_url"))
        if not msn_id:
            result["status"] = "rejected"
            result["message"] = "msn_id is required"
        elif authority_db_file is None:
            result["status"] = "rejected"
            result["message"] = "authority_db_file is required for paypal_webhook mutations"
        else:
            try:
                from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
                    run_datum_workbench_mutation_action,
                )

                mutation_result = run_datum_workbench_mutation_action(
                    "apply",
                    {
                        "target_authority": "paypal_webhook",
                        "operation": "save_webhook",
                        "grantee_msn_id": msn_id,
                        "webhook_url": webhook_url,
                    },
                    authority_db_file=authority_db_file,
                    portal_instance_id=portal_instance_id or "fnd",
                )
                if not mutation_result.get("ok"):
                    err = mutation_result.get("error") or {}
                    result["status"] = "error"
                    result["message"] = _as_text(err.get("message") or "save_webhook_failed")
                else:
                    result["message"] = "PayPal webhook URL saved"
                    result["nimm_envelope"] = mutation_result.get("nimm_envelope")
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)

    else:
        result["status"] = "rejected"
        result["message"] = f"Unknown action: {action_kind}"

    return next_state, result


# ---------------------------------------------------------------------------
# Interface panel frame builders
# ---------------------------------------------------------------------------

def _fnd_csm_render_key(
    grantee_msn: str,
    domain: str,
    frame_id: str,
    engaged_frame_id: str,
) -> str:
    base = f"{grantee_msn}::{domain}::{frame_id}"
    if engaged_frame_id and engaged_frame_id == frame_id:
        return f"{base}::engaged"
    return base


def _build_email_component_group(
    email_tab: dict[str, Any],
    grantee_msn: str,
    domain: str,
    engaged_frame_id: str,
) -> dict[str, Any]:
    rk = lambda fid: _fnd_csm_render_key(grantee_msn, domain, fid, engaged_frame_id)
    profiles = _as_list(email_tab.get("profiles"))
    mailbox_items = (
        [
            {
                "label": _as_text(p.get("send_as")) or _as_text(p.get("mailbox")) or "—",
                "value": _as_text(p.get("role")) or "—",
                "detail": _as_text(p.get("lifecycle")) or "—",
            }
            for p in profiles
        ]
        if profiles
        else [{"label": "status", "value": "No profiles found for domain"}]
    )
    domain_record = _as_dict(email_tab.get("domain_record"))
    domain_items = [
        {"label": k, "value": _as_text(v)}
        for k, v in domain_record.items()
        if isinstance(v, (str, int, float, bool))
    ]
    children: list[dict[str, Any]] = [
        build_characteristic_set_component_frame(
            frame_id="fnd_csm.email.mailboxes",
            label="Mailboxes",
            items=mailbox_items,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.email.mailboxes"),
            target_authority="fnd_csm",
        ),
    ]
    if domain_items:
        children.append(
            build_characteristic_set_component_frame(
                frame_id="fnd_csm.email.domain_status",
                label="Domain Status",
                items=domain_items,
                attention_node_id=grantee_msn or "fnd_csm",
                lens_key=rk("fnd_csm.email.domain_status"),
                target_authority="fnd_csm",
            )
        )
    return build_component_group_frame(
        frame_id="fnd_csm.tab.email",
        label="Email",
        children=children,
        attention_node_id=grantee_msn or "fnd_csm",
        lens_key=rk("fnd_csm.tab.email"),
        initializer_intent="resolve_email_profile",
        target_authority="fnd_csm",
    )


def _build_analytics_component_group(
    analytics_tab: dict[str, Any],
    grantee_msn: str,
    domain: str,
    engaged_frame_id: str,
) -> dict[str, Any]:
    rk = lambda fid: _fnd_csm_render_key(grantee_msn, domain, fid, engaged_frame_id)
    summary = _as_dict(analytics_tab.get("summary"))
    summary_items = [
        {"label": "page views", "value": str(summary.get("page_view", 0))},
        {"label": "form submits", "value": str(summary.get("form_submit", 0))},
        {"label": "ops probes", "value": str(summary.get("ops_probe", 0))},
        {"label": "other", "value": str(summary.get("other", 0))},
    ]
    recent = _as_list(analytics_tab.get("recent_events"))
    event_rows = [
        {
            "event_type": _as_text(e.get("event_type")),
            "path": _as_text(e.get("path")) or "—",
            "timestamp": _as_text(e.get("timestamp")),
        }
        for e in recent[:20]
    ]
    children: list[dict[str, Any]] = [
        build_characteristic_set_component_frame(
            frame_id="fnd_csm.analytics.summary",
            label="Event Summary",
            items=summary_items,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.analytics.summary"),
            target_authority="fnd_csm",
        ),
        build_listing_component_frame(
            frame_id="fnd_csm.analytics.events",
            label="Recent Events",
            columns=[
                {"key": "event_type", "label": "Type"},
                {"key": "path", "label": "Path"},
                {"key": "timestamp", "label": "Time"},
            ],
            rows=event_rows,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.analytics.events"),
            empty_message="No events recorded.",
            initializer_intent="resolve_analytics_summary",
            target_authority="fnd_csm",
        ),
    ]
    return build_component_group_frame(
        frame_id="fnd_csm.tab.analytics",
        label="Analytics",
        children=children,
        attention_node_id=grantee_msn or "fnd_csm",
        lens_key=rk("fnd_csm.tab.analytics"),
        initializer_intent="resolve_analytics_summary",
        target_authority="fnd_csm",
    )


def _build_newsletter_component_group(
    newsletter_tab: dict[str, Any],
    grantee_msn: str,
    domain: str,
    engaged_frame_id: str,
) -> dict[str, Any]:
    rk = lambda fid: _fnd_csm_render_key(grantee_msn, domain, fid, engaged_frame_id)
    sender_items = [
        {
            "label": "current sender",
            "value": _as_text(newsletter_tab.get("current_sender")) or "— not assigned —",
        },
        {"label": "subscribed", "value": str(newsletter_tab.get("subscribed_count", 0))},
        {"label": "unsubscribed", "value": str(newsletter_tab.get("unsubscribed_count", 0))},
    ]
    contact_rows = [
        {
            "email": _as_text(c.get("email")),
            "subscribed": "yes" if c.get("subscribed") else "no",
            "source": _as_text(c.get("source")),
            "last_sent": _as_text(c.get("last_sent")),
            "send_count": str(c.get("send_count", 0)),
        }
        for c in _as_list(newsletter_tab.get("contact_rows"))
    ]
    children: list[dict[str, Any]] = [
        build_characteristic_set_component_frame(
            frame_id="fnd_csm.newsletter.sender",
            label="Sender Assignment",
            items=sender_items,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.newsletter.sender"),
            target_authority="fnd_csm",
        ),
        build_listing_component_frame(
            frame_id="fnd_csm.newsletter.contacts",
            label="Contact List",
            columns=[
                {"key": "email", "label": "Email"},
                {"key": "subscribed", "label": "Subscribed"},
                {"key": "source", "label": "Source"},
                {"key": "last_sent", "label": "Last Sent"},
                {"key": "send_count", "label": "Sends"},
            ],
            rows=contact_rows,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.newsletter.contacts"),
            empty_message="No contacts recorded.",
            initializer_intent="resolve_newsletter_state",
            target_authority="fnd_csm",
        ),
    ]
    return build_component_group_frame(
        frame_id="fnd_csm.tab.newsletter",
        label="Newsletter",
        children=children,
        attention_node_id=grantee_msn or "fnd_csm",
        lens_key=rk("fnd_csm.tab.newsletter"),
        initializer_intent="resolve_newsletter_state",
        target_authority="fnd_csm",
    )


def _build_paypal_component_group(
    paypal_tab: dict[str, Any],
    grantee_msn: str,
    domain: str,
    engaged_frame_id: str,
) -> dict[str, Any]:
    rk = lambda fid: _fnd_csm_render_key(grantee_msn, domain, fid, engaged_frame_id)
    webhook_items = [
        {
            "label": "webhook URL",
            "value": _as_text(paypal_tab.get("webhook_url")) or "— not configured —",
        }
    ]
    orders = _as_list(paypal_tab.get("orders"))
    order_rows = [
        {
            "event": _as_text(o.get("event")),
            "order_id": _as_text(o.get("order_id")),
            "amount": _as_text(o.get("amount")),
            "currency": _as_text(o.get("currency")),
            "status": _as_text(o.get("status")),
            "domain": _as_text(o.get("domain")),
        }
        for o in orders
    ]
    children: list[dict[str, Any]] = [
        build_characteristic_set_component_frame(
            frame_id="fnd_csm.paypal.webhook",
            label="Webhook Configuration",
            items=webhook_items,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.paypal.webhook"),
            target_authority="fnd_csm",
        ),
        build_listing_component_frame(
            frame_id="fnd_csm.paypal.orders",
            label="Recent Orders",
            columns=[
                {"key": "event", "label": "Event"},
                {"key": "order_id", "label": "Order ID"},
                {"key": "amount", "label": "Amount"},
                {"key": "currency", "label": "Currency"},
                {"key": "status", "label": "Status"},
            ],
            rows=order_rows,
            attention_node_id=grantee_msn or "fnd_csm",
            lens_key=rk("fnd_csm.paypal.orders"),
            empty_message="No orders recorded.",
            initializer_intent="resolve_paypal_orders",
            target_authority="fnd_csm",
        ),
    ]
    return build_component_group_frame(
        frame_id="fnd_csm.tab.paypal",
        label="PayPal",
        children=children,
        attention_node_id=grantee_msn or "fnd_csm",
        lens_key=rk("fnd_csm.tab.paypal"),
        initializer_intent="resolve_paypal_orders",
        target_authority="fnd_csm",
    )


def _build_interface_panel(
    *,
    grantee: dict[str, Any],
    domain: str,
    grantee_msn: str,
    engaged_frame_id: str,
    email_tab: dict[str, Any],
    analytics_tab: dict[str, Any],
    newsletter_tab: dict[str, Any],
    paypal_tab: dict[str, Any],
    tool_state: dict[str, Any],
    shell_state: PortalShellState,
    surface_payload: dict[str, Any],
) -> dict[str, Any]:
    active_tab = _as_text(tool_state.get("active_tab")) or "email"
    email_frame = _build_email_component_group(email_tab, grantee_msn, domain, engaged_frame_id)
    analytics_frame = _build_analytics_component_group(analytics_tab, grantee_msn, domain, engaged_frame_id)
    newsletter_frame = _build_newsletter_component_group(newsletter_tab, grantee_msn, domain, engaged_frame_id)
    paypal_frame = _build_paypal_component_group(paypal_tab, grantee_msn, domain, engaged_frame_id)

    return attach_region_family_contract(
        {
            "schema": PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
            "kind": "tabbed_interface_panel",
            "title": "FND-CSM",
            "summary": f"{_as_text(grantee.get('label', 'Grantee'))} — {domain or 'no domain selected'}",
            "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
            "tab_host": "shared_interface_tabs",
            "default_tab_id": active_tab,
            "tabs": [
                {
                    "id": "email",
                    "label": "Email",
                    "initializer": {
                        "verb": "mediate",
                        "target_authority": "fnd_csm",
                        "intent": "resolve_email_profile",
                    },
                },
                {
                    "id": "analytics",
                    "label": "Analytics",
                    "initializer": {
                        "verb": "mediate",
                        "target_authority": "fnd_csm",
                        "intent": "resolve_analytics_summary",
                    },
                },
                {
                    "id": "newsletter",
                    "label": "Newsletter",
                    "initializer": {
                        "verb": "mediate",
                        "target_authority": "fnd_csm",
                        "intent": "resolve_newsletter_state",
                    },
                },
                {
                    "id": "paypal",
                    "label": "PayPal",
                    "initializer": {
                        "verb": "mediate",
                        "target_authority": "fnd_csm",
                        "intent": "resolve_paypal_orders",
                    },
                },
            ],
            "component_frames": [email_frame, analytics_frame, newsletter_frame, paypal_frame],
            "surface_payload": surface_payload,
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=FND_CSM_TOOL_SURFACE_ID,
    )


# ---------------------------------------------------------------------------
# Workbench document loading
# ---------------------------------------------------------------------------

# Canonical sandbox token now lives in
# MyCiteV2/packages/state_machine/portal_shell/shell_schemas.py and is
# re-exported from the portal_shell package alongside
# FND_CSM_TOOL_SURFACE_ID. Keeping the duplicate import line here so the
# rest of this module reads unchanged.
from MyCiteV2.packages.state_machine.portal_shell import (  # noqa: E402
    FND_CSM_SANDBOX_TOKEN,
)


def _load_fnd_csm_sandbox_documents(
    *,
    authority_db_file: str | Path | None,
    tenant_id: str,
) -> list[AuthoritativeDatumDocument]:
    """Load all FND-CSM sandbox documents from the MOS authority store.

    Returns an empty list when ``authority_db_file`` is unset or missing —
    the workbench then renders as an empty sandbox without erroring.

    When ``MYCITE_V2_PORTAL_REQUIRE_AUTHORITY_DB`` is set ("1"/"true"/"yes")
    the absent-or-missing case raises ``RuntimeError`` instead of
    returning an empty list. Production deployments should set this so a
    misconfigured authority path fails closed rather than silently
    rendering an empty workbench.
    """
    require_db = _as_text(os.environ.get("MYCITE_V2_PORTAL_REQUIRE_AUTHORITY_DB")).lower()
    require_db_strict = require_db in {"1", "true", "yes"}
    if authority_db_file is None:
        if require_db_strict:
            raise RuntimeError(
                "MYCITE_V2_PORTAL_REQUIRE_AUTHORITY_DB is set but "
                "authority_db_file was not passed to the FND-CSM runtime."
            )
        return []
    db_path = Path(authority_db_file)
    if not db_path.exists():
        if require_db_strict:
            raise RuntimeError(
                f"MYCITE_V2_PORTAL_REQUIRE_AUTHORITY_DB is set but "
                f"authority_db_file does not exist: {db_path}"
            )
        return []
    store = SqliteSystemDatumStoreAdapter(db_path)
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
    )
    return [
        document
        for document in catalog.documents
        if f".{FND_CSM_SANDBOX_TOKEN}." in document.document_id
    ]


def _resolve_fnd_csm_anchor(
    documents: list[AuthoritativeDatumDocument],
) -> AuthoritativeDatumDocument | None:
    for document in documents:
        if document.is_anchor:
            return document
    return None


def _resolve_fnd_csm_selected_document(
    documents: list[AuthoritativeDatumDocument],
    *,
    focus_document_id: str,
) -> AuthoritativeDatumDocument | None:
    if not focus_document_id:
        return None
    for document in documents:
        if document.document_id == focus_document_id:
            return document
        metadata = document.document_metadata if isinstance(document.document_metadata, dict) else {}
        if _as_text(metadata.get("legacy_alias")) == focus_document_id:
            return document
    return None


# ---------------------------------------------------------------------------
# Main bundle builder
# ---------------------------------------------------------------------------

def build_portal_fnd_csm_surface_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState,
    private_dir: str | Path | None = None,
    webapps_root: str | Path | None = None,
    request_payload: dict[str, Any] | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    tool_rows: list[dict[str, Any]] | None = None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=FND_CSM_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("FND-CSM tool surface is not registered")

    normalized_payload = _as_dict(request_payload)
    tool_state = _normalize_fnd_csm_tool_state(normalized_payload)
    action_result: dict[str, Any] = {}

    # Handle action if present
    action_kind = _as_text(normalized_payload.get("action_kind"))
    if action_kind:
        action_payload = _as_dict(normalized_payload.get("action_payload"))
        tool_state, action_result = _apply_fnd_csm_action(
            action_kind=action_kind,
            action_payload=action_payload,
            tool_state=tool_state,
            private_dir=private_dir,
            authority_db_file=authority_db_file,
            portal_instance_id=portal_instance_id,
        )

    # Pop engaged_frame_id: used for render_key differentiation this cycle only
    engaged_frame_id = _as_text(tool_state.pop("engaged_frame_id", ""))

    # Load grantee profiles and resolve selection
    grantees = _load_grantee_profiles(private_dir)
    selected_grantee = _resolve_selected_grantee(grantees, tool_state)
    domain = _resolve_selected_domain(selected_grantee, tool_state)
    grantee_msn = _as_text(selected_grantee.get("msn_id"))

    # Keep tool_state in sync with resolved selections
    tool_state["selected_grantee_msn"] = grantee_msn
    tool_state["selected_domain"] = domain

    # Build tab data
    email_tab = _build_email_extension_payload(
        selected_grantee,
        domain,
        private_dir,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )
    analytics_tab = _build_analytics_extension_payload(
        domain,
        webapps_root,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )
    newsletter_tab = _build_newsletter_extension_payload(
        selected_grantee,
        domain,
        private_dir,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )
    paypal_tab = _build_paypal_extension_payload(
        selected_grantee,
        domain,
        private_dir,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )

    # Tool posture
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    missing_capabilities = [
        cap for cap in tool_entry.required_capabilities if cap not in portal_scope.capabilities
    ]
    operational = bool(configured and enabled and not missing_capabilities and bool(grantees))

    # Grantee selector entries for control panel
    grantee_entries = [
        {
            "label": _as_text(g.get("label")),
            "meta": _as_text(g.get("msn_id")),
            "active": _as_text(g.get("msn_id")) == _as_text(selected_grantee.get("msn_id")),
        }
        for g in grantees
    ]
    domain_entries = [
        {
            "label": d,
            "meta": d,
            "active": d == domain,
        }
        for d in _as_list(selected_grantee.get("domains"))
    ]

    surface_payload = {
        "schema": FND_CSM_TOOL_SURFACE_SCHEMA,
        "kind": "tool_mediation_surface",
        "tool_id": tool_entry.tool_id,
        "surface_id": FND_CSM_TOOL_SURFACE_ID,
        "entrypoint_id": FND_CSM_TOOL_ENTRYPOINT_ID,
        "title": "FND-CSM",
        "subtitle": "Grantee service management — email, analytics, newsletter, and PayPal.",
        "tool": {
            "tool_id": tool_entry.tool_id,
            "label": tool_entry.label,
            "summary": tool_entry.summary,
            "configured": configured,
            "enabled": enabled,
            "operational": operational,
            "missing_capabilities": missing_capabilities,
        },
        "tool_state": tool_state,
        "action_result": action_result,
        "grantees": [
            {
                "msn_id": _as_text(g.get("msn_id")),
                "label": _as_text(g.get("label")),
                "short_name": _as_text(g.get("short_name")),
                "domains": _as_list(g.get("domains")),
            }
            for g in grantees
        ],
        "selected_grantee": {
            "msn_id": grantee_msn,
            "label": _as_text(selected_grantee.get("label")),
            "short_name": _as_text(selected_grantee.get("short_name")),
            "domains": _as_list(selected_grantee.get("domains")),
            "users": _as_list(selected_grantee.get("users")),
        },
        "selected_domain": domain,
        "focus_subject": dict(shell_state.focus_subject or {}),
        "request_contract": {
            "schema": FND_CSM_TOOL_REQUEST_SCHEMA,
            "action_schema": FND_CSM_TOOL_ACTION_REQUEST_SCHEMA,
            "route": FND_CSM_TOOL_ROUTE,
            "action_route": FND_CSM_TOOL_ROUTE + "/actions",
            "surface_id": FND_CSM_TOOL_SURFACE_ID,
        },
    }

    control_panel = build_unified_control_panel(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=FND_CSM_TOOL_SURFACE_ID,
        surface_label="FND-CSM",
        navigation_groups=[
            {"title": "Grantee", "entries": grantee_entries},
            {"title": "Domain", "entries": domain_entries},
        ],
        actions=[],
        tool_extensions={"fnd_csm_tool_state": tool_state},
    )

    tenant_id = _as_text(portal_instance_id) or _as_text(getattr(portal_scope, "scope_id", "")) or "fnd"
    fnd_csm_sandbox_documents = _load_fnd_csm_sandbox_documents(
        authority_db_file=authority_db_file,
        tenant_id=tenant_id,
    )
    fnd_csm_anchor_document = _resolve_fnd_csm_anchor(fnd_csm_sandbox_documents)
    focus_document_id = _as_text(
        (shell_state.focus_subject or {}).get("file_key")
        if isinstance(shell_state.focus_subject, dict)
        else ""
    )
    fnd_csm_selected_document = _resolve_fnd_csm_selected_document(
        fnd_csm_sandbox_documents,
        focus_document_id=focus_document_id,
    )
    workbench_visible = bool(fnd_csm_sandbox_documents)

    archetype_report = None
    active_for_recognition = fnd_csm_selected_document or fnd_csm_anchor_document
    if active_for_recognition is not None:
        registry = TemplateRegistry()
        candidate_report = recognize_archetype_in_registry(active_for_recognition, registry)
        if candidate_report is not None:
            archetype_report = candidate_report.to_dict()

    workbench_extra_payload: dict[str, Any] = {"forced_visible": workbench_visible}
    if archetype_report is not None:
        workbench_extra_payload["archetype_report"] = archetype_report

    workbench = build_datum_file_workbench(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=FND_CSM_TOOL_SURFACE_ID,
        sandbox_id=FND_CSM_SANDBOX_TOKEN,
        sandbox_label="FND-CSM",
        anchor_document=fnd_csm_anchor_document,
        selected_document=fnd_csm_selected_document,
        sandbox_documents=fnd_csm_sandbox_documents,
        title="FND-CSM Datum Workbench",
        subtitle="Grantee service datum workbench.",
        visible=workbench_visible,
        extra_payload=workbench_extra_payload,
    )

    interface_panel = _build_interface_panel(
        grantee=selected_grantee,
        domain=domain,
        grantee_msn=grantee_msn,
        engaged_frame_id=engaged_frame_id,
        email_tab=email_tab,
        analytics_tab=analytics_tab,
        newsletter_tab=newsletter_tab,
        paypal_tab=paypal_tab,
        tool_state=tool_state,
        shell_state=shell_state,
        surface_payload=surface_payload,
    )

    return {
        "entrypoint_id": FND_CSM_TOOL_ENTRYPOINT_ID,
        "read_write_posture": tool_entry.read_write_posture,
        "page_title": "FND-CSM",
        "page_subtitle": "Grantee service management.",
        "surface_payload": surface_payload,
        "control_panel": control_panel,
        "workbench": workbench,
        "interface_panel": interface_panel,
        "shell_state": shell_state,
        "route": FND_CSM_TOOL_ROUTE,
    }


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_portal_fnd_csm(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    portal_instance_id: str,
    portal_domain: str,
    authority_db_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    shell_request = dict(request_payload or {})
    shell_request["schema"] = PORTAL_SHELL_REQUEST_SCHEMA
    shell_request.setdefault("requested_surface_id", FND_CSM_TOOL_SURFACE_ID)
    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        authority_db_file=authority_db_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )


def run_portal_fnd_csm_action(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    portal_instance_id: str,
    portal_domain: str,
    authority_db_file: str | Path | None = None,
    data_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    shell_request = dict(request_payload or {})
    shell_request["schema"] = PORTAL_SHELL_REQUEST_SCHEMA
    shell_request.setdefault("requested_surface_id", FND_CSM_TOOL_SURFACE_ID)
    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        authority_db_file=authority_db_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
    )




# ---------------------------------------------------------------------------
# Phase 12g — Utilities extension dispatch re-export
# ---------------------------------------------------------------------------
# The dispatch table, the five per-extension renderer wrappers, the grantee
# profile form, and `render_extension` moved to
# `instances/_shared/runtime/utilities_extensions/__init__.py` in Phase 12g.
# No back-compat re-export here: it created a circular import (utilities_extensions
# imports `_build_*_extension_payload` from this module, so we cannot import
# `EXTENSION_RENDERERS` back from utilities_extensions at module load).
# Callers should import EXTENSION_RENDERERS / render_extension from
# `MyCiteV2.instances._shared.runtime.utilities_extensions` directly.
