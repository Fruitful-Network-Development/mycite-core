"""Publication-domain read-only tenant summary semantics."""

from .service import (
    PublicationTenantSummary,
    PublicationTenantSummaryService,
    normalize_publication_tenant_summary,
)

__all__ = [
    "PublicationTenantSummary",
    "PublicationTenantSummaryService",
    "normalize_publication_tenant_summary",
]
