from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_editing import (
    cascade_references,
    delete_datum,
    insert_datum,
    shift_iteration,
)


def _row(addr: str, references: list[str] | None = None, label: str | None = None) -> dict:
    raw_first = [addr, "~", "0-0-0"]
    if references:
        raw_first = [addr, "~", "0-0-0", *references]
    return {
        "datum_address": addr,
        "raw": [raw_first, [label or addr]],
    }


def _addresses(rows) -> list[str]:
    return [r["datum_address"] for r in rows]


class TestCascadeReferences(unittest.TestCase):
    def test_rewrites_bare_address_in_raw(self) -> None:
        rows = [
            _row("0-0-1"),
            _row("1-1-1", references=["0-0-1"]),
        ]
        out = cascade_references(rows, {"0-0-1": "0-0-7"})
        self.assertEqual(out[1]["raw"][0], ["1-1-1", "~", "0-0-0", "0-0-7"])
        self.assertEqual(out[0]["datum_address"], "0-0-1")

    def test_rewrites_rf_token(self) -> None:
        rows = [
            {"datum_address": "1-1-1", "raw": [["1-1-1", "~", "0-0-0", "rf.0-0-1"]]},
        ]
        out = cascade_references(rows, {"0-0-1": "0-0-7"})
        self.assertEqual(out[0]["raw"][0][-1], "rf.0-0-7")

    def test_rewrites_prefixed_dot_token(self) -> None:
        rows = [{"datum_address": "1-1-1", "raw": [["1-1-1", "~", "0-0-0", "3-2-3-17.0-0-1"]]}]
        out = cascade_references(rows, {"0-0-1": "0-0-9"})
        self.assertEqual(out[0]["raw"][0][-1], "3-2-3-17.0-0-9")

    def test_empty_remap_is_noop(self) -> None:
        rows = [_row("0-0-1")]
        out = cascade_references(rows, {})
        self.assertEqual(_addresses(out), ["0-0-1"])


class TestInsertDatum(unittest.TestCase):
    def test_insert_into_empty_family(self) -> None:
        rows = [_row("0-0-1")]
        out, remap = insert_datum(rows, _row("0-0-2"))
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2"])
        self.assertEqual(remap, {})

    def test_insert_displaces_existing_iteration(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("0-0-3")]
        out, remap = insert_datum(rows, _row("0-0-2", label="new_two"))
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2", "0-0-3", "0-0-4"])
        self.assertEqual(remap, {"0-0-2": "0-0-3", "0-0-3": "0-0-4"})

    def test_insert_cascades_references(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("1-1-1", references=["0-0-2"])]
        out, _ = insert_datum(rows, _row("0-0-2", label="new_two"))
        ref_row = next(r for r in out if r["datum_address"] == "1-1-1")
        self.assertEqual(ref_row["raw"][0][-1], "0-0-3")

    def test_insert_top_of_abstraction_first(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("0-0-3"), _row("0-0-4")]
        out, remap = insert_datum(rows, _row("0-0-2", label="new"))
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2", "0-0-3", "0-0-4", "0-0-5"])
        self.assertEqual(remap, {"0-0-2": "0-0-3", "0-0-3": "0-0-4", "0-0-4": "0-0-5"})


class TestDeleteDatum(unittest.TestCase):
    def test_delete_collapses_iterations(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("0-0-3")]
        out, remap = delete_datum(rows, "0-0-2")
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2"])
        self.assertEqual(remap, {"0-0-3": "0-0-2"})

    def test_delete_cascades_references(self) -> None:
        rows = [
            _row("0-0-1"),
            _row("0-0-2"),
            _row("0-0-3"),
            _row("1-1-1", references=["0-0-3"]),
        ]
        out, _ = delete_datum(rows, "0-0-2")
        ref_row = next(r for r in out if r["datum_address"] == "1-1-1")
        self.assertEqual(ref_row["raw"][0][-1], "0-0-2")

    def test_delete_unknown_raises(self) -> None:
        rows = [_row("0-0-1")]
        with self.assertRaises(ValueError):
            delete_datum(rows, "0-0-2")

    def test_delete_does_not_skip_iterations(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("0-0-3"), _row("0-0-4")]
        out, _ = delete_datum(rows, "0-0-2")
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2", "0-0-3"])


class TestShiftIteration(unittest.TestCase):
    def test_shift_to_higher_iteration(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("0-0-3")]
        out, remap = shift_iteration(rows, from_address="0-0-1", to_iteration=3)
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2", "0-0-3"])
        moved_row_label = next(r for r in out if r["datum_address"] == "0-0-3")["raw"][1][0]
        self.assertEqual(moved_row_label, "0-0-1")
        self.assertIn("0-0-1", remap)

    def test_shift_to_lower_iteration(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2"), _row("0-0-3")]
        out, _ = shift_iteration(rows, from_address="0-0-3", to_iteration=1)
        moved_row_label = next(r for r in out if r["datum_address"] == "0-0-1")["raw"][1][0]
        self.assertEqual(moved_row_label, "0-0-3")

    def test_shift_no_op_same_iteration(self) -> None:
        rows = [_row("0-0-1"), _row("0-0-2")]
        out, remap = shift_iteration(rows, from_address="0-0-1", to_iteration=1)
        self.assertEqual(_addresses(out), ["0-0-1", "0-0-2"])
        self.assertEqual(remap, {})


if __name__ == "__main__":
    unittest.main()
