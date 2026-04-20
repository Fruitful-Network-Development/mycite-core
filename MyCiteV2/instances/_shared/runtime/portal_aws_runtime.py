from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any, Mapping

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    AWS_CSM_TOOL_ACTION_REQUEST_SCHEMA,
    AWS_CSM_TOOL_REQUEST_SCHEMA,
    AWS_CSM_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud import (
    AwsEc2RoleOnboardingCloudAdapter,
)
from MyCiteV2.packages.adapters.filesystem import (
    FilesystemAuditLogAdapter,
    FilesystemAwsCsmToolProfileStore,
)
from MyCiteV2.packages.adapters.filesystem.aws_csm_tool_profile_store import (
    AWS_CSM_DOMAIN_SCHEMA,
)
from MyCiteV2.packages.modules.cross_domain.aws_csm_onboarding import (
    AwsCsmOnboardingService,
    AwsCsmOnboardingUnconfiguredCloudPort,
)
from MyCiteV2.packages.modules.cross_domain.aws_csm_profile_registry import (
    AwsCsmProfileRegistryService,
)
from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingPolicyError
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_ENTRYPOINT_ID,
    AWS_CSM_TOOL_ROUTE,
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PORTAL_SHELL_REQUEST_SCHEMA,
    UTILITIES_ROOT_SURFACE_ID,
    PortalScope,
    activity_icon_id_for_surface,
    build_canonical_url,
    build_portal_activity_dispatch_bodies,
    build_portal_surface_catalog,
    build_shell_composition_payload,
    resolve_portal_tool_registry_entry,
)

