from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    AWS_CSM_TOOL_REQUEST_SCHEMA,
    AWS_CSM_TOOL_SURFACE_SCHEMA,
    build_portal_runtime_envelope,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_ENTRYPOINT_ID,
    AWS_CSM_TOOL_ROUTE,
    AWS_CSM_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PORTAL_SHELL_REQUEST_SCHEMA,
    PortalScope,
    build_canonical_url,
    resolve_portal_tool_registry_entry,
)

AWS_TOOL_STATUS_SCHEMA = "mycite.v2.portal.system.tools.aws_csm.status.v1"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


def _tool_root(private_dir: str | Path | None) -> Path | None:
    if private_dir is None:
        return None
    root = Path(private_dir) / "utilities" / "tools" / "aws-csm"
    return root if root.exists() and root.is_dir() else None


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
                "mailbox_local_part": mailbox_local_part or send_as_email.split("@", 1)[0] if "@" in send_as_email else mailbox_local_part,
                "send_as_email": send_as_email,
                "user_email": user_email,
                "role": _as_text(identity.get("role")) or _as_text(identity.get("profile_kind")) or "mailbox",
                "workflow_state": _as_text(workflow.get("lifecycle_state")) or "unknown",
                "verification_state": _as_text(verification.get("portal_state") or verification.get("status")) or "unknown",
                "provider_state": _as_text(provider.get("gmail_send_as_status") or provider.get("aws_ses_identity_status")) or "unknown",
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
    mailbox_profiles = _mailbox_profiles(tool_root)
    newsletter_domains = _newsletter_domains(tool_root)

    newsletter_by_domain = {item["domain"]: item for item in newsletter_domains}
    profiles_by_id = {item["profile_id"]: item for item in mailbox_profiles}
    domain_map: dict[str, dict[str, Any]] = {}
    for profile in mailbox_profiles:
        domain_row = domain_map.setdefault(
            profile["domain"],
            {"domain": profile["domain"], "mailboxes": [], "newsletter": newsletter_by_domain.get(profile["domain"])},
        )
        domain_row["mailboxes"].append(profile)
    for newsletter in newsletter_domains:
        domain_row = domain_map.setdefault(
            newsletter["domain"],
            {"domain": newsletter["domain"], "mailboxes": [], "newsletter": newsletter},
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
        for token, label in (
            ("users", "Users"),
            ("onboarding", "Onboarding"),
            ("newsletter", "Newsletter"),
        ):
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
        "selected_profile": selected_profile,
        "selected_newsletter": selected_newsletter,
        "domain_count": len(domain_rows),
        "profile_count": len(mailbox_profiles),
        "newsletter_domain_count": len(newsletter_domains),
        "contact_count": total_contact_count,
    }
    return workspace, resolved_query


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
    section_rows = list(workspace.get("section_rows") or [])
    if section_rows:
        groups.append({"title": "Sections", "entries": section_rows})
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
                {"title": "Profile", "rows": _facts_rows([("domain", identity.get("domain")), ("send-as", identity.get("send_as_email")), ("user", identity.get("single_user_email")), ("role", identity.get("role"))])},
                {"title": "Onboarding", "rows": _facts_rows([("workflow", workflow.get("lifecycle_state")), ("handoff", workflow.get("handoff_status")), ("verification", verification.get("portal_state") or verification.get("status")), ("provider", provider.get("gmail_send_as_status") or provider.get("aws_ses_identity_status")), ("inbound", inbound.get("receive_state"))])},
                {"title": "SMTP and Inbound", "rows": _facts_rows([("forward target", smtp.get("forward_to_email")), ("credentials", smtp.get("credentials_secret_state")), ("receive verified", inbound.get("receive_verified")), ("capture source", inbound.get("capture_source_kind"))])},
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


def build_portal_aws_surface_bundle(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: object | None,
    surface_query: Mapping[str, Any] | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del shell_state
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
    surface_payload = {
        "schema": AWS_CSM_TOOL_SURFACE_SCHEMA,
        "kind": "aws_csm_workspace",
        "title": "AWS-CSM",
        "subtitle": "Unified domain gallery with mailbox onboarding and newsletter state.",
        "tool": tool_status,
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
    inspector = _build_inspector(tool_status=tool_status, workspace=workspace, surface_payload=surface_payload)
    return {
        "entrypoint_id": AWS_CSM_TOOL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": "AWS-CSM",
        "page_subtitle": "Unified domain gallery and FND-routed service-tool posture.",
        "surface_payload": surface_payload,
        "control_panel": _build_control_panel(portal_scope=portal_scope, workspace=workspace),
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
    }


def run_portal_aws_csm(
    request_payload: dict[str, Any] | None,
    *,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portal_scope, query = _normalize_request(request_payload)
    tool_root = _tool_root(private_dir)
    tool_status = _tool_status(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        tool_root=tool_root,
    )
    workspace, canonical_query = _workspace(
        portal_scope=portal_scope,
        query=query,
        tool_root=tool_root,
    )
    surface_payload = {
        "schema": AWS_CSM_TOOL_SURFACE_SCHEMA,
        "kind": "aws_csm_workspace",
        "title": "AWS-CSM",
        "subtitle": "Unified domain gallery with mailbox onboarding and newsletter state.",
        "tool": tool_status,
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
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=AWS_CSM_TOOL_SURFACE_ID,
        surface_id=AWS_CSM_TOOL_SURFACE_ID,
        entrypoint_id=AWS_CSM_TOOL_ENTRYPOINT_ID,
        read_write_posture="read-only",
        reducer_owned=False,
        canonical_route=AWS_CSM_TOOL_ROUTE,
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=AWS_CSM_TOOL_SURFACE_ID, query=canonical_query),
        shell_state=None,
        surface_payload=surface_payload,
        shell_composition={},
        warnings=[],
        error=None,
    )


__all__ = [
    "AWS_TOOL_STATUS_SCHEMA",
    "build_portal_aws_surface_bundle",
    "run_portal_aws_csm",
]
