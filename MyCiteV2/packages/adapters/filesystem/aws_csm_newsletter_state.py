from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.ports.aws_csm_newsletter import (
    AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
    AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
    AwsCsmNewsletterStatePort,
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
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class FilesystemAwsCsmNewsletterStateAdapter(AwsCsmNewsletterStatePort):
    def __init__(self, private_dir: str | Path) -> None:
        self._private_dir = Path(private_dir)
        self._aws_root = self._private_dir / "utilities" / "tools" / "aws-csm"
        self._newsletter_root = self._aws_root / "newsletter"
        self._runtime_secrets_path = self._newsletter_root / "runtime_secrets.json"

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
        if _as_text(profile.get("schema")) != AWS_CSM_NEWSLETTER_PROFILE_SCHEMA:
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
        if _as_text(contact_log.get("schema")) != AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA:
            contact_log = self._bootstrap_contact_log(domain=token)
            self.save_contact_log(domain=token, payload=contact_log)
        return self.load_profile(domain=token), self.load_contact_log(domain=token)

    def list_verified_author_profiles(self, *, domain: str) -> list[dict[str, Any]]:
        token = _normalized_domain(domain)
        profiles = [profile for profile in self._verified_profiles() if _normalized_domain(profile.get("domain")) == token]
        profiles.sort(
            key=lambda item: (
                0 if _as_text(item.get("mailbox_local_part")).lower() == "technicalcontact" else 1,
                0 if _as_text(item.get("role")).lower() == "technical_contact" else 1,
                _as_text(item.get("send_as_email")).lower(),
            )
        )
        return profiles

    def load_profile(self, *, domain: str) -> dict[str, Any]:
        payload = _read_json(self._profile_path(domain))
        if _as_text(payload.get("schema")) != AWS_CSM_NEWSLETTER_PROFILE_SCHEMA:
            return {}
        return dict(payload)

    def save_profile(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = _normalized_domain(domain)
        body = dict(payload if isinstance(payload, dict) else {})
        body["schema"] = AWS_CSM_NEWSLETTER_PROFILE_SCHEMA
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
        _write_json(self._profile_path(token), body)
        return body

    def load_contact_log(self, *, domain: str) -> dict[str, Any]:
        payload = _read_json(self._contacts_path(domain))
        if _as_text(payload.get("schema")) != AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA:
            return {}
        return dict(payload)

    def save_contact_log(self, *, domain: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = _normalized_domain(domain)
        body = dict(payload if isinstance(payload, dict) else {})
        body["schema"] = AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA
        body["domain"] = token
        body["contacts"] = list(body.get("contacts") or [])
        body["dispatches"] = list(body.get("dispatches") or [])[-20:]
        _write_json(self._contacts_path(token), body)
        return body

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
            "schema": AWS_CSM_NEWSLETTER_PROFILE_SCHEMA,
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
            "schema": AWS_CSM_NEWSLETTER_CONTACT_LOG_SCHEMA,
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
            if _as_text(payload.get("schema")) != "mycite.service_tool.aws_csm.profile.v1":
                continue
            identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
            verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
            provider = payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
            workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
            if _as_text(verification.get("status")).lower() != "verified":
                continue
            if _as_text(provider.get("gmail_send_as_status")).lower() != "verified":
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
