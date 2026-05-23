"""A10b — SES event enrichment of the operator ledger metrics block.

Pins:
  * Default (no bucket env, no kwarg) → all three new metrics dicts empty.
  * With a stubbed s3 client, Send/Bounce/Complaint events are counted
    per (domain → msn_id) and folded into emails_sent_by_msn etc.
  * Domains not mapped to any grantee msn_id are ignored (not counted).
  * S3 errors on one domain/day don't poison the rest of the aggregate.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _seed_grantee_dir(tmp: Path, domain: str, msn_id: str) -> Path:
    """Seed grantee JSONs directly at <tmp>/grantee.*.json.

    `load_grantee_directory(fnd_csm_root)` globs `<root>/grantee.*.json`
    (no utilities/tools/fnd-csm subdir), so the test's `fnd_csm_root`
    arg points at <tmp> directly.
    """
    tmp.mkdir(parents=True, exist_ok=True)
    import json as _json
    payload = {
        "schema": "mycite.v2.grantee.profile.v1",
        "msn_id": msn_id,
        "label": f"Grantee {msn_id}",
        "short_name": msn_id,
        "domains": [domain],
        "users": [f"user@{domain}"],
    }
    (tmp / f"grantee.fnd.{msn_id}.json").write_text(
        _json.dumps(payload), encoding="utf-8"
    )
    return tmp


class _StubS3:
    """Returns canned counts per (Bucket, Prefix). Anything not in the
    map returns KeyCount=0. Test sets `.fail_for_prefix` to raise on a
    specific prefix to exercise the defensive error path.
    """

    def __init__(self, counts: dict[str, int]):
        self.counts = counts
        self.fail_for_prefix: str | None = None
        self.calls: list[dict[str, Any]] = []

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        prefix = kwargs.get("Prefix", "")
        if self.fail_for_prefix and prefix == self.fail_for_prefix:
            raise RuntimeError("s3 transient failure")
        return {"KeyCount": self.counts.get(prefix, 0), "IsTruncated": False}


class SesEventMetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import tolling
        self.tolling = tolling
        # Two grantees: alpha (msn-a) and beta (msn-b); each owns 1 domain.
        # Fresh temp dir per test + clear the module's TTL cache so
        # the first test's empty seed doesn't poison subsequent tests.
        self.tmp = Path(tempfile.mkdtemp(prefix="a10b_ses_"))
        _seed_grantee_dir(self.tmp, "alpha.example.test", "msn-a")
        _seed_grantee_dir(self.tmp, "beta.example.test", "msn-b")
        tolling._GRANTEE_DIRECTORY_CACHE.clear()

    def test_default_no_bucket_returns_empty(self) -> None:
        # No bucket env, no kwarg → opt-out path; everything empty.
        with patch.dict("os.environ", {}, clear=False):
            for var in ("MYCITE_SES_EVENTS_BUCKET", "MYCITE_SES_EVENTS_PREFIX"):
                if var in __import__("os").environ:
                    del __import__("os").environ[var]
            result = self.tolling._aggregate_ses_event_metrics(
                "2026-05-22", "2026-05-23",
                fnd_csm_root=self.tmp,
            )
        self.assertEqual(result["emails_sent_by_msn"], {})
        self.assertEqual(result["emails_bounced_by_msn"], {})
        self.assertEqual(result["emails_complained_by_msn"], {})

    def test_counts_sent_bounced_complained_per_msn(self) -> None:
        # Seed: alpha gets 3 Sends + 1 Bounce on day 1, 2 Sends day 2.
        # beta gets 5 Sends day 1 + 1 Complaint day 2.
        counts = {
            "ses_events/alpha.example.test/2026-05-22/Send/": 3,
            "ses_events/alpha.example.test/2026-05-22/Bounce/": 1,
            "ses_events/alpha.example.test/2026-05-23/Send/": 2,
            "ses_events/beta.example.test/2026-05-22/Send/": 5,
            "ses_events/beta.example.test/2026-05-23/Complaint/": 1,
        }
        stub = _StubS3(counts)
        result = self.tolling._aggregate_ses_event_metrics(
            "2026-05-22", "2026-05-24",  # 2-day window: 22 + 23 (24 excl)
            fnd_csm_root=self.tmp,
            events_bucket="my-events",
            events_prefix="ses_events",
            s3_client=stub,
        )
        self.assertEqual(result["emails_sent_by_msn"], {"msn-a": 5, "msn-b": 5})
        self.assertEqual(result["emails_bounced_by_msn"], {"msn-a": 1})
        self.assertEqual(result["emails_complained_by_msn"], {"msn-b": 1})

    def test_unknown_domains_ignored(self) -> None:
        # ghost.example.test isn't in any grantee profile → must not
        # appear in any metric.
        counts = {
            "ses_events/alpha.example.test/2026-05-22/Send/": 2,
            "ses_events/ghost.example.test/2026-05-22/Send/": 99,
        }
        stub = _StubS3(counts)
        result = self.tolling._aggregate_ses_event_metrics(
            "2026-05-22", "2026-05-23",
            fnd_csm_root=self.tmp,
            events_bucket="my-events",
            s3_client=stub,
        )
        # Only alpha's events counted. ghost never appears because the
        # s3 stub only gets called for domains in the grantee directory
        # (the aggregator iterates domain_to_msn, not S3 listing).
        self.assertEqual(result["emails_sent_by_msn"], {"msn-a": 2})
        # Confirm we never called list for the ghost domain.
        for call in stub.calls:
            self.assertNotIn("ghost.example.test", call.get("Prefix", ""))

    def test_per_domain_s3_failure_does_not_poison_other_domains(self) -> None:
        counts = {
            "ses_events/alpha.example.test/2026-05-22/Send/": 3,
            "ses_events/beta.example.test/2026-05-22/Send/": 4,
        }
        stub = _StubS3(counts)
        # Make alpha's Send list raise; beta should still be counted.
        stub.fail_for_prefix = "ses_events/alpha.example.test/2026-05-22/Send/"
        result = self.tolling._aggregate_ses_event_metrics(
            "2026-05-22", "2026-05-23",
            fnd_csm_root=self.tmp,
            events_bucket="my-events",
            s3_client=stub,
        )
        # alpha Send not counted (failed); beta Send counted normally.
        self.assertEqual(result["emails_sent_by_msn"], {"msn-b": 4})

    def test_paginated_response_summed(self) -> None:
        """Pin that pagination via ContinuationToken adds across pages."""
        # Custom stub that returns 2 pages for one prefix.
        class _PaginatedStub:
            def __init__(self):
                self.call_count = 0
            def list_objects_v2(self, **kwargs):
                self.call_count += 1
                prefix = kwargs.get("Prefix", "")
                if prefix != "ses_events/alpha.example.test/2026-05-22/Send/":
                    return {"KeyCount": 0, "IsTruncated": False}
                if self.call_count == 1:
                    return {
                        "KeyCount": 1000,
                        "IsTruncated": True,
                        "NextContinuationToken": "tok2",
                    }
                return {"KeyCount": 7, "IsTruncated": False}

        stub = _PaginatedStub()
        result = self.tolling._aggregate_ses_event_metrics(
            "2026-05-22", "2026-05-23",
            fnd_csm_root=self.tmp,
            events_bucket="my-events",
            s3_client=stub,
        )
        self.assertEqual(result["emails_sent_by_msn"], {"msn-a": 1007})


class SesEventLambdaNormalizerTests(unittest.TestCase):
    """A10a — quick sanity on the existing ses_event_sink Lambda's
    normalizer + per-domain bucketing. The Lambda is deployed-by-operator
    (admin-session step), but the in-repo code can be exercised offline.
    """

    def _import_lambda(self):
        # Lambda lives in /srv/repo/srv-infra/aws_lambdas/ses_event_sink.
        # Import it directly by path to avoid hard-coding sys.path here.
        import importlib.util
        path = Path("/srv/repo/srv-infra/aws_lambdas/ses_event_sink/lambda_function.py")
        if not path.exists():
            self.skipTest("ses_event_sink lambda not present in this checkout")
        spec = importlib.util.spec_from_file_location("ses_event_sink_lf", path)
        module = importlib.util.module_from_spec(spec)
        # The Lambda imports boto3 at module level; stub it.
        sys.modules["boto3"] = MagicMock()
        spec.loader.exec_module(module)
        return module

    def test_normalize_send_event_extracts_recipients_and_metadata(self) -> None:
        lf = self._import_lambda()
        payload = {
            "eventType": "Send",
            "mail": {
                "messageId": "msg-abc",
                "timestamp": "2026-05-22T10:00:00.000Z",
                "source": "noreply@alpha.example.test",
                "destination": ["donor@example.com", "other@example.com"],
                "tags": {"ses:configuration-set": "fnd-default"},
            },
        }
        record = lf._normalize(payload)
        self.assertIsNotNone(record)
        self.assertEqual(record["event_type"], "Send")
        self.assertEqual(record["message_id"], "msg-abc")
        self.assertEqual(
            record["recipients"], ["donor@example.com", "other@example.com"]
        )
        self.assertEqual(record["from_address"], "noreply@alpha.example.test")
        self.assertEqual(record["config_set"], "fnd-default")

    def test_normalize_bounce_event_uses_bounced_recipients(self) -> None:
        lf = self._import_lambda()
        payload = {
            "eventType": "Bounce",
            "bounce": {
                "bounceType": "Permanent",
                "bounceSubType": "General",
                "bouncedRecipients": [
                    {"emailAddress": "ghost@example.com"},
                ],
            },
            "mail": {"messageId": "msg-xyz", "timestamp": "2026-05-22T10:00:00Z"},
        }
        record = lf._normalize(payload)
        self.assertIsNotNone(record)
        self.assertEqual(record["recipients"], ["ghost@example.com"])
        self.assertEqual(record["bounce_type"], "Permanent")
        self.assertEqual(record["bounce_subtype"], "General")

    def test_normalize_event_missing_recipients_returns_none(self) -> None:
        lf = self._import_lambda()
        payload = {
            "eventType": "Send",
            "mail": {"messageId": "msg-xyz", "destination": []},
        }
        self.assertIsNone(lf._normalize(payload))

    def test_domain_of_extracts_recipient_domain(self) -> None:
        lf = self._import_lambda()
        self.assertEqual(lf._domain_of("alice@Example.Com"), "example.com")
        self.assertEqual(lf._domain_of(""), "")
        self.assertEqual(lf._domain_of("malformed"), "")


if __name__ == "__main__":
    unittest.main()
