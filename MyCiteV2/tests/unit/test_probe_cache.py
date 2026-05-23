"""ProbeCache — single-process TTL cache for AWS read-probes.

Pins:
  * cold miss → compute called, value cached
  * warm hit within TTL → compute NOT called
  * expired entry → compute called again
  * invalidate(key) → next get computes
  * clear() → all entries dropped
  * exception from compute() propagates AND is NOT cached
  * ttl_seconds <= 0 rejected at construction
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from MyCiteV2.packages.peripherals.aws.probe_cache import ProbeCache


class ProbeCacheBasicsTests(unittest.TestCase):
    def test_cold_miss_calls_compute_and_caches(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        calls = []

        def compute() -> str:
            calls.append(1)
            return "v1"

        self.assertEqual(cache.get_or_compute(("probe", "a"), compute), "v1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(cache), 1)

    def test_warm_hit_within_ttl_skips_compute(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        calls = []

        def compute() -> str:
            calls.append(1)
            return "v1"

        cache.get_or_compute(("probe", "a"), compute)
        cache.get_or_compute(("probe", "a"), compute)
        cache.get_or_compute(("probe", "a"), compute)
        self.assertEqual(len(calls), 1)

    def test_expired_entry_triggers_recompute(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        calls = []

        def compute() -> str:
            calls.append(len(calls) + 1)
            return f"v{len(calls)}"

        # First call at t=0
        with patch("MyCiteV2.packages.peripherals.aws.probe_cache.time.monotonic", return_value=0.0):
            self.assertEqual(cache.get_or_compute(("probe", "a"), compute), "v1")
        # Second call at t=30 — still fresh
        with patch("MyCiteV2.packages.peripherals.aws.probe_cache.time.monotonic", return_value=30.0):
            self.assertEqual(cache.get_or_compute(("probe", "a"), compute), "v1")
        # Third call at t=120 — expired (TTL was 60)
        with patch("MyCiteV2.packages.peripherals.aws.probe_cache.time.monotonic", return_value=120.0):
            self.assertEqual(cache.get_or_compute(("probe", "a"), compute), "v2")
        self.assertEqual(len(calls), 2)

    def test_distinct_keys_cached_independently(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        cache.get_or_compute(("probe", "a"), lambda: "value-a")
        cache.get_or_compute(("probe", "b"), lambda: "value-b")
        self.assertEqual(len(cache), 2)
        # Re-fetch must hit cache, not recompute
        self.assertEqual(
            cache.get_or_compute(("probe", "a"), lambda: "WRONG"), "value-a"
        )
        self.assertEqual(
            cache.get_or_compute(("probe", "b"), lambda: "WRONG"), "value-b"
        )


class ProbeCacheInvalidationTests(unittest.TestCase):
    def test_invalidate_drops_one_entry(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        cache.get_or_compute(("p", "a"), lambda: 1)
        cache.get_or_compute(("p", "b"), lambda: 2)
        cache.invalidate(("p", "a"))
        self.assertEqual(len(cache), 1)
        # ('p', 'a') recomputes
        self.assertEqual(cache.get_or_compute(("p", "a"), lambda: 99), 99)
        # ('p', 'b') still cached
        self.assertEqual(cache.get_or_compute(("p", "b"), lambda: 99), 2)

    def test_invalidate_unknown_key_is_noop(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        cache.invalidate(("p", "ghost"))  # must not raise
        self.assertEqual(len(cache), 0)

    def test_clear_drops_everything(self) -> None:
        cache = ProbeCache(ttl_seconds=60)
        cache.get_or_compute(("p", "a"), lambda: 1)
        cache.get_or_compute(("p", "b"), lambda: 2)
        cache.clear()
        self.assertEqual(len(cache), 0)


class ProbeCacheExceptionTests(unittest.TestCase):
    def test_compute_exception_propagates(self) -> None:
        cache = ProbeCache(ttl_seconds=60)

        class ProbeError(RuntimeError):
            pass

        def compute() -> str:
            raise ProbeError("aws is down")

        with self.assertRaises(ProbeError):
            cache.get_or_compute(("p", "a"), compute)

    def test_compute_exception_not_cached(self) -> None:
        """A failed probe must retry next call, not stick the cache to broken."""
        cache = ProbeCache(ttl_seconds=60)
        attempts = []

        def compute() -> str:
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("first call fails")
            return "ok"

        with self.assertRaises(RuntimeError):
            cache.get_or_compute(("p", "a"), compute)
        # Second call retries (would have raised again if exception was cached)
        self.assertEqual(cache.get_or_compute(("p", "a"), compute), "ok")
        self.assertEqual(len(attempts), 2)


class ProbeCacheConstructorTests(unittest.TestCase):
    def test_zero_ttl_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProbeCache(ttl_seconds=0)

    def test_negative_ttl_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProbeCache(ttl_seconds=-1)


if __name__ == "__main__":
    unittest.main()
