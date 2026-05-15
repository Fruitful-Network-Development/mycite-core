"""ext_aws_email — AWS SES configuration + mailbox visibility.

Reads AWS-CSM tool profiles for the selected domain and surfaces them
alongside the grantee's ``aws_ses`` sub-config. When an authority DB is
provided the profile + domain reads come from MOS via
``MosDatumAwsCsmProfileAdapter``; otherwise it falls back to the legacy
filesystem store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemAwsCsmToolProfileStore

from ._shared import _as_dict, _as_text, _grantee_edit_link, _mask_secret


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

    # Canonical AWS-CSM profile layout is
    # ``<private>/utilities/tools/aws-csm/aws-csm.<scope>.<mailbox>.json``;
    # the store globs ``aws-csm.*.json`` directly in its ``tool_root`` so
    # we must point at the aws-csm subdirectory, not at ``private``.
    aws_csm_root = Path(private_dir) / "utilities" / "tools" / "aws-csm"
    fs_store = FilesystemAwsCsmToolProfileStore(aws_csm_root)

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
            profile_id = _as_text(ident.get("profile_id"))
            lifecycle = _as_text(
                _as_dict(payload.get("workflow")).get("lifecycle_state")
            )
            profiles.append({
                "profile_id": profile_id,
                "mailbox": _as_text(ident.get("mailbox_local_part")),
                "send_as": _as_text(ident.get("send_as_email")),
                "role": _as_text(ident.get("role")),
                "lifecycle": lifecycle,
                "inbound": _as_text(
                    _as_dict(payload.get("inbound")).get("receive_state")
                ),
                "suspend_action": _suspend_action_for_profile(profile_id, lifecycle),
            })
    except Exception:
        pass
    return {
        "domain": domain,
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


def _render_ext_aws_email(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_email_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = ["_build_email_extension_payload", "_render_ext_aws_email"]
