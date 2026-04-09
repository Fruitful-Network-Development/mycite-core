from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_refs import ParsedDatumRef, normalize_datum_ref, parse_datum_ref

MSN_ID = "3-2-3-17-77-1-6-4-1-4"


class DatumRefUnitTests(unittest.TestCase):
    def test_parse_accepts_local_dot_and_hyphen_forms(self) -> None:
        cases = (
            ("4-1-77", ParsedDatumRef(raw="4-1-77", datum_address="4-1-77", msn_id="")),
            (
                f"{MSN_ID}.4-1-77",
                ParsedDatumRef(raw=f"{MSN_ID}.4-1-77", datum_address="4-1-77", msn_id=MSN_ID),
            ),
            (
                f"{MSN_ID}-4-1-77",
                ParsedDatumRef(raw=f"{MSN_ID}-4-1-77", datum_address="4-1-77", msn_id=MSN_ID),
            ),
        )

        for raw_value, expected in cases:
            with self.subTest(raw_value=raw_value):
                self.assertEqual(parse_datum_ref(raw_value), expected)
                self.assertEqual(parse_datum_ref(raw_value).qualified, bool(expected.msn_id))

    def test_normalize_can_emit_canonical_forms_needed_by_mvp(self) -> None:
        self.assertEqual(
            normalize_datum_ref(
                "4-1-77",
                local_msn_id=MSN_ID,
                require_qualified=True,
                write_format="dot",
                field_name="focus_subject",
            ),
            f"{MSN_ID}.4-1-77",
        )
        self.assertEqual(
            normalize_datum_ref(
                f"{MSN_ID}.4-1-77",
                write_format="hyphen",
                field_name="focus_subject",
            ),
            f"{MSN_ID}-4-1-77",
        )
        self.assertEqual(
            normalize_datum_ref(
                f"{MSN_ID}-4-1-77",
                write_format="local",
                field_name="focus_subject",
            ),
            "4-1-77",
        )

    def test_parse_rejects_malformed_datum_refs(self) -> None:
        invalid_values = (
            "",
            "not-a-datum",
            "4-1",
            "4-1-77-9",
            "abc.4-1-77",
            f"{MSN_ID}.not-a-datum",
            f"{MSN_ID}-not-a-datum",
        )

        for raw_value in invalid_values:
            with self.subTest(raw_value=raw_value):
                with self.assertRaises(ValueError):
                    parse_datum_ref(raw_value, field_name="focus_subject")

    def test_normalize_rejects_missing_or_invalid_qualification_requirements(self) -> None:
        with self.assertRaisesRegex(ValueError, "focus_subject.local_msn_id"):
            normalize_datum_ref(
                "4-1-77",
                require_qualified=True,
                write_format="dot",
                field_name="focus_subject",
            )

        with self.assertRaisesRegex(ValueError, "focus_subject.local_msn_id"):
            normalize_datum_ref(
                "4-1-77",
                local_msn_id="tenant-1",
                require_qualified=True,
                write_format="dot",
                field_name="focus_subject",
            )

    def test_normalize_rejects_unknown_write_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "write_format"):
            normalize_datum_ref(
                f"{MSN_ID}.4-1-77",
                write_format="json",
                field_name="focus_subject",
            )

    def test_normalization_is_deterministic(self) -> None:
        inputs = (
            ("4-1-77", dict(local_msn_id=MSN_ID, require_qualified=True, write_format="dot")),
            (f"{MSN_ID}.4-1-77", dict(write_format="dot")),
            (f"{MSN_ID}-4-1-77", dict(write_format="hyphen")),
        )

        for raw_value, options in inputs:
            with self.subTest(raw_value=raw_value, options=options):
                first = normalize_datum_ref(raw_value, field_name="focus_subject", **options)
                second = normalize_datum_ref(raw_value, field_name="focus_subject", **options)
                self.assertEqual(first, second)
                self.assertEqual(parse_datum_ref(raw_value), parse_datum_ref(raw_value))


if __name__ == "__main__":
    unittest.main()
