"""Unit tests for cts_gis overlay helpers."""
from __future__ import annotations

import unittest

from MyCiteV2.packages.modules.cross_domain.cts_gis._overlay import (
    _district_timeframe_tokens,
    _is_district_timeframe_label,
)


class DistrictTimeframeLabelTests(unittest.TestCase):
    """The marker filter for district timeframes must accept canonical
    `<period>-district_<digits>` labels and reject the structural aspect
    labels (`applicable_time_frame`, `district_set_collection`,
    `precinct_group-<n>`, `boundary_collection`) that share keyword surface
    area with real districts. Locks the regression that surfaced as 4-row
    phantom listings in the Garland tab for Ohio.
    """

    def test_accepts_canonical_period_district_label(self) -> None:
        self.assertTrue(_is_district_timeframe_label("23_present-district_31"))
        self.assertTrue(_is_district_timeframe_label("24_present-district_31"))
        self.assertTrue(_is_district_timeframe_label("2020-district_42"))

    def test_accepts_bare_district_with_digits(self) -> None:
        self.assertTrue(_is_district_timeframe_label("district_31"))
        self.assertTrue(_is_district_timeframe_label("district-31"))
        self.assertTrue(_is_district_timeframe_label("district31"))

    def test_rejects_aspect_records_without_district_digits(self) -> None:
        # Every label below was previously surfaced by the loose filter as a
        # "district timeframe" and caused a phantom row in the listing.
        for aspect in (
            "applicable_time_frame",
            "district_set_collection",
            "precinct_group-1",
            "precinct_group_42",
            "boundary_collection",
            "time_frame",
            "present",
            "23_present",
        ):
            with self.subTest(aspect=aspect):
                self.assertFalse(
                    _is_district_timeframe_label(aspect),
                    f"aspect label {aspect!r} must NOT be treated as a district timeframe",
                )

    def test_empty_input_returns_false(self) -> None:
        self.assertFalse(_is_district_timeframe_label(""))


class DistrictTimeframeTokensCollectionTests(unittest.TestCase):
    """`_district_timeframe_tokens` consumes a document bundle's row_views
    and returns sorted, deduplicated district-timeframe labels. The
    Ohio source datum has exactly one such label (`23_present-district_31`)
    even though several aspect labels (`applicable_time_frame`,
    `district_set_collection`, `precinct_group-1`) are present in
    sibling rows. The function MUST emit exactly one timeframe for Ohio.
    """

    def test_ohio_document_bundle_yields_single_timeframe(self) -> None:
        ohio_like_bundle = {
            "row_views": [
                {"labels": ["applicable_time_frame"]},
                {"labels": ["precinct_group-1"]},
                {"labels": ["23_present-district_31"]},
                {"labels": ["district_set_collection"]},
                {"labels": ["boundary_collection"]},
            ],
        }
        self.assertEqual(
            _district_timeframe_tokens(ohio_like_bundle),
            ["23_present-district_31"],
        )

    def test_multiple_real_districts_are_all_kept(self) -> None:
        # When a county has multiple district overlays in different periods,
        # each canonical timeframe must survive deduplication.
        bundle = {
            "row_views": [
                {"labels": ["23_present-district_31"]},
                {"labels": ["24_present-district_31"]},
                {"labels": ["23_present-district_32"]},
                {"labels": ["applicable_time_frame"]},
            ],
        }
        self.assertEqual(
            _district_timeframe_tokens(bundle),
            ["23_present-district_31", "23_present-district_32", "24_present-district_31"],
        )

    def test_empty_bundle_returns_empty_list(self) -> None:
        self.assertEqual(_district_timeframe_tokens({}), [])
        self.assertEqual(_district_timeframe_tokens({"row_views": []}), [])


if __name__ == "__main__":
    unittest.main()
