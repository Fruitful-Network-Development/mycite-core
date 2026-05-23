"""TTL cache for AWS read-probes used by the activity-based onboarding overlay.

The portal's email-extension renderer calls live AWS APIs (SES identity
status, CloudWatch send counters, S3 inbound listings) on every page render
to overlay "live evidence" badges onto the onboarding-step progress bar.
Without caching, a 5-mailbox grantee triggers ~15 AWS round-trips per
render. With this cache, 5-minute TTL collapses those to one round-trip
per (probe, args) tuple per worker per 5 minutes.

Design choices (deliberate):

* `time.monotonic()` not wall clock — survives clock jumps / VM suspend.
* No threading lock — gunicorn workers are single-threaded per process.
* No exception caching — a failed probe must retry next time, not stick.
* No size cap — Python dict survives mailbox cardinality (~10s, not 10k).
* Per-process scope — multiple gunicorn workers each warm independently;
  that's fine because probes are read-only and idempotent.

Used by the Wave-B probe methods on AwsPeripheralCloudAdapter; not used
elsewhere yet.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Hashable


class ProbeCache:
    """In-memory TTL cache. Single-process, no locking, no exception caching."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._ttl = ttl_seconds
        self._entries: dict[Hashable, tuple[float, Any]] = {}

    def get_or_compute(
        self, key: Hashable, compute: Callable[[], Any]
    ) -> Any:
        """Return cached value if fresh; otherwise call ``compute()`` and cache.

        Exceptions from ``compute()`` propagate without being cached, so a
        transient AWS error doesn't stick the cache to "broken" for the
        rest of the TTL window.
        """
        now = time.monotonic()
        cached = self._entries.get(key)
        if cached is not None:
            expires_at, value = cached
            if now < expires_at:
                return value
        value = compute()
        self._entries[key] = (now + self._ttl, value)
        return value

    def invalidate(self, key: Hashable) -> None:
        """Drop a single entry. No-op if absent."""
        self._entries.pop(key, None)

    def clear(self) -> None:
        """Drop all entries."""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


__all__ = ["ProbeCache"]
