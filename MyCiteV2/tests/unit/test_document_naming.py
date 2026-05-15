from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.document_naming import (
    CanonicalNameError,
    MalformedSourceNameError,
    _sanitize_sandbox_token,
    _sanitize_segment,
    derive_canonical_id_from_legacy,
    extract_semantic_name_from_sc_stem,
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
                prefix="stl", msn_id=MSN, sandbox="cts_gis", name="registrar", version_hash=HASH
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

    def test_lv_underscore_sandbox(self) -> None:
        text = f"lv.{MSN}.cts_gis.natural_entity.{HASH}"
        parsed = parse_canonical_document_id(text)
        self.assertEqual(parsed.sandbox, "cts_gis")
        self.assertEqual(parsed.name, "natural_entity")

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
            prefix="lv", msn_id=MSN, sandbox="cts_gis", name="natural_entity", version_hash=HASH
        )
        parsed = parse_canonical_document_id(text)
        self.assertEqual(parsed.document_id, text)
        self.assertEqual(parsed.sandbox, "cts_gis")
        self.assertEqual(parsed.name, "natural_entity")

    def test_legacy_rejected(self) -> None:
        for legacy in ("system:anthology", "sandbox:cts_gis:tool.json"):
            with self.subTest(legacy=legacy):
                self.assertFalse(is_canonical_document_id(legacy))
                with self.assertRaises(CanonicalNameError):
                    parse_canonical_document_id(legacy)


class TestSanitizeSegment(unittest.TestCase):
    def test_underscores_preserved(self) -> None:
        self.assertEqual(_sanitize_segment("natural_entity"), "natural_entity")

    def test_spaces_become_underscores(self) -> None:
        self.assertEqual(_sanitize_segment("natural entity"), "natural_entity")

    def test_hyphens_preserved(self) -> None:
        self.assertEqual(_sanitize_segment("3-2-3-17"), "3-2-3-17")

    def test_uppercase_lowercased(self) -> None:
        self.assertEqual(_sanitize_segment("NaturalEntity"), "naturalentity")

    def test_dots_stripped(self) -> None:
        self.assertEqual(_sanitize_segment("foo.bar"), "foobar")

    def test_empty_returns_anchor(self) -> None:
        self.assertEqual(_sanitize_segment(""), "anchor")
        self.assertEqual(_sanitize_segment("..."), "anchor")


class TestSanitizeSandboxToken(unittest.TestCase):
    def test_hyphen_to_underscore(self) -> None:
        self.assertEqual(_sanitize_sandbox_token("cts-gis"), "cts_gis")

    def test_underscore_preserved(self) -> None:
        self.assertEqual(_sanitize_sandbox_token("cts_gis"), "cts_gis")

    def test_idempotent(self) -> None:
        self.assertEqual(_sanitize_sandbox_token("cts_gis"), "cts_gis")
        self.assertEqual(_sanitize_sandbox_token("fnd_ebi"), "fnd_ebi")

    def test_fnd_ebi_slug(self) -> None:
        self.assertEqual(_sanitize_sandbox_token("fnd-ebi"), "fnd_ebi")

    def test_aws_csm_slug(self) -> None:
        self.assertEqual(_sanitize_sandbox_token("aws-csm"), "aws_csm")

    def test_system_unchanged(self) -> None:
        self.assertEqual(_sanitize_sandbox_token("system"), "system")

    def test_empty_returns_anchor(self) -> None:
        self.assertEqual(_sanitize_sandbox_token(""), "anchor")


class TestExtractSemanticName(unittest.TestCase):
    def test_msn_dash_natural_entity(self) -> None:
        self.assertEqual(
            extract_semantic_name_from_sc_stem(f"sc.{MSN}.msn-natural_entity"),
            "natural_entity",
        )

    def test_msn_underscore_address_nodes(self) -> None:
        self.assertEqual(
            extract_semantic_name_from_sc_stem(f"sc.{MSN}.msn_address_nodes"),
            "address_nodes",
        )

    def test_fnd_precinct(self) -> None:
        self.assertEqual(
            extract_semantic_name_from_sc_stem(f"sc.{MSN}.fnd.3-2-3-17-77-1-1"),
            "3-2-3-17-77-1-1",
        )

    def test_no_namespace_prefix(self) -> None:
        self.assertEqual(
            extract_semantic_name_from_sc_stem(f"sc.{MSN}.sos_voterid"),
            "sos_voterid",
        )

    def test_registrar_prefix(self) -> None:
        self.assertEqual(
            extract_semantic_name_from_sc_stem(f"sc.{MSN}.registrar.main"),
            "main",
        )

    def test_cts_prefix(self) -> None:
        self.assertEqual(
            extract_semantic_name_from_sc_stem(f"sc.{MSN}.cts.247_17_77_1"),
            "247_17_77_1",
        )

    def test_malformed_empty_after_msn_dash(self) -> None:
        self.assertIsNone(extract_semantic_name_from_sc_stem(f"sc.{MSN}.msn-"))

    def test_malformed_empty_name_segment(self) -> None:
        self.assertIsNone(extract_semantic_name_from_sc_stem(f"sc.{MSN}."))

    def test_not_sc_prefix_returns_none(self) -> None:
        self.assertIsNone(extract_semantic_name_from_sc_stem(f"tool.{MSN}.cts-gis"))
        self.assertIsNone(extract_semantic_name_from_sc_stem("anthology"))

    def test_no_msn_segment(self) -> None:
        # sc. followed directly by semantic with no MSN — still extracts something
        result = extract_semantic_name_from_sc_stem("sc.natural_entity")
        self.assertEqual(result, "natural_entity")


