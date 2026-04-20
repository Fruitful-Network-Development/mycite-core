from __future__ import annotations

from typing import Any

from MyCiteV2.packages.modules.shared import as_text


def normalize_optional_domain_list(value: object, *, field_name: str) -> tuple[str, ...]:
    """Parse optional `allowed_send_domains` from a live AWS profile JSON payload."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of domain strings or null")
    seen: set[str] = set()
    out: list[str] = []
    for index, item in enumerate(value):
        token = as_text(item).lower()
        if not token or "." not in token:
            raise ValueError(f"{field_name}[{index}] must be a domain-like value")
        if token not in seen:
            seen.add(token)
            out.append(token)
    return tuple(sorted(out))


def effective_allowed_send_domains(*, primary_domain: str, extra_domains: tuple[str, ...]) -> tuple[str, ...]:
    """Union of primary `identity.domain` and optional secondary domains; always includes primary when set."""
    primary = as_text(primary_domain).lower()
    if not primary:
        return tuple(sorted(extra_domains))
    return tuple(sorted({primary} | set(extra_domains)))


def sender_email_domain(email: object) -> str:
    token = as_text(email).lower()
    if "@" not in token:
        return ""
    return token.split("@", 1)[1]


def selected_verified_sender_allowed(email: object, allowed_domains: tuple[str, ...]) -> bool:
    domain = sender_email_domain(email)
    if not domain or not allowed_domains:
        return False
    return domain in frozenset(allowed_domains)


def extract_allowed_send_domains_from_profile(payload: dict[str, Any]) -> tuple[str, ...]:
    """Read top-level `allowed_send_domains` from a live profile dict (may be missing)."""
    return normalize_optional_domain_list(
        payload.get("allowed_send_domains"),
        field_name="allowed_send_domains",
    )
