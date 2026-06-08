"""Analytics ingest orchestration — composes the core leaflet model with the
filesystem store, and coalesces beacon writes.

This is the runtime/composition layer (it may import both core and adapters,
unlike either of those layers). It owns:

  * ``ingest_batch`` — merge a batch of raw events into a month leaflet under
    the store's flock, link the prior month, finalize, and write.
  * ``AnalyticsIngestBuffer`` — an in-process write-coalescer (one per worker).
    The browser emits a heartbeat every ~15s; rewriting a growing YAML on every
    beacon would be O(n²) over a month, so events are buffered per (entity,
    month) and flushed on a count/age threshold, on a lazily-started daemon
    timer, and on shutdown. Losing the last few seconds of un-flushed events on
    a hard crash is acceptable for web analytics.
"""

from __future__ import annotations

import atexit
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import AnalyticsLeafletStore
from MyCiteV2.packages.adapters.filesystem.analytics_leaflet import period_of, prev_period
from MyCiteV2.packages.core.analytics import leaflet_model as lm

_log = logging.getLogger("mycite.portal_host")

FLUSH_COUNT = 25          # flush a (entity, month) once this many events buffer
FLUSH_AGE_SECONDS = 8.0   # …or this long since its first un-flushed event


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def ingest_batch(
    store: AnalyticsLeafletStore,
    entity: str,
    domain: str,
    period: str,
    raw_events: list[dict[str, Any]],
) -> None:
    """Merge a batch of raw events for one (entity, month) under the store lock."""
    if not raw_events:
        return

    def mutate(current: dict[str, Any]) -> dict[str, Any]:
        if current.get("schema") == lm.ANALYTICS_RECORD_SCHEMA and isinstance(
            current.get("visitors"), list
        ):
            month = current
        else:
            month = lm.empty_month(
                entity=entity, domain=domain, period=period, generated_at=""
            )
        before = len(month["visitors"])
        for raw in raw_events:
            lm.merge_event(month, raw)
        # Cross-month lineage only needs the prior month when this batch
        # introduced a NEW visitor (a cookie's returning-flag is set once, when
        # it first appears this month). Skipping the prior read otherwise avoids
        # re-parsing the previous month's full leaflet on every heartbeat flush.
        if len(month["visitors"]) > before:
            prior = store.load_month(entity, prev_period(period))
            lm.link_prior_month(month, prior if prior.get("visitors") else None)
        lm.finalize_month(month, generated_at=_now_iso())
        return month

    store.locked_update(entity, period, mutate)


class AnalyticsIngestBuffer:
    """In-process write-coalescer in front of an :class:`AnalyticsLeafletStore`."""

    def __init__(self, store: AnalyticsLeafletStore) -> None:
        self._store = store
        self._lock = threading.Lock()
        self._pending: dict[tuple[str, str], dict[str, Any]] = {}
        self._timer_started = False
        self._stop = threading.Event()

    def add(self, entity: str, domain: str, raw: dict[str, Any]) -> None:
        period = period_of(raw.get("occurred_at_utc") or raw.get("occurred_at") or "")
        if not period:
            period = period_of(raw.get("received_at_utc") or "") or datetime.now(UTC).strftime("%Y-%m")
        key = (entity, period)
        flush_key: tuple[str, str] | None = None
        with self._lock:
            slot = self._pending.get(key)
            if slot is None:
                slot = {"entity": entity, "domain": domain, "events": [], "since": time.monotonic()}
                self._pending[key] = slot
            slot["events"].append(raw)
            if len(slot["events"]) >= FLUSH_COUNT:
                flush_key = key
        self._ensure_timer()
        if flush_key is not None:
            self._flush_key(flush_key)

    def _due_keys(self) -> list[tuple[str, str]]:
        now = time.monotonic()
        with self._lock:
            return [
                k for k, slot in self._pending.items()
                if (now - slot["since"]) >= FLUSH_AGE_SECONDS
            ]

    def _flush_key(self, key: tuple[str, str]) -> None:
        with self._lock:
            slot = self._pending.pop(key, None)
        if not slot or not slot["events"]:
            return
        try:
            ingest_batch(self._store, slot["entity"], slot["domain"], key[1], slot["events"])
        except Exception:
            _log.warning("analytics_leaflet_flush_failed key=%s", key, exc_info=True)

    def flush_all(self) -> None:
        with self._lock:
            keys = list(self._pending.keys())
        for k in keys:
            self._flush_key(k)

    def _ensure_timer(self) -> None:
        if self._timer_started:
            return
        with self._lock:
            if self._timer_started:
                return
            self._timer_started = True
        t = threading.Thread(target=self._run_timer, name="analytics-flush", daemon=True)
        t.start()
        atexit.register(self.flush_all)

    def _run_timer(self) -> None:
        while not self._stop.wait(FLUSH_AGE_SECONDS):
            for k in self._due_keys():
                self._flush_key(k)


_BUFFERS: dict[str, AnalyticsIngestBuffer] = {}
_BUFFERS_LOCK = threading.Lock()


def get_ingest_buffer(
    *, private_dir: str | Path, webapps_root: str | Path | None = None
) -> AnalyticsIngestBuffer:
    """Process-wide buffer keyed by the resolved analytics dir."""
    store = AnalyticsLeafletStore(private_dir=private_dir, webapps_root=webapps_root)
    key = str(store.analytics_dir)
    with _BUFFERS_LOCK:
        buf = _BUFFERS.get(key)
        if buf is None:
            buf = AnalyticsIngestBuffer(store)
            _BUFFERS[key] = buf
        return buf


__all__ = [
    "AnalyticsIngestBuffer",
    "get_ingest_buffer",
    "ingest_batch",
]
