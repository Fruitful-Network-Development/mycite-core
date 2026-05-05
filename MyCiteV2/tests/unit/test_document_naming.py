from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.document_naming import (
    CanonicalNameError,
    derive_canonical_id_from_legacy,
    format_canonical_document_id,
    is_canonical_document_id,
    parse_canonical_document_id,
)

MSN = "3-2-3-17-77-1-6-4-1-4"
HASH = "a" * 64
HASH_SHA = "sha256:" + HASH


class TestFormatCanonical(unittest.TestCase):
    def test_lv_with_sandbox(self) -> None:
        out = format_canonical_document_id(
            prefix="lv", msn_id=MSN, sandbox="system", name="anthology", version_hash=HASH
        )
        self.assertEqual(out, f"lv.{MSN}.system.anthology.{HASH}")

    def test_lv_strips_sha256_prefix(self) -> None:
        out = format_canonical_document_id(
            prefix="lv", msn_id=MSN, sandbox="system", name="anthology", version_hash=HASH_SHA
        )
        self.assertEqual(out, f"lv.{MSN}.system.anthology.{HASH}")

    def test_stl_no_sandbox(self) -> None:
        out = format_canonical_document_id(
            prefix="stl", msn_id=MSN, sandbox=None, name="registrar", version_hash=HASH
        )
        self.assertEqual(out, f"stl.{MSN}.registrar.{HASH}")

    def test_cptr_no_sandbox(self) -> None:
        out = format_canonical_document_id(
            prefix="cptr", msn_id=MSN, sandbox=None, name="registrar", version_hash=HASH
        )
        self.assertEqual(out, f"cptr.{MSN}.registrar.{HASH}")

    def test_lv_requires_sandbox(self) -> None:
        with self.assertRaises(CanonicalNameError):
            format_canonical_document_id(
                prefix="lv", msn_id=MSN, sandbox=None, name="anthology", version_hash=HASH
            )

    def test_stl_rejects_sandbox(self) -> None:
        with self.assertRaises(CanonicalNameError):
            format_canonical_document_id(
                prefix="stl", msn_id=MSN, sandbox="cts-gis", name="registrar", version_hash=HASH
            )

    def test_unknown_prefix(self) -> None:
        with self.assertRaises(CanonicalNameError):
            format_canonical_document_id(
                prefix="xx", msn_id=MSN, sandbox="system", name="x", version_hash=HASH
            )

    def test_short_hash(self) -> None:
        with self.assertRaises(CanonicalNameError):
            format_canonical_document_id(
                prefix="stl", msn_id=MSN, sandbox=None, name="r", version_hash="ab"
            )


class TestParseCanonical(unittest.TestCase):
    def test_lv(self) -> None:
        text = f"lv.{MSN}.system.anthology.{HASH}"
        parsed = parse_canonical_document_id(text)
        self.assertEqual(parsed.prefix, "lv")
        self.assertEqual(parsed.msn_id, MSN)
        self.assertEqual(parsed.sandbox, "system")
        self.assertEqual(parsed.name, "anthology")
        self.assertEqual(parsed.version_hash, HASH)
        self.assertEqual(parsed.document_id, text)

    def test_stl(self) -> None:
        text = f"stl.{MSN}.registrar.{HASH}"
        parsed = parse_canonical_document_id(text)
        self.assertEqual(parsed.prefix, "stl")
        self.assertIsNone(parsed.sandbox)
        self.assertEqual(parsed.name, "registrar")

    def test_cptr(self) -> None:
        text = f"cptr.{MSN}.registrar.{HASH}"
        parsed = parse_canonical_document_id(text)
        self.assertEqual(parsed.prefix, "cptr")
        self.assertIsNone(parsed.sandbox)

    def test_format_then_parse_round_trip(self) -> None:
        text = format_canonical_document_id(
            prefix="lv", msn_id=MSN, sandbox="cts-gis", name="247-17-77-1", version_hash=HASH
        )
        parsed = parse_canonical_document_id(text)
        self.assertEqual(parsed.document_id, text)

    def test_legacy_rejected(self) -> None:
        for legacy in ("system:anthology", "sandbox:cts_gis:tool.json"):
            with self.subTest(legacy=legacy):
                self.assertFalse(is_canonical_document_id(legacy))
                with self.assertRaises(CanonicalNameError):
                    parse_canonical_document_id(legacy)


class TestDeriveFromLegacy(unittest.TestCase):
    def test_system_anthology(self) -> None:
        out = derive_canonical_id_from_legacy("system:anthology", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"lv.{MSN}.system.anthology.{HASH}")

    def test_sandbox_cts_gis_anchor(self) -> None:
        out = derive_canonical_id_from_legacy(
            "sandbox:cts_gis:tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts-gis.anchor.{HASH}")

    def test_sandbox_other_source(self) -> None:
        out = derive_canonical_id_from_legacy(
            "sandbox:cts_gis:sc.3-2-3-17.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts-gis.sc.{HASH}")

    def test_payload(self) -> None:
        out = derive_canonical_id_from_legacy("payload:registrar.bin", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"stl.{MSN}.registrar.{HASH}")

    def test_cache(self) -> None:
        out = derive_canonical_id_from_legacy("cache:registrar.json", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"cptr.{MSN}.registrar.{HASH}")

    def test_unsupported_legacy_raises(self) -> None:
        with self.assertRaises(CanonicalNameError):
            derive_canonical_id_from_legacy("garbage:thing", msn_id=MSN, version_hash=HASH)


if __name__ == "__main__":
    unittest.main()