AWS_TOOL_STATUS_SCHEMA = "mycite.v2.portal.system.tools.aws_csm.status.v1"
AWS_CSM_ACTION_RESULT_SCHEMA = "mycite.v2.portal.system.tools.aws_csm.action.result.v1"
AWS_CSM_TOOL_ACTION_ROUTE = "/portal/api/v2/system/tools/aws-csm/actions"
AWS_CSM_TOOL_ACTION_ENTRYPOINT_ID = "portal.system.tools.aws_csm.actions"
AWS_CSM_DOMAIN_READINESS_SCHEMA = "mycite.service_tool.aws_csm.domain_readiness.v1"
_AUDIT_FOCUS_SUFFIX = "4-1-77"
_DEFAULT_DOMAIN_REGION = "us-east-1"
_DEFAULT_DOMAIN_INBOUND_LAMBDA = "newsletter-inbound-capture"
_DEFAULT_DOMAIN_RECEIPT_BUCKET = "ses-inbound-fnd-mail"
_ROUTE_SYNC_FAIL_CLOSED_ENV = "AWS_CSM_ROUTE_SYNC_FAIL_CLOSED"
_ROUTE_SYNC_FALLBACK_SCRIPT = "MyCiteV2/scripts/deploy_aws_csm_pass3_inbound_capture.py"
_VISIBLE_ACTIVITY_SURFACE_IDS = (
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
)
_ALLOWED_ACTION_KINDS = frozenset(
    {
        "create_domain",
        "refresh_domain_status",
        "ensure_domain_identity",
        "sync_domain_dns",
        "ensure_domain_receipt_rule",
        "create_profile",
        "stage_smtp_credentials",
        "send_handoff_email",
        "reveal_smtp_password",
        "refresh_provider_status",
        "capture_verification",
        "confirm_verified",
    }
)
_SERVICE_ACTION_KINDS = frozenset(
    {
        "stage_smtp_credentials",
        "refresh_provider_status",
        "capture_verification",
        "confirm_verified",
    }
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_bool(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else _as_text(value).lower() == "true"


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _slugify_domain(value: object) -> str:
    return _normalized_domain(value).replace(".", "-")


def _safe_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _shell_request(portal_scope: PortalScope, query: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REQUEST_SCHEMA,
        "requested_surface_id": AWS_CSM_TOOL_SURFACE_ID,
        "portal_scope": portal_scope.to_dict(),
        "surface_query": dict(query),
    }


def _href_for_query(query: Mapping[str, str]) -> str:
    return build_canonical_url(surface_id=AWS_CSM_TOOL_SURFACE_ID, query=query)


def _normalize_surface_query(raw_query: Mapping[str, Any] | None) -> dict[str, str]:
    raw = dict(raw_query or {})
    query: dict[str, str] = {"view": "domains"}
    domain = _as_text(raw.get("domain")).lower()
    profile = _as_text(raw.get("profile"))
    section = _as_text(raw.get("section")).lower()
    if domain:
        query["domain"] = domain
    if profile:
        query["profile"] = profile
    if section in {"users", "onboarding", "newsletter"}:
        query["section"] = section
    return query


def _normalize_request(payload: dict[str, Any] | None) -> tuple[PortalScope, dict[str, str]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    schema = _as_text(normalized_payload.get("schema")) or AWS_CSM_TOOL_REQUEST_SCHEMA
    if schema != AWS_CSM_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {AWS_CSM_TOOL_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    surface_query = normalized_payload.get("surface_query")
    if not isinstance(surface_query, Mapping):
        surface_query = {
            key: normalized_payload.get(key)
            for key in ("view", "domain", "profile", "section")
            if _as_text(normalized_payload.get(key))
        }
    return portal_scope, _normalize_surface_query(surface_query)


def _normalize_action_request(
    payload: dict[str, Any] | None,
) -> tuple[PortalScope, dict[str, str], dict[str, Any] | None, str, dict[str, Any]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    schema = _as_text(normalized_payload.get("schema")) or AWS_CSM_TOOL_ACTION_REQUEST_SCHEMA
    if schema != AWS_CSM_TOOL_ACTION_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {AWS_CSM_TOOL_ACTION_REQUEST_SCHEMA}")
    portal_scope = PortalScope.from_value(normalized_payload.get("portal_scope"))
    surface_query = _normalize_surface_query(normalized_payload.get("surface_query"))
    raw_shell_state = normalized_payload.get("shell_state")
    shell_state = dict(raw_shell_state) if isinstance(raw_shell_state, dict) else None
    action_kind = _as_text(normalized_payload.get("action_kind")).lower()
    if action_kind not in _ALLOWED_ACTION_KINDS:
        raise ValueError(f"action_kind must be one of {sorted(_ALLOWED_ACTION_KINDS)}")
    action_payload = normalized_payload.get("action_payload")
    if action_payload is None:
        action_payload = {}
    if not isinstance(action_payload, dict):
        raise ValueError("action_payload must be a dict when provided")
    return portal_scope, surface_query, shell_state, action_kind, dict(action_payload)


def _tool_root(private_dir: str | Path | None) -> Path | None:
    if private_dir is None:
        return None
    root = Path(private_dir) / "utilities" / "tools" / "aws-csm"
    return root if root.exists() and root.is_dir() else None


def _tool_store(tool_root: Path | None) -> FilesystemAwsCsmToolProfileStore | None:
    if tool_root is None:
        return None
    return FilesystemAwsCsmToolProfileStore(tool_root)


def _private_config(private_dir: str | Path | None) -> dict[str, Any]:
    if private_dir is None:
        return {}
    return _safe_json_object(Path(private_dir) / "config.json")


def _audit_focus_subject(private_dir: str | Path | None) -> str:
    msn_id = _as_text(_private_config(private_dir).get("msn_id"))
    return f"{msn_id}.{_AUDIT_FOCUS_SUFFIX}" if msn_id else ""


def _tool_files(tool_root: Path | None) -> tuple[str, str]:
    if tool_root is None:
        return "", ""
    collection = ""
    for candidate in sorted(tool_root.glob("tool.*.aws-csm.json")):
        collection = candidate.name
        break
    mediation = "spec.json" if (tool_root / "spec.json").is_file() else ""
    return collection, mediation


def _mailbox_profiles(tool_root: Path | None) -> list[dict[str, Any]]:
    if tool_root is None:
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(tool_root.glob("aws-csm.*.json")):
        payload = _safe_json_object(path)
        identity = dict(payload.get("identity") or {})
        if not identity:
            continue
        profile_id = _as_text(identity.get("profile_id")) or path.stem
        domain = _as_text(identity.get("domain")).lower()
        if not domain:
            continue
        send_as_email = _as_text(identity.get("send_as_email")).lower()
        user_email = _as_text(identity.get("single_user_email")).lower()
        mailbox_local_part = _as_text(identity.get("mailbox_local_part"))
        workflow = dict(payload.get("workflow") or {})
        verification = dict(payload.get("verification") or {})
        provider = dict(payload.get("provider") or {})
        smtp = dict(payload.get("smtp") or {})
        inbound = dict(payload.get("inbound") or {})
        rows.append(
            {
                "profile_id": profile_id,
                "domain": domain,
                "title": send_as_email or user_email or profile_id,
                "mailbox_local_part": (
                    mailbox_local_part or send_as_email.split("@", 1)[0]
                    if "@" in send_as_email
                    else mailbox_local_part
                ),
                "send_as_email": send_as_email,
                "user_email": user_email,
                "role": _as_text(identity.get("role")) or _as_text(identity.get("profile_kind")) or "mailbox",
                "workflow_state": _as_text(workflow.get("lifecycle_state")) or "unknown",
                "verification_state": _as_text(verification.get("portal_state") or verification.get("status")) or "unknown",
                "provider_state": _as_text(
                    provider.get("gmail_send_as_status") or provider.get("aws_ses_identity_status")
                )
                or "unknown",
                "inbound_state": _as_text(inbound.get("receive_state")) or "unknown",
                "forward_target": _as_text(smtp.get("forward_to_email") or identity.get("operator_inbox_target")),
                "raw": payload,
            }
        )
    return rows


def _newsletter_domains(tool_root: Path | None) -> list[dict[str, Any]]:
    if tool_root is None:
        return []
    newsletter_root = tool_root / "newsletter"
    if not newsletter_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for profile_path in sorted(newsletter_root.glob("newsletter.*.profile.json")):
        profile = _safe_json_object(profile_path)
        domain = _as_text(profile.get("domain")).lower()
        if not domain:
            continue
        contacts_payload = _safe_json_object(
            newsletter_root / profile_path.name.replace(".profile.json", ".contacts.json")
        )
        contacts = [item for item in list(contacts_payload.get("contacts") or []) if isinstance(item, dict)]
        dispatches = [item for item in list(contacts_payload.get("dispatches") or []) if isinstance(item, dict)]
        subscribed_count = sum(1 for item in contacts if item.get("subscribed") is True)
        unsubscribed_count = sum(1 for item in contacts if item.get("subscribed") is False)
        rows.append(
            {
                "domain": domain,
                "list_address": _as_text(profile.get("list_address")).lower(),
                "sender_address": _as_text(profile.get("sender_address")).lower(),
                "author_profile_id": _as_text(profile.get("selected_author_profile_id")),
                "author_address": _as_text(profile.get("selected_author_address")).lower(),
                "delivery_mode": _as_text(profile.get("delivery_mode")) or "unknown",
                "contact_count": len(contacts),
                "subscribed_count": subscribed_count,
                "unsubscribed_count": unsubscribed_count,
                "dispatch_count": len(dispatches),
                "last_dispatch_id": _as_text(profile.get("last_dispatch_id")),
                "last_inbound_status": _as_text(profile.get("last_inbound_status")),
                "last_inbound_subject": _as_text(profile.get("last_inbound_subject")),
                "contacts_raw": contacts_payload,
                "raw": profile,
            }
        )
    return rows


def _domain_records(tool_root: Path | None) -> list[dict[str, Any]]:
    store = _tool_store(tool_root)
    if store is None:
        return []
    rows: list[dict[str, Any]] = []
    for payload in store.list_domains():
        identity = _as_dict(payload.get("identity"))
        domain = _normalized_domain(identity.get("domain"))
        if not domain:
            continue
        readiness = _project_domain_readiness(payload)
        observation = _as_dict(payload.get("observation"))
        rows.append(
            {
                "tenant_id": _as_text(identity.get("tenant_id")).lower(),
                "domain": domain,
                "region": _as_text(identity.get("region")) or _DEFAULT_DOMAIN_REGION,
                "hosted_zone_id": _as_text(identity.get("hosted_zone_id")),
                "readiness_state": _as_text(readiness.get("state")) or "unknown",
                "readiness_summary": _as_text(readiness.get("summary")),
                "blocker_count": len(_as_list(readiness.get("blockers"))),
                "last_checked_at": _as_text(observation.get("last_checked_at")),
                "raw": payload,
            }
        )
    return rows


def _join_list(value: object) -> str:
    return ", ".join(_as_text(item) for item in _as_list(value) if _as_text(item))


def _project_domain_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    identity = _as_dict(payload.get("identity"))
    dns = _as_dict(payload.get("dns"))
    ses = _as_dict(payload.get("ses"))
    receipt = _as_dict(payload.get("receipt"))
    observation = _as_dict(payload.get("observation"))

    identity_exists = _as_bool(ses.get("identity_exists"))
    nameserver_match = _as_bool(dns.get("nameserver_match"))
    hosted_zone_present = _as_bool(dns.get("hosted_zone_present"))
    mx_record_present = _as_bool(dns.get("mx_record_present"))
    dkim_records_present = _as_bool(dns.get("dkim_records_present"))
    identity_status = _as_text(ses.get("identity_status")).lower()
    dkim_status = _as_text(ses.get("dkim_status")).lower()
    receipt_status = _as_text(receipt.get("status")).lower()

    blockers: list[str] = []
    if not hosted_zone_present:
        blockers.append("The configured Route 53 hosted zone is missing or unreadable.")
    if not nameserver_match:
        blockers.append("Registrar nameservers do not match the selected hosted zone.")
    if not identity_exists:
        blockers.append("SES domain identity has not been created yet.")
    if identity_exists and not mx_record_present:
        blockers.append("The root MX record is missing from the selected hosted zone.")
    if identity_exists and not dkim_records_present:
        blockers.append("The SES DKIM CNAME records are incomplete in Route 53.")
    if identity_exists and identity_status not in {"verified", "success"}:
        blockers.append("SES domain verification is still pending.")
    if identity_exists and dkim_status and dkim_status not in {"verified", "success"}:
        blockers.append("SES DKIM verification is still pending.")
    if identity_exists and receipt_status != "ok":
        blockers.append("The bare-domain receipt rule is not configured yet.")

    if not identity_exists:
        state = "identity_missing"
        summary = "Create the SES domain identity to obtain DKIM tokens."
    elif any(
        (
            not hosted_zone_present,
            not nameserver_match,
            not mx_record_present,
            not dkim_records_present,
            identity_status not in {"verified", "success"},
            dkim_status not in {"", "verified", "success"},
        )
    ):
        state = "dns_pending"
        summary = "DNS and SES verification still need to settle before mailbox onboarding."
    elif receipt_status != "ok":
        state = "receipt_pending"
        summary = "DNS and SES are ready; finish inbound receipt-rule coverage next."
    else:
        state = "ready_for_mailboxes"
        summary = "Domain onboarding is ready for mailbox creation."

    return {
        "schema": AWS_CSM_DOMAIN_READINESS_SCHEMA,
        "state": state,
        "summary": summary,
        "blockers": blockers,
        "last_checked_at": _as_text(observation.get("last_checked_at")),
        "domain": _normalized_domain(identity.get("domain")),
    }


def _domain_actions(domain_record: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(domain_record, dict):
        return []
    dns = _as_dict(domain_record.get("dns"))
    ses = _as_dict(domain_record.get("ses"))

    nameserver_match = _as_bool(dns.get("nameserver_match"))
    hosted_zone_present = _as_bool(dns.get("hosted_zone_present"))
    dkim_tokens = _as_list(ses.get("dkim_tokens"))
    identity_exists = _as_bool(ses.get("identity_exists"))
    mx_record_present = _as_bool(dns.get("mx_record_present"))

    sync_dns_enabled = hosted_zone_present and nameserver_match and len(dkim_tokens) >= 3
    receipt_enabled = nameserver_match and identity_exists and mx_record_present
    return [
        {
            "kind": "refresh_domain_status",
            "label": "Refresh Domain Status",
            "enabled": True,
            "disabled_reason": "",
        },
        {
            "kind": "ensure_domain_identity",
            "label": "Ensure SES Identity",
            "enabled": hosted_zone_present,
            "disabled_reason": "" if hosted_zone_present else "Provide a hosted zone before creating the SES identity.",
        },
        {
            "kind": "sync_domain_dns",
            "label": "Sync DNS Records",
            "enabled": sync_dns_enabled,
            "disabled_reason": (
                ""
                if sync_dns_enabled
                else "Refresh the domain status after SES identity creation and confirm the hosted-zone nameservers match."
            ),
        },
        {
            "kind": "ensure_domain_receipt_rule",
            "label": "Ensure Receipt Rule",
            "enabled": receipt_enabled,
            "disabled_reason": (
                ""
                if receipt_enabled
                else "Finish SES identity creation and MX/DNS synchronization before enabling receipt-rule coverage."
            ),
        },
    ]


def _selected_domain_onboarding(selected_domain_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(selected_domain_record, dict):
        return None
    raw = _as_dict(selected_domain_record.get("raw"))
    identity = _as_dict(raw.get("identity"))
    dns = _as_dict(raw.get("dns"))
    ses = _as_dict(raw.get("ses"))
    receipt = _as_dict(raw.get("receipt"))
    observation = _as_dict(raw.get("observation"))
    readiness = _project_domain_readiness(raw)
    return {
        "tenant_id": _as_text(identity.get("tenant_id")).lower(),
        "domain": _normalized_domain(identity.get("domain")),
        "region": _as_text(identity.get("region")) or _DEFAULT_DOMAIN_REGION,
        "hosted_zone_id": _as_text(identity.get("hosted_zone_id")),
        "readiness_state": _as_text(readiness.get("state")),
        "readiness_summary": _as_text(readiness.get("summary")),
        "blockers": list(readiness.get("blockers") or []),
        "last_checked_at": _as_text(observation.get("last_checked_at")),
        "registrar_nameservers": _join_list(dns.get("registrar_nameservers")),
        "hosted_zone_nameservers": _join_list(dns.get("hosted_zone_nameservers")),
        "nameserver_match": "yes" if _as_bool(dns.get("nameserver_match")) else "no",
        "mx_record_present": "yes" if _as_bool(dns.get("mx_record_present")) else "no",
        "mx_record_values": _join_list(dns.get("mx_record_values")),
        "ses_identity_exists": "yes" if _as_bool(ses.get("identity_exists")) else "no",
        "ses_identity_status": _as_text(ses.get("identity_status")) or "not_started",
        "dkim_status": _as_text(ses.get("dkim_status")) or "not_started",
        "dkim_token_count": str(len(_as_list(ses.get("dkim_tokens")))),
        "dkim_records_present": "yes" if _as_bool(dns.get("dkim_records_present")) else "no",
        "receipt_rule_status": _as_text(receipt.get("status")) or "not_ready",
        "receipt_rule_name": _as_text(receipt.get("rule_name")) or f"portal-capture-{_slugify_domain(identity.get('domain'))}",
        "receipt_rule_recipient": _as_text(receipt.get("expected_recipient") or identity.get("domain")),
        "receipt_rule_bucket": _as_text(receipt.get("bucket")) or _DEFAULT_DOMAIN_RECEIPT_BUCKET,
        "receipt_rule_prefix": _as_text(receipt.get("prefix")) or f"inbound/{_normalized_domain(identity.get('domain'))}/",
        "actions": _domain_actions(raw),
    }


def _tool_status(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    tool_root: Path | None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=AWS_CSM_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("AWS-CSM tool registry entry is missing")
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    missing_capabilities = [cap for cap in tool_entry.required_capabilities if cap not in portal_scope.capabilities]
    missing_integrations: list[str] = []
    if tool_root is None:
        missing_integrations.append("aws_csm_state_root")
    operational = bool(configured and enabled and not missing_capabilities and not missing_integrations)
    return {
        "schema": AWS_TOOL_STATUS_SCHEMA,
        "configured": configured,
        "enabled": enabled,
        "operational": operational,
        "missing_integrations": missing_integrations,
        "required_capabilities": list(tool_entry.required_capabilities),
        "missing_capabilities": missing_capabilities,
        "tool_id": tool_entry.tool_id,
        "label": tool_entry.label,
        "summary": tool_entry.summary,
    }


def _workspace(
    *,
    portal_scope: PortalScope,
    query: dict[str, str],
    tool_root: Path | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    collection_file, mediation_file = _tool_files(tool_root)
    domain_records = _domain_records(tool_root)
    mailbox_profiles = _mailbox_profiles(tool_root)
    newsletter_domains = _newsletter_domains(tool_root)

    newsletter_by_domain = {item["domain"]: item for item in newsletter_domains}
    profiles_by_id = {item["profile_id"]: item for item in mailbox_profiles}
    domain_map: dict[str, dict[str, Any]] = {}
    for domain_record in domain_records:
        domain = _as_text(domain_record.get("domain"))
        domain_map.setdefault(
            domain,
            {
                "domain": domain,
                "mailboxes": [],
                "newsletter": newsletter_by_domain.get(domain),
                "domain_record": domain_record,
            },
        )
    for profile in mailbox_profiles:
        domain_row = domain_map.setdefault(
            profile["domain"],
            {
                "domain": profile["domain"],
                "mailboxes": [],
                "newsletter": newsletter_by_domain.get(profile["domain"]),
                "domain_record": None,
            },
        )
        domain_row["mailboxes"].append(profile)
    for newsletter in newsletter_domains:
        domain_row = domain_map.setdefault(
            newsletter["domain"],
            {"domain": newsletter["domain"], "mailboxes": [], "newsletter": newsletter, "domain_record": None},
        )
        domain_row["newsletter"] = newsletter

    requested_profile = profiles_by_id.get(_as_text(query.get("profile")))
    selected_domain = _as_text(query.get("domain")).lower()
    if not selected_domain and requested_profile is not None:
        selected_domain = requested_profile["domain"]
    if selected_domain not in domain_map:
        selected_domain = ""

    selected_profile = None
    if requested_profile is not None and requested_profile["domain"] == selected_domain:
        selected_profile = requested_profile

    selected_section = _as_text(query.get("section")).lower()
    if selected_section not in {"users", "onboarding", "newsletter"}:
        selected_section = ""

    resolved_query: dict[str, str] = {"view": "domains"}
    if selected_domain:
        resolved_query["domain"] = selected_domain
    if selected_profile is not None:
        resolved_query["profile"] = selected_profile["profile_id"]
    if selected_section:
        resolved_query["section"] = selected_section

    domain_rows: list[dict[str, Any]] = []
    total_contact_count = 0
    for domain in sorted(domain_map.keys()):
        mailbox_count = len(domain_map[domain]["mailboxes"])
        newsletter = domain_map[domain].get("newsletter")
        domain_record = domain_map[domain].get("domain_record")
        contact_count = int(newsletter.get("contact_count") or 0) if isinstance(newsletter, dict) else 0
        total_contact_count += contact_count
        query_for_domain = {"view": "domains", "domain": domain}
        domain_rows.append(
            {
                "domain": domain,
                "label": domain,
                "profile_count": mailbox_count,
                "newsletter_configured": newsletter is not None,
                "contact_count": contact_count,
                "dispatch_count": int(newsletter.get("dispatch_count") or 0) if isinstance(newsletter, dict) else 0,
                "onboarding_state": _as_text(_as_dict(domain_record).get("readiness_state")) or "legacy_inferred",
                "onboarding_summary": _as_text(_as_dict(domain_record).get("readiness_summary")),
                "tenant_id": _as_text(_as_dict(domain_record).get("tenant_id")),
                "hosted_zone_id": _as_text(_as_dict(domain_record).get("hosted_zone_id")),
                "active": domain == selected_domain,
                "href": _href_for_query(query_for_domain),
                "shell_request": _shell_request(portal_scope, query_for_domain),
            }
        )

    selected_domain_row = domain_map.get(selected_domain) if selected_domain else None
    selected_mailboxes = sorted(
        list((selected_domain_row or {}).get("mailboxes") or []),
        key=lambda item: (item.get("title") or "", item.get("profile_id") or ""),
    )
    selected_newsletter = dict((selected_domain_row or {}).get("newsletter") or {}) if selected_domain_row else None
    selected_domain_record = (
        dict((selected_domain_row or {}).get("domain_record") or {}) if selected_domain_row else None
    )

    mailbox_rows: list[dict[str, Any]] = []
    for profile in selected_mailboxes:
        query_for_profile = {"view": "domains", "domain": selected_domain, "profile": profile["profile_id"]}
        mailbox_rows.append(
            {
                **profile,
                "active": selected_profile is not None and profile["profile_id"] == selected_profile["profile_id"],
                "href": _href_for_query(query_for_profile),
                "shell_request": _shell_request(portal_scope, query_for_profile),
            }
        )

    section_rows = []
    if selected_domain:
        for token, label in (("users", "Users"), ("onboarding", "Onboarding"), ("newsletter", "Newsletter")):
            query_for_section = {"view": "domains", "domain": selected_domain, "section": token}
            if token != "newsletter" and selected_profile is not None:
                query_for_section["profile"] = selected_profile["profile_id"]
            section_rows.append(
                {
                    "label": label,
                    "active": selected_section == token,
                    "href": _href_for_query(query_for_section),
                    "shell_request": _shell_request(portal_scope, query_for_section),
                }
            )

    workspace = {
        "active_filters": {
            "view": "domains",
            "domain": selected_domain,
            "profile_id": selected_profile["profile_id"] if isinstance(selected_profile, dict) else "",
            "section": selected_section,
        },
        "collection_file": collection_file,
        "mediation_file": mediation_file,
        "domain_rows": domain_rows,
        "mailbox_rows": mailbox_rows,
        "section_rows": section_rows,
        "selected_domain": selected_domain,
        "selected_domain_record": selected_domain_record,
        "selected_profile": selected_profile,
        "selected_newsletter": selected_newsletter,
        "domain_count": len(domain_rows),
        "domain_record_count": len(domain_records),
        "profile_count": len(mailbox_profiles),
        "newsletter_domain_count": len(newsletter_domains),
        "contact_count": total_contact_count,
    }
    return workspace, resolved_query


def _selected_domain_create_profile(tool_root: Path | None, *, selected_domain: str) -> dict[str, Any] | None:
    domain = _as_text(selected_domain).lower()
    if not domain:
        return None
    registry = _tool_store(tool_root)
    if registry is None:
        return {
            "domain": domain,
            "enabled": False,
            "disabled_reason": "AWS-CSM tool state is not configured in this portal runtime.",
            "tenant_id": "",
            "region": "",
            "default_role": "operator",
        }
    seed = registry.resolve_domain_seed(domain=domain)
    if not isinstance(seed, dict):
        return {
            "domain": domain,
            "enabled": False,
            "disabled_reason": f"No seed tenant metadata exists for {domain}.",
            "tenant_id": "",
            "region": "",
            "default_role": "operator",
        }
    return {
        "domain": domain,
        "enabled": True,
        "disabled_reason": "",
        "tenant_id": _as_text(seed.get("tenant_id")).lower(),
        "region": _as_text(seed.get("region")) or "us-east-1",
        "default_role": "operator",
    }


def _selected_profile_onboarding(selected_profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(selected_profile, dict):
        return None
    raw = _as_dict(selected_profile.get("raw"))
    identity = _as_dict(raw.get("identity"))
    workflow = _as_dict(raw.get("workflow"))
    verification = _as_dict(raw.get("verification"))
    provider = _as_dict(raw.get("provider"))
    smtp = _as_dict(raw.get("smtp"))
    inbound = _as_dict(raw.get("inbound"))
    tenant_scope_id = (
        _as_text(identity.get("tenant_id"))
        or _as_text(identity.get("domain")).lower()
        or _as_text(identity.get("profile_id"))
    )
    handoff_ready = _as_text(smtp.get("credentials_secret_state")).lower() == "configured" or bool(
        smtp.get("handoff_ready")
    )
    actions = [
        {
            "kind": "stage_smtp_credentials",
            "label": "Stage SMTP Credentials",
            "enabled": True,
            "disabled_reason": "",
        },
        {
            "kind": "send_handoff_email",
            "label": "Send Handoff Email",
            "enabled": handoff_ready and bool(_as_text(smtp.get("forward_to_email") or identity.get("operator_inbox_target"))),
            "disabled_reason": "" if handoff_ready else "Stage SMTP credentials before sending instructions.",
        },
        {
            "kind": "reveal_smtp_password",
            "label": "Reveal SMTP Password",
            "enabled": handoff_ready,
            "disabled_reason": "" if handoff_ready else "Stage SMTP credentials before revealing the password.",
        },
        {
            "kind": "refresh_provider_status",
            "label": "Refresh Provider Status",
            "enabled": True,
            "disabled_reason": "",
        },
        {
            "kind": "capture_verification",
            "label": "Capture Verification",
            "enabled": True,
            "disabled_reason": "",
        },
        {
            "kind": "confirm_verified",
            "label": "Confirm Verified",
            "enabled": True,
            "disabled_reason": "",
        },
    ]
    return {
        "profile_id": _as_text(selected_profile.get("profile_id")),
        "tenant_scope_id": tenant_scope_id,
        "workflow_state": _as_text(workflow.get("lifecycle_state")) or _as_text(selected_profile.get("workflow_state")),
        "handoff_status": _as_text(workflow.get("handoff_status")),
        "verification_state": _as_text(verification.get("portal_state") or verification.get("status"))
        or _as_text(selected_profile.get("verification_state")),
        "email_received_at": _as_text(verification.get("email_received_at") or inbound.get("latest_message_captured_at")),
        "verified_at": _as_text(verification.get("verified_at")),
        "latest_message_reference": _as_text(
            verification.get("latest_message_reference")
            or inbound.get("latest_message_s3_uri")
            or inbound.get("capture_source_reference")
        ),
        "provider_state": _as_text(provider.get("gmail_send_as_status") or provider.get("aws_ses_identity_status"))
        or _as_text(selected_profile.get("provider_state")),
        "inbound_state": _as_text(inbound.get("receive_state")) or _as_text(selected_profile.get("inbound_state")),
        "handoff": {
            "send_as_email": _as_text(identity.get("send_as_email") or selected_profile.get("send_as_email")),
            "single_user_email": _as_text(identity.get("single_user_email") or selected_profile.get("user_email")),
            "operator_inbox_target": _as_text(identity.get("operator_inbox_target")),
            "forward_target": _as_text(smtp.get("forward_to_email") or selected_profile.get("forward_target")),
            "smtp_host": _as_text(smtp.get("host")),
            "smtp_port": _as_text(smtp.get("port")),
            "smtp_username": _as_text(smtp.get("username")),
            "secret_name": _as_text(smtp.get("credentials_secret_name")),
            "secret_state": _as_text(smtp.get("credentials_secret_state")),
            "handoff_ready": handoff_ready,
            "email_received_at": _as_text(verification.get("email_received_at") or inbound.get("latest_message_captured_at")),
            "verified_at": _as_text(verification.get("verified_at")),
        },
        "actions": actions,
    }


def _facts_rows(pairs: list[tuple[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for label, value in pairs:
        text = _as_text(value)
        if text:
            rows.append({"label": label, "value": text})
    return rows


def _build_control_panel(
    *,
    portal_scope: PortalScope,
    workspace: dict[str, Any],
) -> dict[str, Any]:
    collection_file = _as_text(workspace.get("collection_file"))
    mediation_file = _as_text(workspace.get("mediation_file"))
    groups = [
        {
            "title": "Domains",
            "entries": [
                {
                    "label": _as_text(row.get("label")) or _as_text(row.get("domain")),
                    "meta": (
                        f"{int(row.get('profile_count') or 0)} mailbox"
                        + ("" if int(row.get("profile_count") or 0) == 1 else "es")
                        + (" · newsletter" if row.get("newsletter_configured") else "")
                    ),
                    "active": bool(row.get("active")),
                    "href": _as_text(row.get("href")),
                    "shell_request": row.get("shell_request"),
                }
                for row in list(workspace.get("domain_rows") or [])
            ],
        }
    ]
    mailbox_rows = list(workspace.get("mailbox_rows") or [])
    if mailbox_rows:
        groups.append(
            {
                "title": "User Emails",
                "entries": [
                    {
                        "label": _as_text(row.get("title")) or _as_text(row.get("profile_id")),
                        "meta": " · ".join(
                            [token for token in (_as_text(row.get("role")), _as_text(row.get("workflow_state"))) if token]
                        ),
                        "active": bool(row.get("active")),
                        "href": _as_text(row.get("href")),
                        "shell_request": row.get("shell_request"),
                    }
                    for row in mailbox_rows
                ],
            }
        )
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "AWS-CSM",
        "context_items": [
            {"label": "Sandbox", "value": "AWS-CSM"},
            {"label": "File", "value": collection_file or "tool.aws-csm.json"},
            {"label": "Mediation", "value": mediation_file or "spec.json"},
        ],
        "verb_tabs": [],
        "groups": groups,
        "actions": [],
    }


def _build_inspector(
    *,
    tool_status: dict[str, Any],
    workspace: dict[str, Any],
    surface_payload: dict[str, Any],
) -> dict[str, Any]:
    selected_domain_record = workspace.get("selected_domain_record")
    selected_profile = workspace.get("selected_profile")
    selected_newsletter = workspace.get("selected_newsletter")
    subject = None
    sections: list[dict[str, Any]] = [
        {
            "title": "Tool Posture",
            "rows": _facts_rows(
                [
                    ("configured", "yes" if tool_status.get("configured") else "no"),
                    ("enabled", "yes" if tool_status.get("enabled") else "no"),
                    ("operational", "yes" if tool_status.get("operational") else "no"),
                    ("required capability", ", ".join(list(tool_status.get("required_capabilities") or []))),
                    ("missing capability", ", ".join(list(tool_status.get("missing_capabilities") or []))),
                ]
            ),
        }
    ]
    action_result = _as_dict(surface_payload.get("action_result"))
    if action_result:
        sections.append(
            {
                "title": "Latest Action",
                "rows": _facts_rows(
                    [
                        ("action", action_result.get("action_kind")),
                        ("status", action_result.get("status")),
                        ("message", action_result.get("message")),
                    ]
                ),
            }
        )
    if isinstance(selected_profile, dict):
        raw = dict(selected_profile.get("raw") or {})
        identity = dict(raw.get("identity") or {})
        workflow = dict(raw.get("workflow") or {})
        verification = dict(raw.get("verification") or {})
        provider = dict(raw.get("provider") or {})
        smtp = dict(raw.get("smtp") or {})
        inbound = dict(raw.get("inbound") or {})
        subject = {"level": "profile", "id": _as_text(selected_profile.get("profile_id"))}
        sections.extend(
            [
                {
                    "title": "Profile",
                    "rows": _facts_rows(
                        [
                            ("domain", identity.get("domain")),
                            ("send-as", identity.get("send_as_email")),
                            ("user", identity.get("single_user_email")),
                            ("role", identity.get("role")),
                        ]
                    ),
                },
                {
                    "title": "Onboarding",
                    "rows": _facts_rows(
                        [
                            ("workflow", workflow.get("lifecycle_state")),
                            ("handoff", workflow.get("handoff_status")),
                            ("verification", verification.get("portal_state") or verification.get("status")),
                            (
                                "provider",
                                provider.get("gmail_send_as_status") or provider.get("aws_ses_identity_status"),
                            ),
                            ("inbound", inbound.get("receive_state")),
                        ]
                    ),
                },
                {
                    "title": "SMTP and Inbound",
                    "rows": _facts_rows(
                        [
                            ("forward target", smtp.get("forward_to_email")),
                            ("credentials", smtp.get("credentials_secret_state")),
                            ("receive verified", inbound.get("receive_verified")),
                            ("capture source", inbound.get("capture_source_kind")),
                        ]
                    ),
                },
            ]
        )
    elif isinstance(selected_domain_record, dict):
        raw = dict(selected_domain_record.get("raw") or {})
        identity = dict(raw.get("identity") or {})
        readiness = _project_domain_readiness(raw)
        receipt = dict(raw.get("receipt") or {})
        subject = {"level": "domain", "id": _as_text(identity.get("domain"))}
        sections.extend(
            [
                {
                    "title": "Domain Onboarding",
                    "rows": _facts_rows(
                        [
                            ("tenant", identity.get("tenant_id")),
                            ("domain", identity.get("domain")),
                            ("region", identity.get("region")),
                            ("hosted zone", identity.get("hosted_zone_id")),
                            ("readiness", readiness.get("state")),
                            ("receipt rule", receipt.get("rule_name")),
                        ]
                    ),
                }
            ]
        )
    elif isinstance(selected_newsletter, dict):
        subject = {"level": "domain", "id": _as_text(selected_newsletter.get("domain"))}
        sections.append(
            {
                "title": "Newsletter",
                "rows": _facts_rows(
                    [
                        ("domain", selected_newsletter.get("domain")),
                        ("list", selected_newsletter.get("list_address")),
                        ("author", selected_newsletter.get("author_address")),
                        ("delivery mode", selected_newsletter.get("delivery_mode")),
                        ("contacts", selected_newsletter.get("contact_count")),
                        ("dispatches", selected_newsletter.get("dispatch_count")),
                    ]
                ),
            }
        )
    return {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "aws_csm_inspector",
        "title": "AWS-CSM",
        "summary": "Unified service-tool posture and selected domain detail.",
        "visible": True,
        "subject": subject,
        "sections": sections,
        "surface_payload": surface_payload,
    }


def _activity_items(
    *,
    portal_scope: PortalScope,
    active_surface_id: str,
    shell_state: object | None,
) -> list[dict[str, Any]]:
    dispatch_bodies = build_portal_activity_dispatch_bodies(
        portal_scope=portal_scope,
        shell_state=shell_state,
    )
    items: list[dict[str, Any]] = []
    for entry in build_portal_surface_catalog():
        if entry.surface_id not in _VISIBLE_ACTIVITY_SURFACE_IDS:
            continue
        items.append(
            {
                "item_id": entry.surface_id,
                "label": entry.label,
                "icon_id": activity_icon_id_for_surface(entry.surface_id),
                "href": entry.route,
                "active": entry.surface_id == active_surface_id,
                "nav_kind": "surface",
                "nav_behavior": "dispatch" if entry.surface_id in dispatch_bodies else "direct",
                "shell_request": dispatch_bodies.get(entry.surface_id),
            }
        )
    return items


def _shell_state_payload(shell_state: object | None) -> dict[str, Any] | None:
    if isinstance(shell_state, dict):
        return dict(shell_state)
    to_dict = getattr(shell_state, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        return dict(payload) if isinstance(payload, dict) else None
    return None


def _control_panel_collapsed(shell_state: object | None) -> bool:
    if isinstance(shell_state, dict):
        chrome = shell_state.get("chrome")
        return bool(chrome.get("control_panel_collapsed")) if isinstance(chrome, dict) else False
    chrome = getattr(shell_state, "chrome", None)
    return bool(getattr(chrome, "control_panel_collapsed", False))


def _surface_payload(
    *,
    workspace: dict[str, Any],
    tool_status: dict[str, Any],
    action_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": AWS_CSM_TOOL_SURFACE_SCHEMA,
        "kind": "aws_csm_workspace",
        "title": "AWS-CSM",
        "subtitle": "Unified domain gallery with mailbox onboarding and newsletter state.",
        "tool": tool_status,
        "action_contract": {
            "route": AWS_CSM_TOOL_ACTION_ROUTE,
            "request_schema": AWS_CSM_TOOL_ACTION_REQUEST_SCHEMA,
        },
        "cards": [
            {"label": "Domains", "value": str(workspace["domain_count"])},
            {"label": "User Emails", "value": str(workspace["profile_count"])},
            {"label": "Newsletter Domains", "value": str(workspace["newsletter_domain_count"])},
            {"label": "Operational", "value": "yes" if tool_status["operational"] else "no"},
        ],
        "notes": [
            "AWS-CSM is one service tool surface under SYSTEM.",
            "Operational AWS employment requires FND peripheral routing and only works on the FND portal instance.",
        ],
        "workspace": workspace,
    }
    if isinstance(action_result, dict) and action_result:
        payload["action_result"] = action_result
    return payload


def build_portal_aws_surface_bundle(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: object | None,
    surface_query: Mapping[str, Any] | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    action_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if surface_id != AWS_CSM_TOOL_SURFACE_ID:
        raise ValueError(f"Unsupported AWS surface: {surface_id}")
    tool_root = _tool_root(private_dir)
    tool_status = _tool_status(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        tool_root=tool_root,
    )
    workspace, canonical_query = _workspace(
        portal_scope=portal_scope,
        query=_normalize_surface_query(surface_query),
        tool_root=tool_root,
    )
    enriched_workspace = dict(workspace)
    enriched_workspace["create_domain_defaults"] = {
        "tenant_id": "",
        "domain": "",
        "hosted_zone_id": "",
        "region": _DEFAULT_DOMAIN_REGION,
    }
    enriched_workspace["selected_domain_create_profile"] = _selected_domain_create_profile(
        tool_root,
        selected_domain=_as_text(workspace.get("selected_domain")),
    )
    enriched_workspace["selected_domain_onboarding"] = _selected_domain_onboarding(
        workspace.get("selected_domain_record") if isinstance(workspace.get("selected_domain_record"), dict) else None
    )
    enriched_workspace["selected_profile_onboarding"] = _selected_profile_onboarding(
        workspace.get("selected_profile") if isinstance(workspace.get("selected_profile"), dict) else None
    )
    surface_payload = _surface_payload(
        workspace=enriched_workspace,
        tool_status=tool_status,
        action_result=action_result,
    )
    inspector = _build_inspector(
        tool_status=tool_status,
        workspace=enriched_workspace,
        surface_payload=surface_payload,
    )
    return {
        "entrypoint_id": AWS_CSM_TOOL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": "AWS-CSM",
        "page_subtitle": "Unified domain gallery and FND-routed service-tool posture.",
        "surface_payload": surface_payload,
        "control_panel": _build_control_panel(portal_scope=portal_scope, workspace=enriched_workspace),
        "workbench": {
            "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
            "kind": "aws_csm_workbench",
            "title": "AWS-CSM",
            "subtitle": "Domain gallery, user email gallery, onboarding, and newsletter state.",
            "visible": False,
            "surface_payload": surface_payload,
        },
        "inspector": inspector,
        "canonical_route": AWS_CSM_TOOL_ROUTE,
        "canonical_query": canonical_query,
        "canonical_url": build_canonical_url(surface_id=AWS_CSM_TOOL_SURFACE_ID, query=canonical_query),
        "shell_state": _shell_state_payload(shell_state),
    }


def _runtime_envelope_from_bundle(
    *,
    bundle: dict[str, Any],
    portal_scope: PortalScope,
    requested_surface_id: str,
    entrypoint_id: str,
    read_write_posture: str,
) -> dict[str, Any]:
    shell_state = bundle.get("shell_state")
    composition = build_shell_composition_payload(
        active_surface_id=AWS_CSM_TOOL_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        page_title=_as_text(bundle.get("page_title")) or "AWS-CSM",
        page_subtitle=_as_text(bundle.get("page_subtitle")),
        activity_items=_activity_items(
            portal_scope=portal_scope,
            active_surface_id=AWS_CSM_TOOL_SURFACE_ID,
            shell_state=shell_state,
        ),
        control_panel=_as_dict(bundle.get("control_panel")),
        workbench=_as_dict(bundle.get("workbench")),
        inspector=_as_dict(bundle.get("inspector")),
        shell_state=shell_state,
        control_panel_collapsed=_control_panel_collapsed(shell_state),
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=requested_surface_id,
        surface_id=AWS_CSM_TOOL_SURFACE_ID,
        entrypoint_id=entrypoint_id,
        read_write_posture=read_write_posture,
        reducer_owned=False,
        canonical_route=_as_text(bundle.get("canonical_route")) or AWS_CSM_TOOL_ROUTE,
        canonical_query=_as_dict(bundle.get("canonical_query")),
        canonical_url=_as_text(bundle.get("canonical_url"))
        or build_canonical_url(surface_id=AWS_CSM_TOOL_SURFACE_ID, query=_as_dict(bundle.get("canonical_query"))),
        shell_state=_shell_state_payload(shell_state),
        surface_payload=_as_dict(bundle.get("surface_payload")),
        shell_composition=composition,
        warnings=[],
        error=None,
    )


def _action_result(
    *,
    action_kind: str,
    status: str,
    message: str,
    code: str = "",
    details: dict[str, Any] | None = None,
    ephemeral_secret: dict[str, Any] | None = None,
    created_profile: dict[str, Any] | None = None,
    handoff_dispatch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": AWS_CSM_ACTION_RESULT_SCHEMA,
        "action_kind": _as_text(action_kind),
        "status": _as_text(status) or "accepted",
        "code": _as_text(code),
        "message": _as_text(message),
        "details": dict(details or {}),
    }
    if isinstance(ephemeral_secret, dict) and ephemeral_secret:
        payload["ephemeral_secret"] = dict(ephemeral_secret)
    if isinstance(created_profile, dict) and created_profile:
        payload["created_profile"] = dict(created_profile)
    if isinstance(handoff_dispatch, dict) and handoff_dispatch:
        payload["handoff_dispatch"] = dict(handoff_dispatch)
    return payload


def _append_local_audit(
    *,
    audit_storage_file: str | Path | None,
    private_dir: str | Path | None,
    action_kind: str,
    details: dict[str, Any],
) -> None:
    if audit_storage_file is None:
        return
    focus_subject = _audit_focus_subject(private_dir)
    if not focus_subject:
        return
    try:
        LocalAuditService(FilesystemAuditLogAdapter(Path(audit_storage_file))).append_record(
            {
                "event_type": f"portal.aws_csm.{action_kind}.accepted",
                "focus_subject": focus_subject,
                "shell_verb": f"portal.aws_csm.{action_kind}",
                "details": dict(details),
            }
        )
    except Exception:
        return


def _selected_profile_row(
    *,
    tool_root: Path | None,
    surface_query: Mapping[str, Any],
    action_payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    profile_id = _as_text(action_payload.get("profile_id") or surface_query.get("profile"))
    if not profile_id:
        return None
    for row in _mailbox_profiles(tool_root):
        if _as_text(row.get("profile_id")) == profile_id:
            return row
    return None


def _selected_domain_record(
    *,
    tool_root: Path | None,
    surface_query: Mapping[str, Any],
    action_payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    store = _tool_store(tool_root)
    if store is None:
        return None
    requested_domain = _normalized_domain(action_payload.get("domain") or surface_query.get("domain"))
    if not requested_domain:
        return None
    payload = store.load_domain(domain=requested_domain)
    if payload is None:
        return None
    readiness = _project_domain_readiness(payload)
    identity = _as_dict(payload.get("identity"))
    return {
        "tenant_id": _as_text(identity.get("tenant_id")).lower(),
        "domain": requested_domain,
        "readiness_state": _as_text(readiness.get("state")),
        "raw": payload,
    }


def _domain_rule_name(domain: str) -> str:
    return f"portal-capture-{_slugify_domain(domain)}"


def _domain_seed_payload(action_payload: Mapping[str, Any]) -> dict[str, Any]:
    tenant_id = _as_text(action_payload.get("tenant_id")).lower()
    domain = _normalized_domain(action_payload.get("domain"))
    hosted_zone_id = _as_text(action_payload.get("hosted_zone_id")).upper()
    region = _as_text(action_payload.get("region")) or _DEFAULT_DOMAIN_REGION
    if not tenant_id or any(ch.isspace() for ch in tenant_id):
        raise ValueError("tenant_id must be a non-empty token")
    if not domain or "." not in domain or any(ch.isspace() for ch in domain):
        raise ValueError("domain must be a domain-like value")
    if not hosted_zone_id.startswith("Z"):
        raise ValueError("hosted_zone_id must look like a Route 53 hosted zone id")
    payload = {
        "schema": AWS_CSM_DOMAIN_SCHEMA,
        "identity": {
            "tenant_id": tenant_id,
            "domain": domain,
            "region": region,
            "hosted_zone_id": hosted_zone_id,
        },
        "dns": {
            "hosted_zone_present": False,
            "nameserver_match": False,
            "registrar_nameservers": [],
            "hosted_zone_nameservers": [],
            "mx_expected_value": f"10 inbound-smtp.{region}.amazonaws.com",
            "mx_record_present": False,
            "mx_record_values": [],
            "dkim_records_present": False,
            "dkim_record_values": [],
        },
        "ses": {
            "identity_exists": False,
            "identity_status": "not_started",
            "verified_for_sending_status": False,
            "dkim_status": "not_started",
            "dkim_tokens": [],
        },
        "receipt": {
            "status": "not_ready",
            "rule_name": _domain_rule_name(domain),
            "expected_recipient": domain,
            "expected_lambda_name": _DEFAULT_DOMAIN_INBOUND_LAMBDA,
            "bucket": _DEFAULT_DOMAIN_RECEIPT_BUCKET,
            "prefix": f"inbound/{domain}/",
        },
        "observation": {
            "last_checked_at": "",
            "account": "",
            "role_arn": "",
        },
    }
    payload["readiness"] = _project_domain_readiness(payload)
    return payload


def _merged_domain_payload(base_payload: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    working = deepcopy(base_payload)
    for section in ("identity", "dns", "ses", "receipt", "observation"):
        fragment = _as_dict(patch.get(section))
        if not fragment:
            continue
        merged = _as_dict(working.get(section))
        merged.update(fragment)
        working[section] = merged
    working["readiness"] = _project_domain_readiness(working)
    return working


def _refresh_domain_record(
    *,
    store: FilesystemAwsCsmToolProfileStore,
    domain_record: dict[str, Any],
    cloud: object,
) -> dict[str, Any]:
    if not hasattr(cloud, "describe_domain_status"):
        raise ValueError("AWS-backed domain status inspection is not configured in this runtime.")
    observed = getattr(cloud, "describe_domain_status")(domain_record)
    merged = _merged_domain_payload(domain_record, observed if isinstance(observed, Mapping) else {})
    return store.save_domain(
        domain=_normalized_domain(_as_dict(domain_record.get("identity")).get("domain")),
        payload=merged,
    )


def _onboarding_cloud(*, private_dir: str | Path | None, tenant_id: str) -> object:
    try:
        return AwsEc2RoleOnboardingCloudAdapter(private_dir=private_dir, tenant_id=tenant_id)
    except Exception:
        return AwsCsmOnboardingUnconfiguredCloudPort()


def _tenant_scope_for_profile(profile_row: dict[str, Any]) -> str:
    raw = _as_dict(profile_row.get("raw"))
    identity = _as_dict(raw.get("identity"))
    return (
        _as_text(identity.get("tenant_id"))
        or _as_text(identity.get("domain")).lower()
        or _as_text(identity.get("profile_id"))
    )


def _record_profile_handoff_event(
    *,
    store: FilesystemAwsCsmToolProfileStore,
    profile_row: dict[str, Any],
    status: str,
    field_name: str,
    field_value: object,
) -> dict[str, Any]:
    tenant_scope_id = _tenant_scope_for_profile(profile_row)
    working = deepcopy(_as_dict(profile_row.get("raw")))
    workflow = _as_dict(working.get("workflow"))
    workflow["handoff_status"] = status
    workflow[field_name] = field_value
    working["workflow"] = workflow
    return store.save_profile(
        tenant_scope_id=tenant_scope_id,
        profile_id=_as_text(profile_row.get("profile_id")),
        payload=working,
    )


def _route_sync_fail_closed() -> bool:
    token = _as_text(os.getenv(_ROUTE_SYNC_FAIL_CLOSED_ENV)).lower()
    return token in {"1", "true", "yes", "on"}


def _route_sync_manual_step(private_dir: str | Path | None) -> str:
    state_root = (
        Path(private_dir) / "utilities" / "tools" / "aws-csm"
        if private_dir is not None
        else Path("<private_dir>") / "utilities" / "tools" / "aws-csm"
    )
    return (
        f"python3 {_ROUTE_SYNC_FALLBACK_SCRIPT} --apply --state-root {state_root}"
    )


def _sync_verification_route_map(
    *,
    store: FilesystemAwsCsmToolProfileStore,
    cloud: object,
    private_dir: str | Path | None,
) -> dict[str, Any]:
    if not hasattr(cloud, "sync_verification_route_map"):
        return {
            "status": "skipped",
            "message": "Verification-forward route sync is not supported by this runtime cloud adapter.",
            "route_count": 0,
            "tracked_recipients": [],
            "lambda_name": "",
            "changed": False,
            "manual_step": _route_sync_manual_step(private_dir),
        }
    sync = getattr(cloud, "sync_verification_route_map")
    if not callable(sync):
        return {
            "status": "warning",
            "message": "Verification-forward route sync adapter entry is present but not callable.",
            "route_count": 0,
            "tracked_recipients": [],
            "lambda_name": "",
            "changed": False,
            "manual_step": _route_sync_manual_step(private_dir),
        }
    try:
        summary = sync(profiles=store.list_profiles())
    except Exception as exc:  # noqa: BLE001
        warning = (
            f"Verification-forward route sync failed: {_as_text(exc) or 'unknown error'}. "
            f"Fallback: {_route_sync_manual_step(private_dir)}"
        )
        if _route_sync_fail_closed():
            raise ValueError(warning)
        return {
            "status": "warning",
            "message": warning,
            "route_count": 0,
            "tracked_recipients": [],
            "lambda_name": "",
            "changed": False,
            "manual_step": _route_sync_manual_step(private_dir),
        }
    payload = _as_dict(summary)
    status = _as_text(payload.get("status")).lower() or "success"
    if status not in {"success", "warning", "failure", "skipped"}:
        status = "success"
    message = _as_text(payload.get("message")) or (
        "Verification-forward route sync completed."
        if status in {"success", "skipped"}
        else "Verification-forward route sync needs operator attention."
    )
    if status in {"warning", "failure"} and _route_sync_fail_closed():
        raise ValueError(message)
    return {
        "status": status,
        "message": message,
        "route_count": payload.get("route_count"),
        "tracked_recipients": list(payload.get("tracked_recipients") or []),
        "lambda_name": _as_text(payload.get("lambda_name")),
        "changed": _as_bool(payload.get("changed")),
        "manual_step": _as_text(payload.get("manual_step")) or _route_sync_manual_step(private_dir),
    }


def _merge_route_sync_details(details: dict[str, Any], route_sync: dict[str, Any] | None) -> None:
    payload = _as_dict(route_sync)
    if not payload:
        return
    details["route_sync_status"] = _as_text(payload.get("status")) or "unknown"
    details["route_sync_message"] = _as_text(payload.get("message"))
    details["route_sync_route_count"] = _as_text(payload.get("route_count"))
    details["route_sync_lambda_name"] = _as_text(payload.get("lambda_name"))
    details["route_sync_changed"] = "true" if _as_bool(payload.get("changed")) else "false"
    details["route_sync_tracked_recipients"] = ", ".join(
        _as_text(item) for item in _as_list(payload.get("tracked_recipients")) if _as_text(item)
    )
    details["route_sync_manual_step"] = _as_text(payload.get("manual_step"))


def _apply_action(
    *,
    portal_scope: PortalScope,
    surface_query: dict[str, str],
    action_kind: str,
    action_payload: dict[str, Any],
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    tool_root = _tool_root(private_dir)
    if tool_root is None:
        return surface_query, _action_result(
            action_kind=action_kind,
            status="error",
            code="aws_csm_state_root_missing",
            message="AWS-CSM tool state is not configured in this portal runtime.",
        )
    store = _tool_store(tool_root)
    if store is None:
        return surface_query, _action_result(
            action_kind=action_kind,
            status="error",
            code="aws_csm_store_unavailable",
            message="AWS-CSM profile storage is unavailable in this portal runtime.",
        )

    try:
        if action_kind == "create_domain":
            domain_payload = _domain_seed_payload(action_payload)
            tenant_id = _as_text(_as_dict(domain_payload.get("identity")).get("tenant_id")).lower()
            created_domain = store.create_domain(tenant_id=tenant_id, payload=domain_payload)
            cloud = _onboarding_cloud(private_dir=private_dir, tenant_id=tenant_id)
            refreshed_domain = _refresh_domain_record(store=store, domain_record=created_domain, cloud=cloud)
            readiness = _project_domain_readiness(refreshed_domain)
            domain = _normalized_domain(_as_dict(refreshed_domain.get("identity")).get("domain"))
            next_query = {"view": "domains", "domain": domain, "section": "onboarding"}
            details = {
                "tenant_id": tenant_id,
                "domain": domain,
                "hosted_zone_id": _as_text(_as_dict(refreshed_domain.get("identity")).get("hosted_zone_id")),
                "readiness_state": _as_text(readiness.get("state")),
            }
            _append_local_audit(
                audit_storage_file=audit_storage_file,
                private_dir=private_dir,
                action_kind=action_kind,
                details=details,
            )
            return next_query, _action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"Created AWS-CSM domain onboarding for {domain}.",
                details=details,
            )

        if action_kind in {
            "refresh_domain_status",
            "ensure_domain_identity",
            "sync_domain_dns",
            "ensure_domain_receipt_rule",
        }:
            domain_row = _selected_domain_record(
                tool_root=tool_root,
                surface_query=surface_query,
                action_payload=action_payload,
            )
            if domain_row is None:
                return surface_query, _action_result(
                    action_kind=action_kind,
                    status="error",
                    code="domain_required",
                    message="Select an AWS-CSM domain before running this action.",
                )
            tenant_id = _as_text(domain_row.get("tenant_id"))
            cloud = _onboarding_cloud(private_dir=private_dir, tenant_id=tenant_id)
            raw_domain = _as_dict(domain_row.get("raw"))
            if action_kind == "ensure_domain_identity":
                if not hasattr(cloud, "ensure_domain_identity"):
                    raise ValueError("AWS-backed domain identity creation is not configured in this runtime.")
                getattr(cloud, "ensure_domain_identity")(raw_domain)
            elif action_kind == "sync_domain_dns":
                if not hasattr(cloud, "sync_domain_dns"):
                    raise ValueError("AWS-backed domain DNS synchronization is not configured in this runtime.")
                getattr(cloud, "sync_domain_dns")(raw_domain)
            elif action_kind == "ensure_domain_receipt_rule":
                if not hasattr(cloud, "ensure_domain_receipt_rule"):
                    raise ValueError("AWS-backed domain receipt-rule wiring is not configured in this runtime.")
                getattr(cloud, "ensure_domain_receipt_rule")(raw_domain)
            refreshed_domain = _refresh_domain_record(store=store, domain_record=raw_domain, cloud=cloud)
            readiness = _project_domain_readiness(refreshed_domain)
            domain = _normalized_domain(_as_dict(refreshed_domain.get("identity")).get("domain"))
            next_query = {"view": "domains", "domain": domain, "section": "onboarding"}
            details = {
                "tenant_id": _as_text(_as_dict(refreshed_domain.get("identity")).get("tenant_id")),
                "domain": domain,
                "hosted_zone_id": _as_text(_as_dict(refreshed_domain.get("identity")).get("hosted_zone_id")),
                "readiness_state": _as_text(readiness.get("state")),
                "updated_sections": ["dns", "ses", "receipt", "observation", "readiness"],
            }
            _append_local_audit(
                audit_storage_file=audit_storage_file,
                private_dir=private_dir,
                action_kind=action_kind,
                details=details,
            )
            return next_query, _action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"AWS-CSM domain action {action_kind} completed for {domain}.",
                details=details,
            )

        if action_kind == "create_profile":
            outcome = AwsCsmProfileRegistryService(store).create_profile(action_payload)
            cloud = _onboarding_cloud(private_dir=private_dir, tenant_id=outcome.tenant_id)
            route_sync = _sync_verification_route_map(
                store=store,
                cloud=cloud,
                private_dir=private_dir,
            )
            next_query = {"view": "domains", "domain": outcome.domain, "profile": outcome.profile_id, "section": "onboarding"}
            details = {
                "profile_id": outcome.profile_id,
                "tenant_id": outcome.tenant_id,
                "domain": outcome.domain,
                "send_as_email": outcome.send_as_email,
                "single_user_email": outcome.single_user_email,
                "operator_inbox_target": outcome.operator_inbox_target,
            }
            _merge_route_sync_details(details, route_sync)
            message = f"Created draft AWS-CSM profile {outcome.profile_id}."
            if _as_text(route_sync.get("status")) in {"warning", "failure"}:
                message += " Verification-forward route sync needs operator attention."
            _append_local_audit(
                audit_storage_file=audit_storage_file,
                private_dir=private_dir,
                action_kind=action_kind,
                details=details,
            )
            return next_query, _action_result(
                action_kind=action_kind,
                status="accepted",
                message=message,
                details=details,
                created_profile=details,
            )

        profile_row = _selected_profile_row(
            tool_root=tool_root,
            surface_query=surface_query,
            action_payload=action_payload,
        )
        if profile_row is None:
            return surface_query, _action_result(
                action_kind=action_kind,
                status="error",
                code="profile_required",
                message="Select an AWS-CSM profile before running this action.",
            )
        tenant_scope_id = _tenant_scope_for_profile(profile_row)
        if not tenant_scope_id:
            return surface_query, _action_result(
                action_kind=action_kind,
                status="error",
                code="tenant_scope_missing",
                message="The selected AWS-CSM profile is missing tenant scope metadata.",
            )

        if action_kind in _SERVICE_ACTION_KINDS:
            focus_subject = _audit_focus_subject(private_dir)
            if not focus_subject:
                return surface_query, _action_result(
                    action_kind=action_kind,
                    status="error",
                    code="focus_subject_missing",
                    message="private/config.json must provide msn_id before AWS-CSM onboarding writes can run.",
                )
            cloud = _onboarding_cloud(private_dir=private_dir, tenant_id=tenant_scope_id)
            outcome = AwsCsmOnboardingService(profile_store=store, cloud=cloud).apply(
                {
                    "tenant_scope": {"scope_id": tenant_scope_id},
                    "focus_subject": focus_subject,
                    "profile_id": _as_text(profile_row.get("profile_id")),
                    "onboarding_action": action_kind,
                }
            )
            details = {
                "profile_id": _as_text(profile_row.get("profile_id")),
                "tenant_scope_id": tenant_scope_id,
                "updated_sections": list(outcome.updated_sections),
            }
            route_sync_message_suffix = ""
            if action_kind == "stage_smtp_credentials":
                route_sync = _sync_verification_route_map(
                    store=store,
                    cloud=cloud,
                    private_dir=private_dir,
                )
                _merge_route_sync_details(details, route_sync)
                if _as_text(route_sync.get("status")) in {"warning", "failure"}:
                    route_sync_message_suffix = " Verification-forward route sync needs operator attention."
            _append_local_audit(
                audit_storage_file=audit_storage_file,
                private_dir=private_dir,
                action_kind=action_kind,
                details=details,
            )
            return surface_query, _action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"AWS-CSM action {action_kind} completed for {_as_text(profile_row.get('profile_id'))}.{route_sync_message_suffix}",
                details=details,
            )

        cloud = _onboarding_cloud(private_dir=private_dir, tenant_id=tenant_scope_id)
        live_profile = store.load_profile(
            tenant_scope_id=tenant_scope_id,
            profile_id=_as_text(profile_row.get("profile_id")),
        )
        if live_profile is None:
            raise ValueError("AWS-CSM profile could not be reloaded for the requested action.")

        if action_kind == "send_handoff_email":
            dispatch = cloud.send_handoff_email(live_profile)
            _record_profile_handoff_event(
                store=store,
                profile_row=profile_row,
                status="instruction_sent",
                field_name="handoff_email_sent_to",
                field_value=_as_text(dispatch.get("sent_to")),
            )
            details = {
                "profile_id": _as_text(profile_row.get("profile_id")),
                "tenant_scope_id": tenant_scope_id,
                "send_as_email": _as_text(dispatch.get("send_as_email")),
                "sent_to": _as_text(dispatch.get("sent_to")),
                "message_id": _as_text(dispatch.get("message_id")),
            }
            _append_local_audit(
                audit_storage_file=audit_storage_file,
                private_dir=private_dir,
                action_kind=action_kind,
                details=details,
            )
            return surface_query, _action_result(
                action_kind=action_kind,
                status="accepted",
                message=f"Sent Gmail handoff instructions to {_as_text(dispatch.get('sent_to'))}.",
                details=details,
                handoff_dispatch=dispatch,
            )

        if action_kind == "reveal_smtp_password":
            secret = cloud.read_handoff_secret(live_profile)
            _record_profile_handoff_event(
                store=store,
                profile_row=profile_row,
                status="secret_revealed",
                field_name="handoff_secret_revealed_to",
                field_value=_as_text(
                    _as_dict(live_profile.get("smtp")).get("forward_to_email")
                    or _as_dict(live_profile.get("identity")).get("operator_inbox_target")
                ),
            )
            details = {
                "profile_id": _as_text(profile_row.get("profile_id")),
                "tenant_scope_id": tenant_scope_id,
                "send_as_email": _as_text(secret.get("send_as_email")),
                "secret_name": _as_text(secret.get("secret_name")),
                "state": _as_text(secret.get("state")),
            }
            _append_local_audit(
                audit_storage_file=audit_storage_file,
                private_dir=private_dir,
                action_kind=action_kind,
                details=details,
            )
            return surface_query, _action_result(
                action_kind=action_kind,
                status="accepted",
                message="Ephemeral SMTP credentials were revealed for operator-only handoff.",
                details=details,
                ephemeral_secret=secret,
            )

        return surface_query, _action_result(
            action_kind=action_kind,
            status="error",
            code="action_unhandled",
            message=f"AWS-CSM action {action_kind} is not implemented.",
        )
    except AwsCsmOnboardingPolicyError as exc:
        return surface_query, _action_result(
            action_kind=action_kind,
            status="error",
            code=_as_text(getattr(exc, "code", "")) or "policy_error",
            message=str(exc),
        )
    except ValueError as exc:
        return surface_query, _action_result(
            action_kind=action_kind,
            status="error",
            code="action_failed",
            message=str(exc),
        )
    except Exception as exc:
        return surface_query, _action_result(
            action_kind=action_kind,
            status="error",
            code="action_failed",
            message=_as_text(exc) or "The AWS-CSM action could not be completed.",
        )


def run_portal_aws_csm(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, query = _normalize_request(request_payload)
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_CSM_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=None,
        surface_query=query,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
    )
    return _runtime_envelope_from_bundle(
        bundle=bundle,
        portal_scope=portal_scope,
        requested_surface_id=AWS_CSM_TOOL_SURFACE_ID,
        entrypoint_id=AWS_CSM_TOOL_ENTRYPOINT_ID,
        read_write_posture="read-only",
    )


def run_portal_aws_csm_action(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    audit_storage_file: str | Path | None = None,
) -> dict[str, Any]:
    portal_scope, surface_query, shell_state, action_kind, action_payload = _normalize_action_request(
        request_payload
    )
    next_query, action_result = _apply_action(
        portal_scope=portal_scope,
        surface_query=surface_query,
        action_kind=action_kind,
        action_payload=action_payload,
        private_dir=private_dir,
        audit_storage_file=audit_storage_file,
    )
    bundle = build_portal_aws_surface_bundle(
        surface_id=AWS_CSM_TOOL_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_query=next_query,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
        action_result=action_result,
    )
    return _runtime_envelope_from_bundle(
        bundle=bundle,
        portal_scope=portal_scope,
        requested_surface_id=AWS_CSM_TOOL_SURFACE_ID,
        entrypoint_id=AWS_CSM_TOOL_ACTION_ENTRYPOINT_ID,
        read_write_posture="write",
    )


__all__ = [
    "AWS_CSM_ACTION_RESULT_SCHEMA",
    "AWS_CSM_TOOL_ACTION_ENTRYPOINT_ID",
    "AWS_CSM_TOOL_ACTION_ROUTE",
    "AWS_TOOL_STATUS_SCHEMA",
    "build_portal_aws_surface_bundle",
    "run_portal_aws_csm",
    "run_portal_aws_csm_action",
]
