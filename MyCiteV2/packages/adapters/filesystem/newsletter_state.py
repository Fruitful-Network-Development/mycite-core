from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

_log = logging.getLogger("mycite.portal_host")

from MyCiteV2.packages.adapters.filesystem.contact_leaflet import (
    ContactLeafletStore,
    entity_for_domain,
)
from MyCiteV2.packages.ports.newsletter import (
    _ACCEPTED_NEWSLETTER_CONTACT_LOG_SCHEMAS,
    _ACCEPTED_NEWSLETTER_PROFILE_SCHEMAS,
    NEWSLETTER_CONTACT_LOG_SCHEMA,
    NEWSLETTER_PROFILE_SCHEMA,
    NewsletterStatePort,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized_domain(value: object) -> str:
    token = _as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def _optional_email(value: object) -> str:
    token = _as_text(value).lower()
    if not token or token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning(
            "newsletter_state_json_parse_failed path=%s", path, exc_info=True
        )
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically (temp file in the same dir + os.replace).

    Newsletter contact logs are written from several concurrent paths
    (public subscribe/connect, operator edits, dispatch callbacks); a torn
    file would read back as ``{}`` and silently drop the whole list, so the
    write must be all-or-nothing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class FilesystemNewsletterStateAdapter(NewsletterStatePort):
    def __init__(
        self,
        private_dir: str | Path,
        *,
        webapps_root: str | Path | None = None,
    ) -> None:
        self._private_dir = Path(private_dir)
        self._aws_root = self._private_dir / "utilities" / "tools" / "aws-csm"
        self._newsletter_root = self._aws_root / "newsletter"
        self._runtime_secrets_path = self._newsletter_root / "runtime_secrets.json"
        # Roster (contacts[]) lives in a per-entity YAML leaflet; this JSON
        # adapter only owns dispatch-send history (dispatches[]) + the per-domain
        # profile. load_contact_log composes the two stores back into one view.
        self._leaflet = ContactLeafletStore(
            private_dir=self._private_dir, webapps_root=webapps_root
        )

    def list_newsletter_domains(self) -> list[str]:
        domains: set[str] = set()
        if self._newsletter_root.exists():
            for path in sorted(self._newsletter_root.glob("newsletter.*.profile.json")):
                token = path.name.removeprefix("newsletter.").removesuffix(".profile.json").strip().lower()
                if token:
                    domains.add(token)
        for profile in self._verified_profiles():
            token = _normalized_domain(profile.get("domain"))
            if token:
                domains.add(token)
        return sorted(domains)

    def ensure_domain_bootstrap(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
        unsubscribe_secret_name: str,
        dispatch_callback_secret_name: str,
        inbound_callback_secret_name: str,
        inbound_processor_lambda_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        token = _normalized_domain(domain)
        profile = self.load_profile(domain=token)
        if _as_text(profile.get("schema")) not in _ACCEPTED_NEWSLETTER_PROFILE_SCHEMAS:
            profile = self._bootstrap_profile(
                domain=token,
                dispatcher_callback_url=dispatcher_callback_url,
                inbound_callback_url=inbound_callback_url,
                unsubscribe_secret_name=unsubscribe_secret_name,
                dispatch_callback_secret_name=dispatch_callback_secret_name,
                inbound_callback_secret_name=inbound_callback_secret_name,
                inbound_processor_lambda_name=inbound_processor_lambda_name,
            )
            self.save_profile(domain=token, payload=profile)
        else:
            profile["callback_url"] = dispatcher_callback_url
            profile["inbound_callback_url"] = inbound_callback_url
            profile["unsubscribe_secret_name"] = unsubscribe_secret_name
            profile["dispatch_callback_secret_name"] = dispatch_callback_secret_name
            profile["inbound_callback_secret_name"] = inbound_callback_secret_name
            profile["inbound_processor_lambda_name"] = inbound_processor_lambda_name
            self.save_profile(domain=token, payload=profile)

        contact_log = self.load_contact_log(domain=token)
        if _as_text(contact_log.get("schema")) not in _ACCEPTED_NEWSLETTER_CONTACT_LOG_SCHEMAS:
            contact_log = self._bootstrap_contact_log(domain=token)
            self.save_contact_log(domain=token, payload=contact_log)
        return self.load_profile(domain=token), self.load_contact_log(domain=token)

    def list_verified_author_profiles(self, *, domain: str) -> list[dict[str, Any]]:
        token = _normalized_domain(domain)
        profiles = [profile for profile in self._verified_profiles() if _normalized_domain(profile.get("domain")) == token]
        profiles.sort(
            key=lambda item: (
                0 if _as_text(item.get("mailbox_local_part")).lower() == "admin" else 1,
                _as_text(item.get("send_as_email")).lower(),
            )
        )
        return profiles

    def load_profile(self, *, domain: str) -> dict[str, Any]:
        payload = _read_json(self._profile_path(domain))
        if _as_text(payload.get("schema")) not in _ACCEPTED_NEWSLETTER_PROFILE_SCHEMAS:
            return {}
        return dict(payload)

    def save_profile(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = _normalized_domain(domain)
        body = dict(payload if isinstance(payload, dict) else {})
        body["schema"] = NEWSLETTER_PROFILE_SCHEMA
        body["domain"] = token
        body["list_address"] = f"news@{token}"
        body["sender_address"] = f"news@{token}"
        body["selected_author_profile_id"] = _as_text(body.get("selected_author_profile_id"))
        body["selected_author_address"] = _optional_email(body.get("selected_author_address"))
        body["delivery_mode"] = _as_text(body.get("delivery_mode")) or "inbound-mail-workflow"
        body["aws_region"] = _as_text(body.get("aws_region")) or "us-east-1"
        body["callback_url"] = _as_text(body.get("callback_url"))
        body["inbound_callback_url"] = _as_text(body.get("inbound_callback_url"))
        body["dispatcher_lambda_name"] = _as_text(body.get("dispatcher_lambda_name")) or "newsletter-dispatcher"
        body["inbound_processor_lambda_name"] = _as_text(body.get("inbound_processor_lambda_name")) or "newsletter-inbound-capture"
        body["unsubscribe_secret_name"] = _as_text(body.get("unsubscribe_secret_name"))
        body["dispatch_callback_secret_name"] = _as_text(body.get("dispatch_callback_secret_name"))
        body["inbound_callback_secret_name"] = _as_text(body.get("inbound_callback_secret_name"))
        body["updated_at"] = _as_text(body.get("updated_at")) or ""
        body["signature"] = _as_text(body.get("signature"))[:4000]
        _write_json(self._profile_path(token), body)
        return body

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        """Composed view: dispatch history from the legacy JSON log + the
        contact ROSTER from the per-entity YAML leaflet.

        The roster lives in a single leaflet per entity (an entity may own
        several domains), so the contacts returned here are scoped to this
        domain — only rows whose ``domain`` matches (rows missing a ``domain``
        are treated as belonging to the requested domain for back-compat).
        Callers keep seeing the historical ``{schema, domain, contacts[],
        dispatches[]}`` shape, so none of them change.
        """
        token = _normalized_domain(domain)
        json_payload = _read_json(self._contacts_path(token))
        json_ok = (
            _as_text(json_payload.get("schema"))
            in _ACCEPTED_NEWSLETTER_CONTACT_LOG_SCHEMAS
        )
        contacts = self._roster_for_domain(token)
        leaflet_present = self._leaflet.leaflet_present(entity_for_domain(token))
        # Empty when neither store holds anything for the domain — preserves the
        # historical "no log yet" sentinel that write paths key off of.
        if not json_ok and not leaflet_present and not contacts:
            return {}
        dispatches = list(json_payload.get("dispatches") or []) if json_ok else []
        return {
            "schema": NEWSLETTER_CONTACT_LOG_SCHEMA,
            "domain": token,
            "contacts": contacts,
            "dispatches": dispatches,
            "updated_at": _as_text(json_payload.get("updated_at")),
        }

    def contact_log_present(self, *, domain: str) -> bool:
        """True when a contact roster already exists for the domain's entity.

        Lets a write path distinguish "no roster yet" (safe to create fresh)
        from "a roster file exists but didn't load" (parse error / schema drift)
        so it never silently overwrites and drops existing contacts. Tracks the
        YAML leaflet — the store that now owns the roster — OR the legacy JSON
        contact log (so an un-migrated domain is still protected).
        """
        if self._leaflet.leaflet_present(entity_for_domain(_normalized_domain(domain))):
            return True
        path = self._contacts_path(domain)
        return path.exists() and path.is_file()

    def _roster_for_domain(self, domain: str) -> list[dict[str, Any]]:
        """Contacts in this domain's entity leaflet, scoped to the domain."""
        token = _normalized_domain(domain)
        entity = entity_for_domain(token)
        rows: list[dict[str, Any]] = []
        for row in self._leaflet.load_roster(entity):
            row_domain = _normalized_domain(row.get("domain"))
            # Rows missing a domain (legacy) belong to the requested domain.
            if row_domain and row_domain != token:
                continue
            rows.append(dict(row))
        return rows

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Split-write: ROSTER (contacts[]) -> per-entity YAML leaflet;
        DISPATCH history (dispatches[]) + profile metadata -> legacy JSON.

        Callers still hand us the whole composed ``{contacts, dispatches}``
        dict; we route each half to the store that owns it. The returned dict
        is the same composed shape (re-read so it reflects what was persisted).
        """
        token = _normalized_domain(domain)
        body = dict(payload if isinstance(payload, dict) else {})
        contacts = list(body.get("contacts") or [])

        # 1. Roster -> YAML leaflet. Merge into the entity's existing roster so a
        #    save scoped to ONE domain never drops a sibling domain's contacts
        #    (an entity may own several). Every persisted row carries its domain.
        entity = entity_for_domain(token)
        merged = self._merge_roster(token, entity, contacts)
        self._leaflet.save_roster(entity, merged)

        # 2. Dispatch history + metadata -> JSON. Strip contacts so the roster
        #    has exactly one home; keep an empty list for shape continuity.
        json_body = dict(body)
        json_body["schema"] = NEWSLETTER_CONTACT_LOG_SCHEMA
        json_body["domain"] = token
        json_body["contacts"] = []
        # Preserve full dispatch history — a write must never drop dispatch
        # records as a side effect.
        json_body["dispatches"] = list(body.get("dispatches") or [])
        _write_json(self._contacts_path(token), json_body)

        return self.load_contact_log(domain=token)

    def _merge_roster(
        self, domain: str, entity: str, incoming: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Replace this domain's slice of the entity roster with ``incoming``.

        Other domains' contacts in the same entity leaflet are preserved
        untouched; the incoming rows are stamped with this domain.
        """
        token = _normalized_domain(domain)
        kept: list[dict[str, Any]] = []
        for row in self._leaflet.load_roster(entity):
            row_domain = _normalized_domain(row.get("domain"))
            # Keep only OTHER domains' rows; this domain's slice is replaced.
            if row_domain and row_domain != token:
                kept.append(dict(row))
        for row in incoming:
            if not isinstance(row, dict):
                continue
            stamped = dict(row)
            stamped["domain"] = token
            kept.append(stamped)
        return kept

    def runtime_secret_seed(self, *, secret_kind: str) -> str:
        payload = _read_json(self._runtime_secrets_path)
        if secret_kind == "signing_secret":
            return _as_text(payload.get("signing_secret"))
        if secret_kind == "dispatch_secret":
            return _as_text(payload.get("dispatch_secret"))
        if secret_kind == "inbound_secret":
            return _as_text(payload.get("inbound_secret"))
        return ""

    def _profile_path(self, domain: str) -> Path:
        token = _normalized_domain(domain)
        return self._newsletter_root / f"newsletter.{token}.profile.json"

    def _contacts_path(self, domain: str) -> Path:
        token = _normalized_domain(domain)
        return self._newsletter_root / f"newsletter.{token}.contacts.json"

    def _bootstrap_profile(
        self,
        *,
        domain: str,
        dispatcher_callback_url: str,
        inbound_callback_url: str,
        unsubscribe_secret_name: str,
        dispatch_callback_secret_name: str,
        inbound_callback_secret_name: str,
        inbound_processor_lambda_name: str,
    ) -> dict[str, Any]:
        token = _normalized_domain(domain)
        verified = self.list_verified_author_profiles(domain=token)
        selected = next(
            (item for item in verified if _as_text(item.get("profile_id"))),
            None,
        )
        if selected is None and verified:
            selected = verified[0]
        return {
            "schema": NEWSLETTER_PROFILE_SCHEMA,
            "domain": token,
            "list_address": f"news@{token}",
            "sender_address": f"news@{token}",
            "selected_author_profile_id": _as_text(
                (selected or {}).get("profile_id")
            ),
            "selected_author_address": _optional_email(
                (selected or {}).get("send_as_email")
            ),
            "delivery_mode": "inbound-mail-workflow",
            "aws_region": "us-east-1",
            "signature": "",
            "dispatch_queue_url": "",
            "dispatch_queue_arn": "",
            "dispatcher_lambda_name": "newsletter-dispatcher",
            "inbound_processor_lambda_name": inbound_processor_lambda_name,
            "callback_url": dispatcher_callback_url,
            "inbound_callback_url": inbound_callback_url,
            "unsubscribe_secret_name": unsubscribe_secret_name,
            "dispatch_callback_secret_name": dispatch_callback_secret_name,
            "inbound_callback_secret_name": inbound_callback_secret_name,
            "last_inbound_message_id": "",
            "last_inbound_status": "",
            "last_inbound_checked_at": "",
            "last_inbound_processed_at": "",
            "last_inbound_subject": "",
            "last_inbound_sender": "",
            "last_inbound_recipient": "",
            "last_inbound_error": "",
            "last_inbound_s3_uri": "",
            "last_dispatch_id": "",
            "updated_at": "",
        }

    def _bootstrap_contact_log(self, *, domain: str) -> dict[str, Any]:
        token = _normalized_domain(domain)
        return {
            "schema": NEWSLETTER_CONTACT_LOG_SCHEMA,
            "domain": token,
            "contacts": [],
            "dispatches": [],
            "updated_at": "",
        }

    def _verified_profiles(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self._aws_root.exists():
            return out
        for path in sorted(self._aws_root.glob("aws-csm.*.json")):
            payload = _read_json(path)
            if _as_text(payload.get("schema")) != "mycite.service_tool.aws.profile.v2":
                continue
            identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
            verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
            provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
            workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
            if _as_text(verification.get("status")).lower() != "verified":
                continue
            provider_status = _as_text(provider.get("send_as_provider_status")).lower()
            if not provider_status:
                provider_status = _as_text(provider.get("gmail_send_as_status")).lower()
            if provider_status != "verified":
                continue
            if not bool(workflow.get("is_send_as_confirmed") or workflow.get("is_mailbox_operational")):
                continue
            send_as_email = _optional_email(identity.get("send_as_email"))
            domain = _normalized_domain(identity.get("domain"))
            if not send_as_email or not domain:
                continue
            out.append(
                {
                    "profile_id": _as_text(identity.get("profile_id")),
                    "domain": domain,
                    "send_as_email": send_as_email,
                    "mailbox_local_part": _as_text(identity.get("mailbox_local_part")),
                    "role": _as_text(identity.get("role")),
                    "operator_inbox_target": _optional_email(
                        identity.get("operator_inbox_target") or identity.get("single_user_email")
                    ),
                }
            )
        return out
