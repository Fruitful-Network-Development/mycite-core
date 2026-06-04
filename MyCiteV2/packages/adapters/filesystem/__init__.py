"""Filesystem-backed adapter implementations for the phase-06 MVP slice."""

from .analytics_event_paths import AnalyticsEventPathResolution, AnalyticsEventPathResolver
from .audit_log import FilesystemAuditLogAdapter
from .aws_narrow_write import FilesystemAwsNarrowWriteAdapter
from .aws_read_only_status import FilesystemAwsReadOnlyStatusAdapter
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
    "AnalyticsEventPathResolution",
    "AnalyticsEventPathResolver",
    "CONTACT_RECORD_SCHEMA",
    "ContactLeafletStore",
    "entity_for_domain",
    "FilesystemAuditLogAdapter",
    "FilesystemNewsletterStateAdapter",
    "FilesystemAwsNarrowWriteAdapter",
    "FilesystemAwsReadOnlyStatusAdapter",
    "FilesystemLiveAwsProfileAdapter",
    "FilesystemNetworkRootReadModelAdapter",
    "FilesystemSystemDatumStoreAdapter",
    "is_live_aws_profile_file",
]
