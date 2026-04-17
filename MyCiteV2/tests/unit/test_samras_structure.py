from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.structures.samras import (
    InvalidSamrasStructure,
    decode_structure,
    encode_canonical_structure_from_addresses,
)


_LIVE_INVALID_MSN_SAMRAS = (
    "000000000010000000000110011011100000000100000000010100000010010000001111"
    "000001000100000100100000010011000001011100000110000000011011000001110000"
    "00011110000010000100001000100000100011000010010000001001"
)


class SamrasStructureUnitTests(unittest.TestCase):
    def test_round_trips_a_canonical_breadth_first_address_tree(self) -> None:
        structure = encode_canonical_structure_from_addresses(
            ["1", "2", "2-1", "2-2", "2-2-1", "3"]
        )

        decoded = decode_structure(structure.bitstream)

        self.assertEqual(decoded.source_format, "canonical")
        self.assertEqual(decoded.canonical_state, "canonical")
        self.assertEqual(decoded.addresses, ("1", "2", "3", "2-1", "2-2", "2-2-1"))
        self.assertEqual(decoded.root_count, 3)
        self.assertEqual(decoded.node_count, 6)

    def test_current_live_like_invalid_magnitude_fails_closed(self) -> None:
        with self.assertRaises(InvalidSamrasStructure) as exc:
            decode_structure(_LIVE_INVALID_MSN_SAMRAS)

        self.assertIn("legacy address width must be positive", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
