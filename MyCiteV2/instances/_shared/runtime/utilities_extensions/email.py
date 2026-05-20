"""ext_email — AWS SES configuration + mailbox visibility (Email extension).

Reads operator profiles via the AWS peripheral's `ProfileStore` and
surfaces them alongside the grantee's ``aws_ses`` sub-config. Lists
every mailbox across every domain the active grantee owns; per-mailbox
domain is one column in the resulting table.

Architecture: this extension imports only from the AWS peripheral
(`peripherals.aws.ProfileStore`) and never reaches into another
extension. Per-grantee profile state lives in JSON files under
`deployed/<grantee>/private/utilities/tools/aws-csm/aws-csm.*.json`;
no MOS authority is consulted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.peripherals.aws import ProfileStore

from ._shared import _as_dict, _as_list, _as_text, _grantee_edit_link, _mask_secret


def _build_email_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
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

    # Phase 16c: take the union of the grantee's registered domains
    # AND the currently-selected ``domain`` (in case the operator
    # picked a domain that isn't in the grantee list yet). Lowercased
    # for case-insensitive identity matching downstream.
    grantee_domains = {
        _as_text(d).lower() for d in _as_list(grantee.get("domains")) if _as_text(d)
    }
    if domain:
        grantee_domains.add(domain.lower())
    if not grantee_domains or private_dir is None:
        return {"profiles": [], "domain": domain, "configuration": configuration}

    # Profiles live as JSON files at
    # ``<private>/utilities/tools/aws-csm/aws-csm.<scope>.<mailbox>.json``;
    # `ProfileStore` globs `aws-csm.*.json` under that root. No MOS.
    tool_root = Path(private_dir) / "utilities" / "tools" / "aws-csm"
    store = ProfileStore(root=tool_root)

    # The configuration block uses the active domain's record (when
    # available) so SES identity / region / SMTP creds shown above
    # reflect the operator's primary domain. The profiles list below
    # spans ALL of the grantee's domains.
    domain_record: dict[str, Any] = {}
    if domain:
        try:
            domain_record = _as_dict(store.get_domain(domain))
        except Exception:
            domain_record = {}

    profiles: list[dict[str, Any]] = []
    try:
        operator_source = store.list_profiles()
        for payload in operator_source:
            ident = _as_dict(payload.get("identity"))
            profile_domain = _as_text(ident.get("domain")).lower()
            if profile_domain not in grantee_domains:
                continue
            profile_id = _as_text(ident.get("profile_id"))
            lifecycle = _as_text(
                _as_dict(payload.get("workflow")).get("lifecycle_state")
            )
            workflow = _as_dict(payload.get("workflow"))
            inbox_target = _as_text(ident.get("operator_inbox_target"))
            profiles.append({
                "profile_id": profile_id,
                "domain": profile_domain,
                "mailbox": _as_text(ident.get("mailbox_local_part")),
                "send_as": _as_text(ident.get("send_as_email")),
                "role": _as_text(ident.get("role")),
                "lifecycle": lifecycle,
                "inbound": _as_text(
                    _as_dict(payload.get("inbound")).get("receive_state")
                ),
                "suspend_action": _suspend_action_for_profile(profile_id, lifecycle),
                "resend_handoff_action": _resend_handoff_action_for_profile(
                    profile_id, lifecycle, inbox_target
                ),
                "handoff_email_sent_at": _as_text(workflow.get("handoff_email_sent_at")),
            })
        # Stable ordering: by domain, then mailbox local part — keeps
        # cvcc.admin / cvcc.finance / cvccboard.daniel / etc. grouped
        # so the operator can scan the table predictably.
        profiles.sort(key=lambda r: (r["domain"], r["mailbox"]))
    except Exception:
        pass
    return {
        "domain": domain,
        "domains": sorted(grantee_domains),
        "profiles": profiles,
        "domain_record": domain_record,
        "configuration": configuration,
    }


def _suspend_action_for_profile(profile_id: str, lifecycle: str) -> dict[str, Any]:
    """Per-row toggle button. Suspended rows resume to ``operational``;
    everything else (``operational``, empty, etc.) becomes ``suspended``.
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    is_suspended = lifecycle.lower() == "suspended"
    if is_suspended:
        return {
            "label": "Resume",
            "route": "/__fnd/email/admin/suspend",
            "schema": "mycite.v2.email.admin.suspend.request.v1",
            "payload": {"profile_id": profile_id, "suspended": False},
            "variant": "secondary",
        }
    return {
        "label": "Suspend",
        "route": "/__fnd/email/admin/suspend",
        "schema": "mycite.v2.email.admin.suspend.request.v1",
        "payload": {"profile_id": profile_id, "suspended": True},
        "confirm": f"Suspend mailbox {profile_id}?",
        "variant": "danger",
    }


def _resend_handoff_action_for_profile(
    profile_id: str, lifecycle: str, inbox_target: str
) -> dict[str, Any]:
    """Per-row "Resend handoff" button.

    Visible only while the mailbox is still in draft / instruction_sent
    state — i.e. lifecycle is empty or ``draft``. Operational and
    suspended rows do not need a resend.
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    state = _as_text(lifecycle).lower()
    if state in {"operational", "suspended"}:
        return {}
    target_label = _as_text(inbox_target) or "the configured inbox"
    return {
        "label": "Resend handoff",
        "route": "/__fnd/email/admin/resend-handoff",
        "schema": "mycite.v2.email.admin.resend_handoff.request.v1",
        "payload": {"profile_id": profile_id},
        "confirm": f"Resend handoff email for {profile_id} to {target_label}?",
        "variant": "secondary",
    }


def _render_ext_aws_email(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_email_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = [
    "_build_email_extension_payload",
    "_render_ext_aws_email",
    "_resend_handoff_action_for_profile",
]
