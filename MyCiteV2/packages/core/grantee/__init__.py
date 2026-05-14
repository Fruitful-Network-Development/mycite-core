"""Grantee profile schema and filesystem store.

The grantee JSON file (``grantee.{fnd_msn}.{grantee_msn}.json``) is the
operator-owned source of truth for per-grantee configuration: display name,
domains roster, mailbox users, and the credential fields the Utilities
extensions consume (PayPal, AWS SES, newsletter sender).

See ``/srv/agentic/knowledge/legacy/mycite-core/contracts/grantee_profile_contract.md``
for the canonical schema and storage invariants.
"""

from .schema import (
    AwsSesConfig,
    GRANTEE_PROFILE_SCHEMA,
    GranteeProfile,
    NewsletterConfig,
    PaypalConfig,
)
from .store import load_grantee_profile, save_grantee_profile

__all__ = [
    "AwsSesConfig",
    "GRANTEE_PROFILE_SCHEMA",
    "GranteeProfile",
    "NewsletterConfig",
    "PaypalConfig",
    "load_grantee_profile",
    "save_grantee_profile",
]
