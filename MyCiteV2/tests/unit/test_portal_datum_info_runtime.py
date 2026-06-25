"""Guards run_datum_info input validation (the hyphae-path INFORMATION surface).
Full closure computation is covered by datum_semantics tests + live verification."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_info_runtime import run_datum_info


class DatumInfoGuardTests(unittest.TestCase):
    def test_missing_inputs_400(self) -> None:
        r = run_datum_info(authority_db_file=None, portal_instance_id="fnd", document_id="", datum_address="")
        self.assertFalse(r["ok"])
        self.assertEqual(r["status_code"], 400)

    def test_missing_address_400(self) -> None:
        r = run_datum_info(authority_db_file=None, portal_instance_id="fnd", document_id="d", datum_address="")
        self.assertFalse(r["ok"])
        self.assertEqual(r["status_code"], 400)


if __name__ == "__main__":
    unittest.main()
