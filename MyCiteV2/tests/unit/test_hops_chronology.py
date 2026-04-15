from __future__ import annotations

from datetime import datetime, timezone
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.structures.hops.chronology import (  # noqa: E402
    build_chronology_authority,
    encode_utc_datetime_as_hops,
)
from MyCiteV2.packages.core.structures.hops.time_address import compare_time_addresses  # noqa: E402
from MyCiteV2.packages.core.structures.hops.time_address_schema import (  # noqa: E402
    schema_from_anchor_payload,
    validate_address_with_schema,
)


class HopsChronologyTests(unittest.TestCase):
    def _anthology_payload(self) -> dict[str, object]:
        return {
            "1-1-1": [
                [
                    "1-1-1",
                    "0-0-1",
                    "00000010000110000000110011010101111000011011001100011101111001111101000111110100011111010001011011010111000111100111100",
                ],
                ["HOPS-chornological"],
            ]
        }

    def _quadrennium_payload(self) -> dict[str, object]:
        return {
            "1-1-1": [["1-1-1", "rf.0-0-1", "00000100011100000101100100011011111101110110110101110001111001111001111101000"], ["HOPS-quadrennium_cycle"]],
            "2-0-1": [["2-0-1", "~", "1-1-1"], ["HOPS-space-quadrennium"]],
            "3-1-1": [["3-1-1", "2-0-1", "0"], ["HOPS-babelette-quadrennium_cycle"]],
        }

    def test_schema_decodes_live_chronology_authority(self) -> None:
        schema_payload = schema_from_anchor_payload(self._anthology_payload())
        self.assertTrue(bool(schema_payload.get("ok")))
        self.assertEqual(
            (schema_payload.get("schema") or {}).get("denotations"),
            [4, 1000, 1000, 1000, 1461, 24, 60, 60],
        )

    def test_encoder_projects_utc_time_onto_quadrennium_axis(self) -> None:
        schema_payload = schema_from_anchor_payload(self._anthology_payload())
        authority = build_chronology_authority(
            schema_payload=schema_payload,
            quadrennium_payload=self._quadrennium_payload(),
        )
        hops = encode_utc_datetime_as_hops(
            datetime(2026, 7, 4, 12, 34, 56, tzinfo=timezone.utc),
            authority=authority,
        )
        self.assertEqual(hops, "0-0-0-507-916-12-34-56")
        self.assertTrue(bool(validate_address_with_schema(hops, schema_payload).get("ok")))

    def test_numeric_time_comparison_is_descoped_from_string_ordering(self) -> None:
        self.assertLess(
            compare_time_addresses("0-0-0-507-916-12-34-56", "0-0-0-507-916-12-34-57"),
            0,
        )


if __name__ == "__main__":
    unittest.main()
