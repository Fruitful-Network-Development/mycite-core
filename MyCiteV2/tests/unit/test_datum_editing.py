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


class TestRoundTripVersionHash(unittest.TestCase):
    """AC-3: insert → hash changes; delete same datum → hash returns to original."""

    def _compute_hash(self, rows: list) -> str:
        import hashlib
        import json
        sorted_rows = sorted(rows, key=lambda r: tuple(int(p) for p in r["datum_address"].split("-")))
        payload = json.dumps([r["raw"] for r in sorted_rows], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def test_insert_changes_hash_delete_restores_it(self) -> None:
        original_rows = [_row("0-0-1", label="a"), _row("0-0-2", label="b")]
        hash_before = self._compute_hash(original_rows)

        new_datum = _row("0-0-2", label="inserted")
        after_insert, _ = insert_datum(original_rows, new_datum)
        hash_after_insert = self._compute_hash(after_insert)
        self.assertNotEqual(hash_before, hash_after_insert, "Hash must change after insert")
        self.assertEqual(len(after_insert), 3)

        # Delete the inserted datum (now at 0-0-2 after shift, inserted at 0-0-2 → others shifted)
        inserted_addr = new_datum["datum_address"]
        after_delete, _ = delete_datum(after_insert, inserted_addr)
        hash_after_delete = self._compute_hash(after_delete)
        self.assertEqual(len(after_delete), 2)
        self.assertEqual(hash_before, hash_after_delete, "Hash must return to original after deleting inserted datum")

    def test_delete_changes_hash(self) -> None:
        # Verify that deleting any datum produces a different hash.
        # Note: re-inserting a freshly-constructed row does NOT necessarily restore the
        # original hash because insert_datum cascades reference-remap across the new row's
        # raw payload (including its embedded self-address). The correct round-trip uses
        # the insert→delete direction (covered by test_insert_changes_hash_delete_restores_it).
        original_rows = [_row("0-0-1", label="a"), _row("0-0-2", label="b"), _row("0-0-3", label="c")]
        hash_before = self._compute_hash(original_rows)

        after_delete, _ = delete_datum(original_rows, "0-0-2")
        hash_after_delete = self._compute_hash(after_delete)
        self.assertNotEqual(hash_before, hash_after_delete, "Hash must change after delete")
        self.assertEqual(len(after_delete), 2)

        after_delete_last, _ = delete_datum(after_delete, "0-0-2")
        hash_after_both = self._compute_hash(after_delete_last)
        self.assertNotEqual(hash_after_delete, hash_after_both, "Each deletion produces distinct hash")


if __name__ == "__main__":
    unittest.main()
