"""C3 — DMARC ramp ladder + parsing (the safety-critical pure logic).

The ladder must NEVER:
  * skip a rung (none -> reject)
  * advance without MAIL FROM live
  * advance without >= MIN_ALIGNMENT_PCT alignment
  * advance without >= MIN_DWELL_DAYS dwell
  * advance past the terminal p=reject
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.peripherals.aws.dmarc_ramp import (
    MIN_ALIGNMENT_PCT,
    MIN_DWELL_DAYS,
    compute_dmarc_ramp,
    parse_dmarc_policy,
)


class ParseDmarcPolicyTests(unittest.TestCase):
    def test_parses_basic_record(self) -> None:
        tags = parse_dmarc_policy(
            '"v=DMARC1; p=none; rua=mailto:x@y.com; adkim=s; aspf=s"'
        )
        self.assertEqual(tags["v"], "DMARC1")
        self.assertEqual(tags["p"], "none")
        self.assertEqual(tags["pct"], "100")  # defaulted
        self.assertEqual(tags["rua"], "mailto:x@y.com")

    def test_explicit_pct_preserved(self) -> None:
        tags = parse_dmarc_policy("v=DMARC1; p=quarantine; pct=20")
        self.assertEqual(tags["pct"], "20")

    def test_non_dmarc_returns_empty(self) -> None:
        self.assertEqual(parse_dmarc_policy('"v=spf1 include:amazonses.com"'), {})
        self.assertEqual(parse_dmarc_policy(""), {})
        self.assertEqual(parse_dmarc_policy("garbage"), {})


def _tags(p: str, pct: str = "100") -> dict[str, str]:
    return {"v": "DMARC1", "p": p, "pct": pct, "rua": "mailto:dmarc-reports@x.com"}


class RampLadderHappyPathTests(unittest.TestCase):
    """Each rung advances to the next when all preconditions are met."""

    def _allowed(self, tags):
        return compute_dmarc_ramp(
            current_tags=tags,
            mail_from_live=True,
            alignment_pct=99.0,
            days_at_current=14,
        )

    def test_none_advances_to_quarantine_20(self) -> None:
        d = self._allowed(_tags("none"))
        self.assertTrue(d["allowed"])
        self.assertEqual(d["proposed_policy"], "quarantine")
        self.assertEqual(d["proposed_pct"], "20")
        self.assertIn("p=quarantine", d["proposed_record"])
        self.assertIn("pct=20", d["proposed_record"])

    def test_quarantine_20_advances_to_quarantine_100(self) -> None:
        d = self._allowed(_tags("quarantine", "20"))
        self.assertTrue(d["allowed"])
        self.assertEqual(d["proposed_policy"], "quarantine")
        self.assertEqual(d["proposed_pct"], "100")
        # pct=100 is the default → no explicit pct clause
        self.assertNotIn("pct=", d["proposed_record"])

    def test_quarantine_100_advances_to_reject(self) -> None:
        d = self._allowed(_tags("quarantine", "100"))
        self.assertTrue(d["allowed"])
        self.assertEqual(d["proposed_policy"], "reject")

    def test_reject_is_terminal(self) -> None:
        d = self._allowed(_tags("reject"))
        self.assertFalse(d["allowed"])
        self.assertIsNone(d["proposed_policy"])
        self.assertIn("terminal", d["blockers"][0])


class RampLadderGuardrailTests(unittest.TestCase):
    """Every precondition individually blocks the ramp."""

    def test_mail_from_not_live_blocks(self) -> None:
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=False,
            alignment_pct=99.0,
            days_at_current=14,
        )
        self.assertFalse(d["allowed"])
        self.assertTrue(any("MAIL FROM" in b for b in d["blockers"]))

    def test_low_alignment_blocks(self) -> None:
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=True,
            alignment_pct=80.0,
            days_at_current=14,
        )
        self.assertFalse(d["allowed"])
        self.assertTrue(any("alignment" in b for b in d["blockers"]))

    def test_missing_alignment_blocks(self) -> None:
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=True,
            alignment_pct=None,
            days_at_current=14,
        )
        self.assertFalse(d["allowed"])
        self.assertTrue(any("alignment" in b for b in d["blockers"]))

    def test_short_dwell_blocks(self) -> None:
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=True,
            alignment_pct=99.0,
            days_at_current=MIN_DWELL_DAYS - 1,
        )
        self.assertFalse(d["allowed"])
        self.assertTrue(any("at current policy" in b for b in d["blockers"]))

    def test_missing_dwell_blocks(self) -> None:
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=True,
            alignment_pct=99.0,
            days_at_current=None,
        )
        self.assertFalse(d["allowed"])
        self.assertTrue(any("dwell" in b for b in d["blockers"]))

    def test_exactly_at_thresholds_allowed(self) -> None:
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=True,
            alignment_pct=MIN_ALIGNMENT_PCT,
            days_at_current=MIN_DWELL_DAYS,
        )
        self.assertTrue(d["allowed"])

    def test_never_skips_a_rung(self) -> None:
        # From p=none the only allowed target is quarantine pct=20 —
        # never reject, never quarantine pct=100.
        d = compute_dmarc_ramp(
            current_tags=_tags("none"),
            mail_from_live=True,
            alignment_pct=99.0,
            days_at_current=99,
        )
        self.assertEqual(d["proposed_policy"], "quarantine")
        self.assertEqual(d["proposed_pct"], "20")
        self.assertNotEqual(d["proposed_policy"], "reject")

    def test_unknown_policy_not_auto_ramped(self) -> None:
        d = compute_dmarc_ramp(
            current_tags={"v": "DMARC1", "p": "bogus", "pct": "100"},
            mail_from_live=True,
            alignment_pct=99.0,
            days_at_current=14,
        )
        self.assertFalse(d["allowed"])
        self.assertTrue(any("unrecognized" in b for b in d["blockers"]))


if __name__ == "__main__":
    unittest.main()
