from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
import re

from MyCiteV2.packages.modules.shared import as_text


_REPORT_SUBJECT_TOKENS = (
    "report-id:",
    "report domain:",
    "aggregate report",
    "feedback report",
    "dmarc",
)
_REPORT_SENDER_TOKENS = ("dmarc",)
_CONFIRMATION_SUBJECT_PREFIX = "gmail confirmation - send mail as "
_LINK_PATTERN = re.compile(r"https?://[^\s<>\"]+")
_PROVIDER_SUBJECT_HINTS: dict[str, tuple[str, ...]] = {
    "gmail": (_CONFIRMATION_SUBJECT_PREFIX,),
    "outlook": (
        "verify",
        "verification",
        "confirm",
        "microsoft",
        "outlook",
    ),
    "yahoo": (
        "verify",
        "verification",
        "confirm",
        "yahoo",
    ),
    "proofpoint": (
        "verify",
        "verification",
        "confirm",
        "proofpoint",
    ),
    "generic_manual": (
        "verify",
        "verification",
        "confirm",
    ),
}
_PROVIDER_ALLOWED_SENDERS: dict[str, set[str]] = {
    "gmail": {"gmail-noreply@google.com"},
    "outlook": {
        "account-security-noreply@accountprotection.microsoft.com",
        "noreply@outlook.com",
        "no-reply@microsoft.com",
    },
    "yahoo": {
        "account-security@yahoo-inc.com",
        "no-reply@yahoo.com",
        "noreply@yahoo.com",
    },
    "proofpoint": set(),
    "generic_manual": set(),
}


def _normalized_provider(value: object) -> str:
    token = as_text(value).lower()
    if token in _PROVIDER_SUBJECT_HINTS:
        return token
    return "generic_manual"

def _normalized_email(value: object) -> str:
    token = as_text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local_part, domain_part = token.split("@", 1)
    if not local_part or not domain_part or "." not in domain_part:
        return ""
    return token


def extract_links_from_raw_email(raw_bytes: bytes) -> list[str]:
    message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    text_parts: list[str] = []
    if hasattr(message, "walk"):
        for part in message.walk():
            disposition = str(part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            try:
                text_parts.append(str(part.get_content() or ""))
            except Exception:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = str(part.get_content_charset() or "utf-8")
                    text_parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            text_parts.append(payload.decode(str(message.get_content_charset() or "utf-8"), errors="replace"))
    joined = "\n".join(part for part in text_parts if part)
    return [match.group(0) for match in _LINK_PATTERN.finditer(joined)]


@dataclass(frozen=True)
class AwsCsmForwardDecision:
    should_forward: bool
    classification: str
    reason: str
    sender: str
    recipient: str
    subject: str
    confirmation_link_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "should_forward": self.should_forward,
            "classification": self.classification,
            "reason": self.reason,
            "sender": self.sender,
            "recipient": self.recipient,
            "subject": self.subject,
            "confirmation_link_count": self.confirmation_link_count,
        }


class AwsCsmVerificationForwardFilter:
    def __init__(
        self,
        *,
        allowed_senders: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> None:
        senders = list(allowed_senders or [])
        self._global_allowed_senders = {
            _normalized_email(item)
            for item in senders
            if _normalized_email(item)
        }

    def _subject_matches_provider(self, *, provider: str, lowered_subject: str) -> bool:
        hints = _PROVIDER_SUBJECT_HINTS.get(provider, _PROVIDER_SUBJECT_HINTS["generic_manual"])
        if provider == "gmail":
            return lowered_subject.startswith(_CONFIRMATION_SUBJECT_PREFIX)
        return any(token in lowered_subject for token in hints)

    def _allowed_senders_for_provider(self, *, provider: str) -> set[str]:
        defaults = set(_PROVIDER_ALLOWED_SENDERS.get(provider, set()))
        if not self._global_allowed_senders:
            return defaults
        return defaults.union(self._global_allowed_senders)

    def decide(
        self,
        *,
        tracked_recipients: list[str] | tuple[str, ...] | set[str],
        sender: str,
        recipient: str,
        subject: str,
        raw_bytes: bytes,
        handoff_provider: str = "gmail",
    ) -> AwsCsmForwardDecision:
        provider = _normalized_provider(handoff_provider)
        normalized_sender = _normalized_email(sender)
        normalized_recipient = _normalized_email(recipient)
        normalized_subject = as_text(subject)
        lowered_subject = normalized_subject.lower()
        tracked = {
            _normalized_email(item)
            for item in list(tracked_recipients or [])
            if _normalized_email(item)
        }
        if any(token in normalized_sender for token in _REPORT_SENDER_TOKENS):
            return AwsCsmForwardDecision(
                should_forward=False,
                classification="blocked_report",
                reason="Sender matches a blocked report-like source.",
                sender=normalized_sender,
                recipient=normalized_recipient,
                subject=normalized_subject,
            )
        if any(token in lowered_subject for token in _REPORT_SUBJECT_TOKENS):
            return AwsCsmForwardDecision(
                should_forward=False,
                classification="blocked_report",
                reason="Subject matches a blocked report-like pattern.",
                sender=normalized_sender,
                recipient=normalized_recipient,
                subject=normalized_subject,
            )
        allowed_senders = self._allowed_senders_for_provider(provider=provider)
        if allowed_senders and normalized_sender not in allowed_senders:
            return AwsCsmForwardDecision(
                should_forward=False,
                classification="blocked_sender",
                reason=f"Sender is not allowlisted for {provider} confirmation forwarding.",
                sender=normalized_sender,
                recipient=normalized_recipient,
                subject=normalized_subject,
            )
        if normalized_recipient not in tracked:
            return AwsCsmForwardDecision(
                should_forward=False,
                classification="blocked_recipient",
                reason="Recipient is not a tracked AWS-CSM send-as address.",
                sender=normalized_sender,
                recipient=normalized_recipient,
                subject=normalized_subject,
            )
        if not self._subject_matches_provider(provider=provider, lowered_subject=lowered_subject):
            return AwsCsmForwardDecision(
                should_forward=False,
                classification="blocked_subject",
                reason=f"Subject is not recognized as a {provider} confirmation message.",
                sender=normalized_sender,
                recipient=normalized_recipient,
                subject=normalized_subject,
            )
        links = extract_links_from_raw_email(raw_bytes)
        if not links:
            return AwsCsmForwardDecision(
                should_forward=False,
                classification="blocked_missing_link",
                reason="Verification-class mail must contain a confirmation link before forwarding.",
                sender=normalized_sender,
                recipient=normalized_recipient,
                subject=normalized_subject,
            )
        return AwsCsmForwardDecision(
            should_forward=True,
            classification="verification_confirmation",
            reason=f"Mail matches the {provider} confirmation forwarding policy.",
            sender=normalized_sender,
            recipient=normalized_recipient,
            subject=normalized_subject,
            confirmation_link_count=len(links),
        )


__all__ = [
    "AwsCsmForwardDecision",
    "AwsCsmVerificationForwardFilter",
    "extract_links_from_raw_email",
]