class TestDeriveFromLegacy(unittest.TestCase):
    def test_system_anthology(self) -> None:
        out = derive_canonical_id_from_legacy("system:anthology", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"lv.{MSN}.system.anthology.{HASH}")

    def test_system_natural_entity_preserves_underscore(self) -> None:
        out = derive_canonical_id_from_legacy(
            "system:natural_entity", msn_id=MSN, version_hash=HASH
        )
        self.assertEqual(out, f"lv.{MSN}.system.natural_entity.{HASH}")

    def test_sandbox_cts_gis_anchor(self) -> None:
        out = derive_canonical_id_from_legacy(
            "sandbox:cts_gis:tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.anchor.{HASH}")

    def test_sandbox_hyphen_slug_normalised_to_underscore(self) -> None:
        out = derive_canonical_id_from_legacy(
            "sandbox:cts-gis:tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.anchor.{HASH}")

    def test_sandbox_sc_msn_natural_entity(self) -> None:
        out = derive_canonical_id_from_legacy(
            f"sandbox:cts_gis:sc.{MSN}.msn-natural_entity.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.natural_entity.{HASH}")

    def test_sandbox_sc_msn_address_nodes(self) -> None:
        out = derive_canonical_id_from_legacy(
            f"sandbox:cts_gis:sc.{MSN}.msn_address_nodes.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.address_nodes.{HASH}")

    def test_sandbox_sc_fnd_precinct(self) -> None:
        out = derive_canonical_id_from_legacy(
            f"sandbox:cts_gis:sc.{MSN}.fnd.3-2-3-17-77-1-1.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.3-2-3-17-77-1-1.{HASH}")

    def test_sandbox_sc_sos_voterid(self) -> None:
        out = derive_canonical_id_from_legacy(
            f"sandbox:cts_gis:sc.{MSN}.sos_voterid.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.sos_voterid.{HASH}")

    def test_sandbox_sc_malformed_empty_stem_raises(self) -> None:
        with self.assertRaises(MalformedSourceNameError):
            derive_canonical_id_from_legacy(
                f"sandbox:cts_gis:sc.{MSN}.msn-.json",
                msn_id=MSN,
                version_hash=HASH,
            )

    def test_sandbox_other_source(self) -> None:
        # sc.3-2-3-17 has no msn-... prefix — the address fragment itself is the name
        out = derive_canonical_id_from_legacy(
            "sandbox:cts_gis:sc.3-2-3-17.json",
            msn_id=MSN,
            version_hash=HASH,
        )
        self.assertEqual(out, f"lv.{MSN}.cts_gis.3-2-3-17.{HASH}")

    def test_payload(self) -> None:
        out = derive_canonical_id_from_legacy("payload:registrar.bin", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"stl.{MSN}.registrar.{HASH}")

    def test_payload_name_underscore_preserved(self) -> None:
        out = derive_canonical_id_from_legacy("payload:natural_entity.bin", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"stl.{MSN}.natural_entity.{HASH}")

    def test_cache(self) -> None:
        out = derive_canonical_id_from_legacy("cache:registrar.json", msn_id=MSN, version_hash=HASH)
        self.assertEqual(out, f"cptr.{MSN}.registrar.{HASH}")

    def test_cache_name_underscore_preserved(self) -> None:
        out = derive_canonical_id_from_legacy(
            "cache:natural_entity.json", msn_id=MSN, version_hash=HASH
        )
        self.assertEqual(out, f"cptr.{MSN}.natural_entity.{HASH}")

    def test_unsupported_legacy_raises(self) -> None:
        with self.assertRaises(CanonicalNameError):
            derive_canonical_id_from_legacy("garbage:thing", msn_id=MSN, version_hash=HASH)


if __name__ == "__main__":
    unittest.main()
