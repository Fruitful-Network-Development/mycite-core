"""Filesystem-backed adapter implementations for the phase-06 MVP slice."""

from .analytics_leaflet import (
    ANALYTICS_RECORD_SCHEMA,
    AnalyticsLeafletStore,
    period_of,
)
from .audit_log import FilesystemAuditLogAdapter
from .aws_narrow_write import FilesystemAwsNarrowWriteAdapter
from .aws_read_only_status import FilesystemAwsReadOnlyStatusAdapter
from .campaign_leaflet import (
    CAMPAIGN_RECORD_SCHEMA,
    CampaignLeafletStore,
)
from .contact_leaflet import (
    CONTACT_RECORD_SCHEMA,
    ContactLeafletStore,
    entity_for_domain,
)
from .live_aws_profile import FilesystemLiveAwsProfileAdapter, is_live_aws_profile_file
from .live_system_datum_store import FilesystemSystemDatumStoreAdapter
from .network_root_read_model import FilesystemNetworkRootReadModelAdapter
from .newsletter_state import FilesystemNewsletterStateAdapter

__all__ = [
    "ANALYTICS_RECORD_SCHEMA",
    "AnalyticsLeafletStore",
    "CAMPAIGN_RECORD_SCHEMA",
    "CampaignLeafletStore",
    "CONTACT_RECORD_SCHEMA",
    "ContactLeafletStore",
    "entity_for_domain",
    "period_of",
    "FilesystemAuditLogAdapter",
    "FilesystemNewsletterStateAdapter",
    "FilesystemAwsNarrowWriteAdapter",
    "FilesystemAwsReadOnlyStatusAdapter",
    "FilesystemLiveAwsProfileAdapter",
    "FilesystemNetworkRootReadModelAdapter",
    "FilesystemSystemDatumStoreAdapter",
    "is_live_aws_profile_file",
]
