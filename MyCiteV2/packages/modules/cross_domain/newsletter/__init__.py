from MyCiteV2.packages.ports.newsletter.contracts import (
    NEWSLETTER_CONTACT_LOG_SCHEMA,
    NEWSLETTER_PROFILE_SCHEMA,
)

from .service import NewsletterService

__all__ = [
    "NEWSLETTER_CONTACT_LOG_SCHEMA",
    "NEWSLETTER_PROFILE_SCHEMA",
    "NewsletterService",
]
