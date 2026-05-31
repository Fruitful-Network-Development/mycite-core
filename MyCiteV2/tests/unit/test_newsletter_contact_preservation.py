"""Newsletter contact normalizer must preserve the FULL canonical row.

Regression for the inbound-dispatch data-loss bug: ``normalize_contact`` (and
thus ``normalize_contact_log``, which the inbound dispatch path runs over the
whole list before saving it back) used to rebuild a 12-field subset, silently
dropping phone / first_name / middle_name / last_name / organization /
forward_status / subject / message / signup_date on every dispatch.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.newsletter.payload_utils import (
    normalize_contact,
    normalize_contact_log,
)

_RICH = {
    "email": "Jo@Example.com",
    "first_name": "Jo",
    "middle_name": "Q",
    "last_name": "Public",
    "phone": "555-1212",
    "organization": "Acme Co",
    "forward_status": "sent",
    "subject": "hello",
    "message": "a message",
    "signup_date": "2026-01-02",
    "subscribed": True,
    "notes": "vip",
}

_PRESERVED = (
    "first_name",
    "middle_name",
    "last_name",
    "phone",
    "organization",
    "forward_status",
    "subject",
    "message",
    "signup_date",
    "notes",
)


class NormalizeContactPreservationTests(unittest.TestCase):
    def test_normalize_contact_preserves_all_fields(self) -> None:
        out = normalize_contact(_RICH)
        self.assertIsNotNone(out)
        for field in _PRESERVED:
            self.assertEqual(out.get(field), _RICH[field], f"dropped {field}")
        # Identity invariants still normalized.
        self.assertEqual(out["email"], "jo@example.com")
        self.assertTrue(out["subscribed"])

    def test_normalize_contact_log_round_trip_preserves_fields(self) -> None:
        log = normalize_contact_log({"contacts": [_RICH]}, domain="example.com")
        self.assertEqual(len(log["contacts"]), 1)
        row = log["contacts"][0]
        for field in _PRESERVED:
            self.assertEqual(row.get(field), _RICH[field], f"dropped {field}")

    def test_strips_internal_source_path_key(self) -> None:
        out = normalize_contact({**_RICH, "_source_path": "/tmp/x"})
        self.assertNotIn("_source_path", out)

    def test_rejects_non_dict_and_emailless(self) -> None:
        self.assertIsNone(normalize_contact("nope"))
        self.assertIsNone(normalize_contact({"name": "no email"}))


if __name__ == "__main__":
    unittest.main()
