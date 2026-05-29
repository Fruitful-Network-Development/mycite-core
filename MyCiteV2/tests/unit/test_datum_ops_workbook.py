"""S6 — workbook YAML envelope + diff→ops compiler.

Verifies (a) the multi-sheet workbook round-trips per-sheet MSS identity, and
(b) the compiler infers an op sequence whose application reproduces an edited
workbook's structure (relocate + recompile + rebuild).
"""

from __future__ import annotations

import unittest

from MyCiteV2.packages.core.datum_io import workbook_from_yaml, workbook_to_yaml
from MyCiteV2.packages.core.datum_ops import (
    RebuildCollection,
    RecompileMagnitude,
    RelocateNode,
    Workbook,
    apply_sequence,
    compile_workbook,
    defined_node_addrs,
    labels,
    plan_migration,
    samras_deps,
    workbook_codec,
)
from MyCiteV2.packages.core.datum_ops.node_ops import RelocateNode as _Reloc  # noqa: F401
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

_NID = labels.RF_NODE_ID
_TITLE = labels.RF_TITLE


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.{name}." + ("a" * 64),
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"agro_erp/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _def(addr: str, node: str, title: str) -> tuple[str, object]:
    return (addr, [[addr, _NID, node, _TITLE, labels.encode_label_bits(title)], [title]])


def _product(addr: str, taxon: str) -> tuple[str, object]:
    return (addr, [[addr, _NID, taxon, "2-1-1", "100"], ["prod"]])


def _wb() -> Workbook:
    node_set = {"1", "1-1", "2", "2-1"}
    bits = samras_deps.build_magnitude_bitstream(node_set)
    txa = _doc("txa", [
        _def("4-2-1", "1", "genus_root"),
        _def("4-2-2", "1-1", "g_child"),
        _def("4-2-3", "2", "catch_all"),
        _def("4-2-4", "2-1", "stray_sp"),
        ("5-0-1", [["5-0-1", "~", "4-2-1", "4-2-2", "4-2-3", "4-2-4"], ["txa_id_collection"]]),
    ])
    anchor = _doc("anchor", [("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]])])
    product = _doc("product_profiles", [_product("4-9-1", "2-1")])
    return Workbook(sandbox="agro_erp", sheets={"anchor": anchor, "txa": txa, "product_profiles": product})


class WorkbookEnvelopeTests(unittest.TestCase):
    def test_roundtrip_preserves_mss_identity(self) -> None:
        wb = _wb()
        text = workbook_codec.to_yaml(wb)
        back = workbook_codec.from_yaml(text)
        for name in wb.names():
            self.assertEqual(
                compute_mss_hash(wb.sheet(name))["version_hash"],
                compute_mss_hash(back.sheet(name))["version_hash"],
                name,
            )

    def test_low_level_codec_sandbox_and_sheets(self) -> None:
        wb = _wb()
        sandbox, docs = workbook_from_yaml(workbook_to_yaml(wb.sandbox, [wb.sheet("txa")]))
        self.assertEqual(sandbox, "agro_erp")
        self.assertEqual(docs[0].document_name, "txa")


class CompilerTests(unittest.TestCase):
    def test_compile_relocate_recovers_edited_structure(self) -> None:
        baseline = _wb()
        # produce an edited workbook by applying a known relocate + housekeeping
        known = [
            RelocateNode("txa", "2-1", "1"),
            RecompileMagnitude("anchor", "1-1-1", "txa"),
            RebuildCollection("txa", "5-0-1", "txa_id_collection"),
        ]
        edited, _ = apply_sequence(baseline, known)

        ops = compile_workbook(baseline, edited)
        # the compiler should infer a relocate + the housekeeping cascade
        self.assertTrue(any(isinstance(o, RelocateNode) for o in ops))
        self.assertTrue(any(isinstance(o, RecompileMagnitude) for o in ops))
        self.assertTrue(any(isinstance(o, RebuildCollection) for o in ops))

        # applying the inferred ops to the baseline reproduces the edited structure
        rebuilt, _ = apply_sequence(baseline, ops)
        self.assertEqual(
            defined_node_addrs(rebuilt.sheet("txa")),
            defined_node_addrs(edited.sheet("txa")),
        )
        self.assertEqual(
            str(rebuilt.sheet("product_profiles").rows[0].raw[0][2]),
            str(edited.sheet("product_profiles").rows[0].raw[0][2]),
        )
        # and the inferred plan is consistent (rule-checked, no dangling)
        plan = plan_migration(baseline, ops)
        self.assertIn("txa", plan.touched)

    def test_compile_noop_when_identical(self) -> None:
        wb = _wb()
        self.assertEqual(compile_workbook(wb, wb), [])


if __name__ == "__main__":
    unittest.main()
