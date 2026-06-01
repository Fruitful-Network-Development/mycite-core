"""Port: analytics event-file path resolution.

``core.analytics.derivations.read_events`` needs to locate the per-domain
NDJSON event files, but *locating files on disk* is an adapter concern. This
port defines the structural contract (a ``Protocol``) so core depends on the
interface, not on the filesystem adapter that implements it
(:class:`MyCiteV2.packages.adapters.filesystem.analytics_event_paths.AnalyticsEventPathResolver`).

core → ports is allowed; core → adapters is not. The concrete resolver is
constructed by the caller (in ``instances`` / adapters) and injected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AnalyticsEventPathResolution(Protocol):
    """The resolved location of one domain/month event file."""

    events_file: Path


@runtime_checkable
class AnalyticsEventPathResolver(Protocol):
    """Resolves where to read a domain's per-month analytics NDJSON."""

    def resolve_events_file(
        self, *, domain: object, year_month: object
    ) -> AnalyticsEventPathResolution: ...
