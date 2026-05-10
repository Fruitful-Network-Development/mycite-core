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
    PortalScope,
    PortalShellState,
    resolve_portal_tool_registry_entry,
)
from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAwsCsmNewsletterStateAdapter,
    FilesystemAwsCsmToolProfileStore,
)

FND_CSM_TOOL_SURFACE_SCHEMA = "mycite.v2.portal.system.tools.fnd_csm.surface.v1"
FND_CSM_TOOL_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.fnd_csm.request.v1"
FND_CSM_TOOL_ACTION_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.fnd_csm.action.request.v1"
GRANTEE_PROFILE_SCHEMA = "mycite.v2.grantee.profile.v1"
_ANALYTICS_EVENT_WINDOW_MONTHS = 3


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


# ---------------------------------------------------------------------------
# Grantee profile loading
# ---------------------------------------------------------------------------

def _load_grantee_profiles(private_dir: str | Path | None) -> list[dict[str, Any]]:
    """Glob and parse all grantee profile JSON files from the fnd-csm tool directory."""
    if private_dir is None:
        return []
    pattern = str(Path(private_dir) / "utilities" / "tools" / "fnd-csm" / "grantee.*.json")
    profiles: list[dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("schema") == GRANTEE_PROFILE_SCHEMA:
                profiles.append(payload)
        except Exception:
            pass
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
# Tab builders
# ---------------------------------------------------------------------------

def _build_email_tab(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
) -> dict[str, Any]:
    """Reads AWS-CSM tool profiles for the selected domain."""
    if not domain or private_dir is None:
        return {"profiles": [], "domain": domain}
    try:
        store = FilesystemAwsCsmToolProfileStore(private_dir)
        domain_record = _as_dict(store.load_domain(domain=domain))
    except Exception:
        domain_record = {}

    profiles: list[dict[str, Any]] = []
    try:
        for payload in store.list_domains():
            ident = _as_dict(payload.get("identity"))
            if _as_text(ident.get("domain")).lower() == domain.lower():
                profiles.append({
                    "profile_id": _as_text(ident.get("profile_id")),
                    "mailbox": _as_text(ident.get("mailbox_local_part")),
                    "send_as": _as_text(ident.get("send_as_email")),
                    "role": _as_text(ident.get("role")),
                    "lifecycle": _as_text(
                        _as_dict(payload.get("workflow")).get("lifecycle_state")
                    ),
                    "inbound": _as_text(
                        _as_dict(payload.get("inbound")).get("receive_state")
                    ),
                })
    except Exception:
        pass
    return {
        "domain": domain,
        "profiles": profiles,
        "domain_record": domain_record,
    }


def _build_analytics_tab(
    domain: str,
    webapps_root: str | Path | None,
) -> dict[str, Any]:
    """Reads NDJSON analytics event files from the webapps folder for this domain."""
    if not domain or webapps_root is None:
        return {"domain": domain, "summary": {}, "recent_events": []}
    events_dir = Path(webapps_root) / "clients" / domain / "analytics" / "events"
    counts: dict[str, int] = {"page_view": 0, "form_submit": 0, "ops_probe": 0, "other": 0}
    recent: list[dict[str, Any]] = []
    if events_dir.exists() and events_dir.is_dir():
        for ndjson_path in sorted(events_dir.glob("*.ndjson"), reverse=True)[:_ANALYTICS_EVENT_WINDOW_MONTHS]:
            try:
                for line in Path(ndjson_path).read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        etype = _as_text(event.get("event_type"))
                        counts[etype if etype in counts else "other"] += 1
                        if len(recent) < 20:
                            recent.append({
                                "event_type": etype,
                                "path": _as_text(event.get("path")),
                                "timestamp": _as_text(event.get("timestamp") or event.get("received_at")),
                            })
                    except Exception:
                        pass
            except Exception:
                pass
    return {
        "domain": domain,
        "summary": counts,
        "recent_events": recent,
        "events_dir_present": events_dir.exists(),
    }


def _build_newsletter_tab(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
) -> dict[str, Any]:
    """Reads the contact log and newsletter sender profile for the domain."""
    if not domain or private_dir is None:
        return {
            "domain": domain,
            "sender_options": _as_list(grantee.get("users")),
            "current_sender": "",
            "contact_rows": [],
        }
    contacts: list[dict[str, Any]] = []
    current_sender = ""
    try:
        adapter = FilesystemAwsCsmNewsletterStateAdapter(private_dir)
        contacts_payload = _as_dict(adapter.load_contact_log(domain=domain))
        raw_contacts = _as_list(contacts_payload.get("contacts"))
        contacts = [
            {
                "email": _as_text(c.get("email")),
                "subscribed": bool(c.get("subscribed")),
                "source": _as_text(c.get("source")),
                "last_sent": _as_text(c.get("last_newsletter_sent_at")),
                "send_count": int(c.get("send_count") or 0),
            }
            for c in raw_contacts
            if isinstance(c, dict) and _as_text(c.get("email"))
        ]
        profile = _as_dict(adapter.load_profile(domain=domain))
        current_sender = _as_text(
            profile.get("selected_sender_address") or profile.get("sender_address")
        ).lower()
    except Exception:
        pass
    return {
        "domain": domain,
        "sender_options": _as_list(grantee.get("users")),
        "current_sender": current_sender,
        "contact_rows": contacts,
        "subscribed_count": sum(1 for c in contacts if c.get("subscribed")),
        "unsubscribed_count": sum(1 for c in contacts if not c.get("subscribed")),
    }


def _build_paypal_tab(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
) -> dict[str, Any]:
    """Reads PayPal orders and any stored webhook configuration."""
    orders: list[dict[str, Any]] = []
    webhook_url = ""
    if private_dir is not None:
        orders_path = Path(private_dir) / "utilities" / "tools" / "paypal-csm" / "orders.ndjson"
        try:
            if orders_path.exists():
                lines = orders_path.read_text(encoding="utf-8").splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        order = json.loads(line)
                        if not domain or _as_text(order.get("domain")).lower() == domain.lower():
                            orders.append({
                                "event": _as_text(order.get("event")),
                                "order_id": _as_text(order.get("order_id")),
                                "amount": _as_text(order.get("amount")),
                                "currency": _as_text(order.get("currency_code")),
                                "status": _as_text(order.get("status")),
                                "timestamp_ms": order.get("timestamp_ms"),
                                "domain": _as_text(order.get("domain")),
                            })
                            if len(orders) >= 30:
                                break
                    except Exception:
                        pass
        except Exception:
            pass
        # Optional per-grantee webhook config
        msn_id = _as_text(grantee.get("msn_id"))
        webhook_path = Path(private_dir) / "utilities" / "tools" / "fnd-csm" / f"paypal-webhook.{msn_id}.json"
        try:
            if webhook_path.exists():
                wh = json.loads(webhook_path.read_text(encoding="utf-8"))
                webhook_url = _as_text(_as_dict(wh).get("webhook_url"))
        except Exception:
            pass
    return {
        "domain": domain,
        "webhook_url": webhook_url,
        "orders": orders,
    }


# ---------------------------------------------------------------------------
# Tool state normalization
# ---------------------------------------------------------------------------

def _normalize_tool_state(request_payload: dict[str, Any]) -> dict[str, Any]:
    tool_state = _as_dict(request_payload.get("tool_state"))
    return {
        "selected_grantee_msn": _as_text(tool_state.get("selected_grantee_msn")),
        "selected_domain": _as_text(tool_state.get("selected_domain")),
        "active_tab": _as_text(tool_state.get("active_tab")) or "email",
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
                adapter = FilesystemAwsCsmNewsletterStateAdapter(private_dir)
                profile = _as_dict(adapter.load_profile(domain=domain))
                profile["selected_sender_address"] = sender
                adapter.save_profile(domain=domain, payload=profile)
                result["message"] = f"Newsletter sender for {domain} set to {sender}"
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
        elif private_dir is None:
            result["status"] = "rejected"
            result["message"] = "private_dir is not configured"
        else:
            try:
                adapter = FilesystemAwsCsmNewsletterStateAdapter(private_dir)
                contacts_payload = _as_dict(adapter.load_contact_log(domain=domain))
                contacts = _as_list(contacts_payload.get("contacts"))
                updated = False
                for contact in contacts:
                    if isinstance(contact, dict) and _as_text(contact.get("email")).lower() == email:
                        contact["subscribed"] = subscribed
                        updated = True
                if updated:
                    contacts_payload["contacts"] = contacts
                    adapter.save_contact_log(domain=domain, payload=contacts_payload)
                    status_word = "subscribed" if subscribed else "unsubscribed"
                    result["message"] = f"{email} {status_word}"
                else:
                    result["status"] = "rejected"
                    result["message"] = f"Contact not found: {email}"
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)

    elif action_kind == "save_paypal_webhook":
        msn_id = _as_text(action_payload.get("msn_id"))
        webhook_url = _as_text(action_payload.get("webhook_url"))
        if not msn_id or private_dir is None:
            result["status"] = "rejected"
            result["message"] = "msn_id and private_dir are required"
        else:
            try:
                wh_path = Path(private_dir) / "utilities" / "tools" / "fnd-csm" / f"paypal-webhook.{msn_id}.json"
                wh_path.write_text(
                    json.dumps({"webhook_url": webhook_url}, indent=2), encoding="utf-8"
                )
                result["message"] = "PayPal webhook URL saved"
            except Exception as exc:
                result["status"] = "error"
                result["message"] = str(exc)

    else:
        result["status"] = "rejected"
        result["message"] = f"Unknown action: {action_kind}"

    return next_state, result


# ---------------------------------------------------------------------------
# Interface panel assembly
# ---------------------------------------------------------------------------

def _build_interface_panel(
    *,
    grantee: dict[str, Any],
    domain: str,
    email_tab: dict[str, Any],
    analytics_tab: dict[str, Any],
    newsletter_tab: dict[str, Any],
    paypal_tab: dict[str, Any],
    tool_state: dict[str, Any],
    shell_state: PortalShellState,
) -> dict[str, Any]:
    active_tab = _as_text(tool_state.get("active_tab")) or "email"

    # Email sections
    email_sections: list[dict[str, Any]] = []
    profiles = _as_list(email_tab.get("profiles"))
    if profiles:
        for prof in profiles:
            email_sections.append({
                "tab_id": "email",
                "title": f"Mailbox: {prof.get('send_as', prof.get('mailbox', '—'))}",
                "rows": [
                    {"label": "send-as", "value": _as_text(prof.get("send_as"))},
                    {"label": "role", "value": _as_text(prof.get("role"))},
                    {"label": "lifecycle", "value": _as_text(prof.get("lifecycle")) or "—"},
                    {"label": "inbound", "value": _as_text(prof.get("inbound")) or "—"},
                ],
            })
    else:
        email_sections.append({
            "tab_id": "email",
            "title": "Email",
            "rows": [{"label": "status", "value": "No profiles found for domain"}],
        })

    # Analytics sections
    summary = _as_dict(analytics_tab.get("summary"))
    analytics_sections: list[dict[str, Any]] = [
        {
            "tab_id": "analytics",
            "title": "Event Summary",
            "rows": [
                {"label": "page views", "value": str(summary.get("page_view", 0))},
                {"label": "form submits", "value": str(summary.get("form_submit", 0))},
                {"label": "ops probes", "value": str(summary.get("ops_probe", 0))},
                {"label": "other", "value": str(summary.get("other", 0))},
            ],
        }
    ]
    recent = _as_list(analytics_tab.get("recent_events"))
    if recent:
        analytics_sections.append({
            "tab_id": "analytics",
            "title": f"Recent Events (last {len(recent)})",
            "rows": [
                {
                    "label": _as_text(e.get("event_type")),
                    "value": _as_text(e.get("path")) or "—",
                    "detail": _as_text(e.get("timestamp")),
                }
                for e in recent[:10]
            ],
        })

    # Newsletter sections
    nl_sections: list[dict[str, Any]] = [
        {
            "tab_id": "newsletter",
            "title": "Sender Assignment",
            "rows": [
                {
                    "label": "current sender",
                    "value": _as_text(newsletter_tab.get("current_sender")) or "— not assigned —",
                },
                {
                    "label": "subscribed",
                    "value": str(newsletter_tab.get("subscribed_count", 0)),
                },
                {
                    "label": "unsubscribed",
                    "value": str(newsletter_tab.get("unsubscribed_count", 0)),
                },
            ],
            "sender_options": _as_list(newsletter_tab.get("sender_options")),
            "current_sender": _as_text(newsletter_tab.get("current_sender")),
        },
        {
            "tab_id": "newsletter",
            "title": "Contact List",
            "contact_rows": _as_list(newsletter_tab.get("contact_rows")),
        },
    ]

    # PayPal sections
    orders = _as_list(paypal_tab.get("orders"))
    paypal_sections: list[dict[str, Any]] = [
        {
            "tab_id": "paypal",
            "title": "Webhook Configuration",
            "rows": [
                {
                    "label": "webhook URL",
                    "value": _as_text(paypal_tab.get("webhook_url")) or "— not configured —",
                }
            ],
            "webhook_url": _as_text(paypal_tab.get("webhook_url")),
            "grantee_msn": _as_text(grantee.get("msn_id")),
        },
        {
            "tab_id": "paypal",
            "title": f"Recent Orders ({len(orders)})",
            "rows": [
                {
                    "label": _as_text(o.get("event")),
                    "value": f"{o.get('amount', '—')} {o.get('currency', '')}".strip(),
                    "detail": _as_text(o.get("status")),
                }
                for o in orders[:10]
            ],
        },
    ]

    all_sections = email_sections + analytics_sections + nl_sections + paypal_sections

    return attach_region_family_contract(
        {
            "schema": PORTAL_SHELL_REGION_INTERFACE_PANEL_SCHEMA,
            "kind": "tabbed_panel",
            "title": "FND-CSM",
            "summary": f"{_as_text(grantee.get('label', 'Grantee'))} — {domain or 'no domain selected'}",
            "subject": dict(shell_state.mediation_subject or shell_state.focus_subject or {}),
            "default_tab_id": active_tab,
            "tabs": [
                {"id": "email", "label": "Email"},
                {"id": "analytics", "label": "Analytics"},
                {"id": "newsletter", "label": "Newsletter"},
                {"id": "paypal", "label": "PayPal"},
            ],
            "sections": all_sections,
            "surface_payload": {
                "grantee": grantee,
                "domain": domain,
                "email": email_tab,
                "analytics": analytics_tab,
                "newsletter": newsletter_tab,
                "paypal": paypal_tab,
                "tool_state": tool_state,
            },
        },
        family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
        surface_id=FND_CSM_TOOL_SURFACE_ID,
    )


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
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=FND_CSM_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("FND-CSM tool surface is not registered")

    normalized_payload = _as_dict(request_payload)
    tool_state = _normalize_tool_state(normalized_payload)
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
        )

    # Load grantee profiles and resolve selection
    grantees = _load_grantee_profiles(private_dir)
    selected_grantee = _resolve_selected_grantee(grantees, tool_state)
    domain = _resolve_selected_domain(selected_grantee, tool_state)

    # Keep tool_state in sync with resolved selections
    tool_state["selected_grantee_msn"] = _as_text(selected_grantee.get("msn_id"))
    tool_state["selected_domain"] = domain

    # Build tab data
    email_tab = _build_email_tab(selected_grantee, domain, private_dir)
    analytics_tab = _build_analytics_tab(domain, webapps_root)
    newsletter_tab = _build_newsletter_tab(selected_grantee, domain, private_dir)
    paypal_tab = _build_paypal_tab(selected_grantee, domain, private_dir)

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
            "msn_id": _as_text(selected_grantee.get("msn_id")),
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

    workbench = build_datum_file_workbench(
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_id=FND_CSM_TOOL_SURFACE_ID,
        sandbox_id="fnd-csm",
        sandbox_label="FND-CSM",
        anchor_document=None,
        sandbox_documents=[],
        title="FND-CSM Datum Workbench",
        subtitle="Grantee service datum workbench.",
        visible=False,
    )

    interface_panel = _build_interface_panel(
        grantee=selected_grantee,
        domain=domain,
        email_tab=email_tab,
        analytics_tab=analytics_tab,
        newsletter_tab=newsletter_tab,
        paypal_tab=paypal_tab,
        tool_state=tool_state,
        shell_state=shell_state,
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
    tool_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        request_payload,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        authority_db_file=authority_db_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
        tool_rows=tool_rows,
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
    tool_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        request_payload,
        portal_instance_id=portal_instance_id,
        portal_domain=portal_domain,
        private_dir=private_dir,
        webapps_root=webapps_root,
        authority_db_file=authority_db_file,
        data_dir=data_dir,
        tool_exposure_policy=tool_exposure_policy,
        tool_rows=tool_rows,
    )
