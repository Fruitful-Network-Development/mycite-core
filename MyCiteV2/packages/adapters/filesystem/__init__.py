"""Filesystem-backed adapter implementations for the phase-06 MVP slice."""

from .audit_log import FilesystemAuditLogAdapter
from .aws_narrow_write import FilesystemAwsNarrowWriteAdapter
from .aws_read_only_status import FilesystemAwsReadOnlyStatusAdapter

__all__ = [
    "FilesystemAuditLogAdapter",
    "FilesystemAwsNarrowWriteAdapter",
    "FilesystemAwsReadOnlyStatusAdapter",
]
