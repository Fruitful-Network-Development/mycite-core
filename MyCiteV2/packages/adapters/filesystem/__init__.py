"""Filesystem-backed adapter implementations for the phase-06 MVP slice."""

from .audit_log import FilesystemAuditLogAdapter

__all__ = [
    "FilesystemAuditLogAdapter",
]
