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
from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAwsCsmNewsletterStateAdapter,
    FilesystemAwsCsmToolProfileStore,
)
from MyCiteV2.packages.core.grantee import (
    GRANTEE_PROFILE_SCHEMA,
    PaypalConfig,
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
# Phase 10 — Reflective/operational separation helpers
# ---------------------------------------------------------------------------
# Each operational extension (email, newsletter, paypal, analytics) splits
# into two sections:
#
#   "configuration" — read-only mirror of the relevant grantee JSON
#                     sub-config, with an "Edit in Grantee Profile" link.
#   The rest of the payload — operational reality (mailboxes, orders,
#                              contact log, events).
#
# Operators edit configuration via the Phase 9 ext_grantee_profile form;
# the operational data is observed-only.


def _grantee_edit_link(focus_field: str) -> dict[str, str]:
    """Build the {label, href, focus_field} edit-link for a configuration section.

    The href points at the Utilities tool-exposure surface with a query
    parameter telling the client to scroll the grantee form to a particular
    sub-config. Phase 10 emits this as plain metadata; the client-side
    rendering interprets focus_field to anchor-scroll.
    """
    return {
        "label": "Edit in Grantee Profile",
        "href": f"/portal/utilities/tool-exposure?utilities_extension=ext_grantee_profile&focus_field={focus_field}",
        "focus_field": focus_field,
    }


def _mask_secret(value: object) -> str:
    """Return a redacted form of a secret. Empty input → empty output.

    Keeps the last 4 characters visible for operator verification; everything
    else is replaced with bullets. Strings shorter than 8 characters are
    fully masked.
    """
    text = _as_text(value)
    if not text:
        return ""
    if len(text) < 8:
        return "•" * len(text)
    return "•" * (len(text) - 4) + text[-4:]


# ---------------------------------------------------------------------------
# Grantee profile loading
# ---------------------------------------------------------------------------

def _hydrate_paypal_from_sidecar(
    private_dir: Path, msn_id: str
) -> PaypalConfig | None:
    """Read a legacy paypal-webhook.{msn_id}.json sidecar into a PaypalConfig.

    Phase 8 read-side backward compat: grantee JSON files written before
    the inline `paypal` sub-config landed will not carry credentials. If a
    sidecar file is present, hydrate the in-memory profile from it so the
    Utilities extensions render correctly. Returns None when no sidecar
    exists or its shape is unusable.
    """
    if not msn_id:
        return None
    sidecar_path = private_dir / "utilities" / "tools" / "fnd-csm" / f"paypal-webhook.{msn_id}.json"
    if not sidecar_path.exists():
        return None
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    webhook_url = _as_text(payload.get("webhook_url"))
    if not webhook_url:
        return None
    try:
        return PaypalConfig(webhook_url=webhook_url)
    except ValueError:
        return None


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
# Tab builders
# ---------------------------------------------------------------------------

def _build_email_tab(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    """Reads AWS-CSM tool profiles for the selected domain.

    When ``authority_db_file`` is provided, profile + domain reads come
    from MOS via :class:`MosDatumAwsCsmProfileAdapter`. Otherwise falls
    back to the legacy filesystem store.
    """
    aws_subconfig = _as_dict(grantee.get("aws_ses"))
    configuration = {
        "label": "AWS SES configuration",
        "summary": "Identity, region, and SMTP credentials. Edit in the Grantee Profile.",
        "items": [
            {"label": "Region", "value": _as_text(aws_subconfig.get("region"))},
            {"label": "Identity", "value": _as_text(aws_subconfig.get("identity"))},
            {"label": "SMTP username", "value": _as_text(aws_subconfig.get("smtp_username"))},
            {"label": "SMTP password", "value": _mask_secret(aws_subconfig.get("smtp_password"))},
        ],
        "edit_link": _grantee_edit_link("aws_ses"),
    }
    if not domain or private_dir is None:
        return {"profiles": [], "domain": domain, "configuration": configuration}

    mos_store: Any = None
    if authority_db_file is not None:
        try:
            from MyCiteV2.packages.adapters.sql.aws_csm_profile_registry import (
                MosDatumAwsCsmProfileAdapter,
            )

            mos_store = MosDatumAwsCsmProfileAdapter(
                authority_db_file=authority_db_file,
                tenant_id=portal_instance_id or "fnd",
            )
        except Exception:
            mos_store = None

    fs_store = FilesystemAwsCsmToolProfileStore(private_dir)

    domain_record: dict[str, Any] = {}
    try:
        if mos_store is not None:
            mos_domain = mos_store.load_domain(domain=domain)
            if mos_domain:
                domain_record = _as_dict(mos_domain)
        if not domain_record:
            domain_record = _as_dict(fs_store.load_domain(domain=domain))
    except Exception:
        domain_record = {}

    profiles: list[dict[str, Any]] = []
    try:
        # Mailboxes for the active domain come from the operator-profile
        # records (one per operator), filtered by identity.domain.
        operator_source = (
            mos_store.list_profiles() if mos_store is not None else fs_store.list_profiles()
        )
        # If MOS is empty (not yet seeded), fall back to filesystem.
        if mos_store is not None and not operator_source:
            operator_source = fs_store.list_profiles()
        for payload in operator_source:
            ident = _as_dict(payload.get("identity"))
            if _as_text(ident.get("domain")).lower() != domain.lower():
                continue
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
        "configuration": configuration,
    }


def _build_analytics_tab(
    domain: str,
    webapps_root: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    """Reads NDJSON analytics event files from the webapps folder for this domain.

    Prefers the pre-aggregated MOS summary datum
    (``fnd_analytics_summary_<domain_token>``) when present, falling
    back to the live NDJSON glob otherwise. The summary datum is
    refreshed by
    :mod:`MyCiteV2.scripts.sync_fnd_analytics_summary` (run periodically).
    """
    # Phase 10: analytics has no operator-editable configuration; the events
    # directory is observed only. Surface a small data_source hint so the
    # client can show operators where the numbers come from.
    data_source: dict[str, str] = {
        "label": "Data source",
        "summary": "Read-only operational events. Configure analytics ingestion at the webapps layer.",
        "events_dir": "",
        "kind": "",
    }
    if not domain or webapps_root is None:
        return {"domain": domain, "summary": {}, "recent_events": [], "data_source": data_source}
    if authority_db_file is not None:
        try:
            from MyCiteV2.packages.adapters.sql.fnd_analytics_summary import (
                MosDatumAnalyticsSummaryAdapter,
            )

            adapter = MosDatumAnalyticsSummaryAdapter(
                authority_db_file=authority_db_file,
                tenant_id=portal_instance_id or "fnd",
            )
            cached = adapter.load_summary(domain=domain)
            if cached is not None:
                data_source["kind"] = "mos_datum"
                return {
                    "domain": domain,
                    "summary": cached.get("summary", {}),
                    "recent_events": cached.get("recent_events", []),
                    "source": "mos_datum",
                    "computed_at": cached.get("computed_at", ""),
                    "data_source": data_source,
                }
        except Exception:
            pass
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
    data_source["events_dir"] = str(events_dir)
    data_source["kind"] = "webapps_ndjson"
    return {
        "domain": domain,
        "summary": counts,
        "recent_events": recent,
        "events_dir_present": events_dir.exists(),
        "data_source": data_source,
    }


def _build_newsletter_tab(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    """Reads the contact log and newsletter sender profile for the domain.

    When ``authority_db_file`` is provided, the contact log is sourced
    from the MOS v2 datum (``fnd_newsletter_contact_log_<domain>``).
    Profile reads stay on the filesystem adapter regardless.
    """
    newsletter_subconfig = _as_dict(grantee.get("newsletter"))
    configuration = {
        "label": "Newsletter configuration",
        "summary": "Sender address, display name, and reply-to. Edit in the Grantee Profile.",
        "items": [
            {"label": "Sender address", "value": _as_text(newsletter_subconfig.get("selected_sender_address"))},
            {"label": "Display name", "value": _as_text(newsletter_subconfig.get("sender_display_name"))},
            {"label": "Reply-to", "value": _as_text(newsletter_subconfig.get("reply_to"))},
        ],
        "edit_link": _grantee_edit_link("newsletter"),
    }
    if not domain or private_dir is None:
        return {
            "domain": domain,
            "sender_options": _as_list(grantee.get("users")),
            "current_sender": "",
            "contact_rows": [],
            "configuration": configuration,
        }
    contacts: list[dict[str, Any]] = []
    current_sender = ""
    try:
        adapter = FilesystemAwsCsmNewsletterStateAdapter(private_dir)
        if authority_db_file is not None:
            from MyCiteV2.packages.adapters.sql.newsletter_contact_log import (
                MosDatumNewsletterContactLogAdapter,
            )

            mos_adapter = MosDatumNewsletterContactLogAdapter(
                authority_db_file=authority_db_file,
                tenant_id=portal_instance_id or "fnd",
            )
            contacts_payload = _as_dict(mos_adapter.load_contact_log(domain=domain))
        else:
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
        "configuration": configuration,
    }


def _build_paypal_tab(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    """Reads PayPal orders and any stored webhook configuration.

    Prefers the MOS-backed orders + webhook datums (per Phase D.3 of
    the unification audit). Falls back to the legacy filesystem NDJSON
    and per-grantee JSON config when MOS data is missing.
    """
    orders: list[dict[str, Any]] = []
    webhook_url = ""

    # Phase 8 (grantee_profile_contract.md): inline grantee.paypal.webhook_url
    # is the canonical source. MOS adapter + sidecar remain as fallbacks for
    # one transition cycle.
    grantee_paypal = _as_dict(grantee.get("paypal"))
    if grantee_paypal:
        webhook_url = _as_text(grantee_paypal.get("webhook_url"))

    if authority_db_file is not None:
        try:
            from MyCiteV2.packages.adapters.sql.fnd_paypal import (
                MosDatumPayPalOrdersAdapter,
                MosDatumPayPalWebhookAdapter,
            )

            orders_adapter = MosDatumPayPalOrdersAdapter(
                authority_db_file=authority_db_file,
                tenant_id=portal_instance_id or "fnd",
            )
            if domain:
                orders = orders_adapter.load_orders(domain=domain)
            # Phase 8: only consult the MOS webhook adapter when the grantee
            # JSON did not already supply a webhook_url. Grantee-inline wins.
            if not webhook_url:
                grantee_msn = _as_text(grantee.get("msn_id"))
                if grantee_msn:
                    webhook_adapter = MosDatumPayPalWebhookAdapter(
                        authority_db_file=authority_db_file,
                        tenant_id=portal_instance_id or "fnd",
                    )
                    hook = webhook_adapter.load_webhook(grantee_msn_id=grantee_msn)
                    if hook:
                        webhook_url = _as_text(hook.get("webhook_url"))
        except Exception:
            orders = []
            # Preserve a grantee-inline webhook_url even if the MOS adapter
            # threw; it was set before this try block ran.

    # Phase 10: build the configuration mirror up front so it's attached
    # to whichever return path executes (MOS shortcut or filesystem fallback).
    paypal_subconfig = _as_dict(grantee.get("paypal"))

    def _paypal_configuration() -> dict[str, Any]:
        return {
            "label": "PayPal configuration",
            "summary": "Webhook URL, client credentials, and environment. Edit in the Grantee Profile.",
            "items": [
                {"label": "Webhook URL", "value": _as_text(paypal_subconfig.get("webhook_url")) or webhook_url},
                {"label": "Environment", "value": _as_text(paypal_subconfig.get("environment")) or "sandbox"},
                {"label": "Client ID", "value": _as_text(paypal_subconfig.get("client_id"))},
                {"label": "Client secret", "value": _mask_secret(paypal_subconfig.get("client_secret"))},
            ],
            "edit_link": _grantee_edit_link("paypal"),
        }

    if orders or webhook_url:
        return {
            "domain": domain,
            "webhook_url": webhook_url,
            "orders": orders,
            "configuration": _paypal_configuration(),
        }

    # Filesystem fallback (unchanged from the pre-MOS behavior).
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
        # Optional per-grantee webhook config — only consulted when no
        # grantee-inline webhook_url (Phase 8 precedence).
        if not webhook_url:
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
        "configuration": _paypal_configuration(),
    }


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
    email_tab = _build_email_tab(
        selected_grantee,
        domain,
        private_dir,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )
    analytics_tab = _build_analytics_tab(
        domain,
        webapps_root,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )
    newsletter_tab = _build_newsletter_tab(
        selected_grantee,
        domain,
        private_dir,
        authority_db_file=authority_db_file,
        portal_instance_id=portal_instance_id,
    )
    paypal_tab = _build_paypal_tab(
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
# Phase 2 — Utilities extension dispatch
# ---------------------------------------------------------------------------
# The four FND-CSM tabs (email, analytics, newsletter, paypal) are re-exposed
# as Utilities extensions per portal_tool_surface_contract.md. Each extension
# reuses the existing _build_*_tab function unchanged; render_extension()
# adapts the context shape so the caller passes one dict regardless of which
# extension is being rendered.


def _render_ext_aws_email(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_email_tab(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _render_ext_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_analytics_tab(
        domain=_as_text(ctx.get("domain")),
        webapps_root=ctx.get("webapps_root"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _render_ext_newsletter(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_newsletter_tab(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _render_ext_paypal(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_paypal_tab(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _build_grantee_profile_form_fields(grantee_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Construct the field list for the grantee profile form.

    Phase 9 (grantee_profile_contract.md): one flat form covering identity
    + paypal + aws_ses + newsletter sub-configs. Nested keys use a "."
    separator (e.g. "paypal.webhook_url"); the save route deserializes
    them back into the nested GranteeProfile shape.
    """
    paypal = _as_dict(grantee_dict.get("paypal"))
    aws_ses = _as_dict(grantee_dict.get("aws_ses"))
    newsletter = _as_dict(grantee_dict.get("newsletter"))
    return [
        # Identity
        {
            "key": "label",
            "label": "Display name",
            "type": "text",
            "value": _as_text(grantee_dict.get("label")),
            "required": True,
        },
        {
            "key": "short_name",
            "label": "Short name",
            "type": "text",
            "value": _as_text(grantee_dict.get("short_name")),
        },
        {
            "key": "domains",
            "label": "Domains",
            "type": "string_list",
            "value": list(grantee_dict.get("domains") or []),
            "help_text": "Domains this grantee owns; one per line.",
        },
        {
            "key": "users",
            "label": "Mailbox users",
            "type": "string_list",
            "value": list(grantee_dict.get("users") or []),
            "help_text": "Operator emails who can act on this grantee.",
        },
        # PayPal
        {
            "key": "paypal.webhook_url",
            "label": "PayPal webhook URL",
            "type": "url",
            "value": _as_text(paypal.get("webhook_url")),
            "placeholder": "https://example.org/__fnd/paypal/webhook",
        },
        {
            "key": "paypal.client_id",
            "label": "PayPal client ID",
            "type": "text",
            "value": _as_text(paypal.get("client_id")),
        },
        {
            "key": "paypal.client_secret",
            "label": "PayPal client secret",
            "type": "password",
            "value": _as_text(paypal.get("client_secret")),
            "help_text": "Stored plaintext on disk; restrict POSIX perms.",
        },
        {
            "key": "paypal.environment",
            "label": "PayPal environment",
            "type": "select",
            "value": _as_text(paypal.get("environment")) or "sandbox",
            "options": ["sandbox", "live"],
        },
        # AWS SES
        {
            "key": "aws_ses.region",
            "label": "AWS SES region",
            "type": "text",
            "value": _as_text(aws_ses.get("region")),
            "placeholder": "us-east-1",
        },
        {
            "key": "aws_ses.identity",
            "label": "AWS SES identity",
            "type": "email",
            "value": _as_text(aws_ses.get("identity")),
            "placeholder": "noreply@example.org",
        },
        {
            "key": "aws_ses.smtp_username",
            "label": "AWS SES SMTP username",
            "type": "text",
            "value": _as_text(aws_ses.get("smtp_username")),
        },
        {
            "key": "aws_ses.smtp_password",
            "label": "AWS SES SMTP password",
            "type": "password",
            "value": _as_text(aws_ses.get("smtp_password")),
            "help_text": "Stored plaintext on disk; restrict POSIX perms.",
        },
        # Newsletter
        {
            "key": "newsletter.selected_sender_address",
            "label": "Newsletter sender",
            "type": "email",
            "value": _as_text(newsletter.get("selected_sender_address")),
            "placeholder": "hello@example.org",
        },
        {
            "key": "newsletter.sender_display_name",
            "label": "Sender display name",
            "type": "text",
            "value": _as_text(newsletter.get("sender_display_name")),
        },
        {
            "key": "newsletter.reply_to",
            "label": "Reply-to",
            "type": "email",
            "value": _as_text(newsletter.get("reply_to")),
        },
    ]


def _render_ext_grantee_profile(ctx: dict[str, Any]) -> dict[str, Any]:
    """Phase 9 renderer for the grantee-profile editor.

    Returns a payload containing one form_component_frame whose submit_action
    points at POST /__fnd/grantee/save. The frame carries the current values
    of every grantee field; if no grantee is selected, the form is omitted
    and the payload signals "select a grantee first".
    """
    from MyCiteV2.packages.state_machine.nimm.mediate_handlers import (
        build_form_component_frame,
    )

    grantee = _as_dict(ctx.get("grantee"))
    msn_id = _as_text(grantee.get("msn_id"))
    if not msn_id:
        return {
            "grantee_msn_id": "",
            "form_frame": None,
            "empty_message": "Select a grantee to edit its profile.",
        }

    form_frame = build_form_component_frame(
        frame_id="grantee_profile_form",
        label=f"Grantee: {grantee.get('label') or msn_id}",
        intro=(
            "Edit identity, mailbox users, and per-grantee credentials. "
            "Saved values land in the grantee JSON file on disk and are "
            "consumed by the Email, Newsletter, and PayPal extensions."
        ),
        fields=_build_grantee_profile_form_fields(grantee),
        submit_action={
            "route": "/__fnd/grantee/save",
            "schema": "mycite.v2.grantee.save.request.v1",
            "payload": {"msn_id": msn_id},
        },
        submit_label="Save grantee profile",
        target_authority="utilities",
    )
    return {
        "grantee_msn_id": msn_id,
        "form_frame": form_frame,
    }


EXTENSION_RENDERERS: dict[str, Any] = {
    "ext_aws_email": _render_ext_aws_email,
    "ext_analytics": _render_ext_analytics,
    "ext_newsletter": _render_ext_newsletter,
    "ext_paypal": _render_ext_paypal,
    "ext_grantee_profile": _render_ext_grantee_profile,
}


def render_extension(tool_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Render an extension by tool_id with the given context dict.

    Returns an empty dict for unknown tool_ids rather than raising; this keeps
    the utilities surface bundle resilient when an extension is mis-registered.
    Required context keys vary by extension; see _render_ext_* for specifics.
    """
    renderer = EXTENSION_RENDERERS.get(_as_text(tool_id))
    if renderer is None:
        return {}
    try:
        return renderer(ctx)
    except Exception:
        return {}
