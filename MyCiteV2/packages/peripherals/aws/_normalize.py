"""Shared normalization helpers for the AWS peripheral.

The lambda functions under `srv-infra/aws_lambdas/` each ship their own
copy of `_normalized_email` deliberately — they are independent units
deployed to AWS Lambda and must not import from mycite-core. This file
is the in-process equivalent for adapter / cli / profile-store code.
"""

from __future__ import annotations


def as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalized_email(value: object) -> str:
    token = as_text(value).lower()
    if token.count("@") != 1 or any(ch.isspace() for ch in token):
        return ""
    local, domain = token.split("@", 1)
    if not local or not domain or "." not in domain:
        return ""
    return token


def normalized_domain(value: object) -> str:
    token = as_text(value).lower()
    if token.startswith("www."):
        token = token[4:]
    return token


def recipient_domain(recipient: object) -> str:
    token = normalized_email(recipient)
    return token.split("@", 1)[1] if token else ""
