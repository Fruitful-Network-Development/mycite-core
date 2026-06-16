"""datum_resolve primitives — decode_label edge cases + bounded cached_index.

Pins the consolidation-spine behavior surfaced by the 2026-06-16 review:

* ``decode_label`` returns "" for an empty / all-zero (NUL-terminated) babelette and
  DROPS non-printable control bytes — this is the INTENDED behavior (an unset weight
  decodes to "" → 0.0, not the old BinaryTextLens "{N} bits" sentinel that
  ``_parse_weight`` mis-parsed as a numeric weight). A clean ASCII babelette round-trips;
  non-binary or non-byte-aligned input is returned verbatim.
* ``_INDEX_CACHE`` is bounded (FIFO eviction) so superseded content-hash document_ids do
  not accumulate unboundedly over the portal's process lifetime.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops import datum_resolve
from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    cached_index,
    decode_label,
    encode_label,
)


def _bits(text: str) -> str:
    return "".join(format(b, "08b") for b in text.encode("ascii"))


class TestDecodeLabel(unittest.TestCase):
    def test_clean_ascii_roundtrips(self) -> None:
        self.assertEqual(decode_label(encode_label("25 lbs")), "25 lbs")
        self.assertEqual(decode_label(_bits("brassica")), "brassica")

    def test_empty_and_all_zero_decode_to_empty(self) -> None:
        # An unset weight (all-zero / NUL-terminated blob) is "", NOT the old
        # BinaryTextLens "{N} bits" sentinel that _parse_weight mis-read as a number.
        self.assertEqual(decode_label(""), "")
        self.assertEqual(decode_label("0" * 512), "")
        self.assertEqual(decode_label("0" * 136), "")

    def test_control_bytes_are_dropped_not_sentineled(self) -> None:
        # "AB" then a TAB (0x09) control byte: printable kept, control dropped.
        blob = _bits("AB") + format(9, "08b")
        self.assertEqual(decode_label(blob), "AB")

    def test_non_binary_or_unaligned_returned_verbatim(self) -> None:
        self.assertEqual(decode_label("25 lbs"), "25 lbs")   # not all 0/1
        self.assertEqual(decode_label("0101010"), "0101010")  # len % 8 != 0


class TestCachedIndexBounded(unittest.TestCase):
    def test_cache_is_bounded(self) -> None:
        class _Doc:
            def __init__(self, did: str) -> None:
                self.document_id = did
                self.rows: tuple = ()

        datum_resolve._INDEX_CACHE.clear()
        try:
            for i in range(datum_resolve._INDEX_CACHE_MAX * 2):
                cached_index(_Doc(f"lv.x.agro_erp.doc.{i:064d}"))
            self.assertLessEqual(
                len(datum_resolve._INDEX_CACHE), datum_resolve._INDEX_CACHE_MAX
            )
        finally:
            datum_resolve._INDEX_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
