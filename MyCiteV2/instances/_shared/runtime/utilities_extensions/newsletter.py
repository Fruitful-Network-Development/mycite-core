"""ext_newsletter — contact log + sender configuration for the grantee.

Reads the contact log and newsletter sender profile for the domain.
When ``authority_db_file`` is provided, the contact log is sourced from
the MOS v2 datum (``fnd_newsletter_contact_log_<domain>``). Profile
reads stay on the filesystem adapter regardless.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemAwsCsmNewsletterStateAdapter

from ._shared import _as_dict, _as_list, _as_text, _grantee_edit_link


def _build_newsletter_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
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


def _render_ext_newsletter(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_newsletter_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = ["_build_newsletter_extension_payload", "_render_ext_newsletter"]
