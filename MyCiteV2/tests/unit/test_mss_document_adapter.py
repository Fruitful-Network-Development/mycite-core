"""AuthoritativeDatumDocument → MssDatum closure adapter.

Proves the adapter resolves references ACROSS documents (a sandbox datum →
anthology base), builds the downward closure, round-trips through the codec, and
reports dropped dangling/malformed tokens rather than mangling them.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.mss.document_adapter import (
    MssAdapterReport,
    build_catalog_index,
    document_closure_to_mss,
)
from MyCiteV2.packages.core.mss.document_codec import (
    decode_document,
    encode_document,
    mss_document_hash,
    reindex_into_isolated_anthology,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.s.{name}." + ("a" * 64),
        source_kind="sandbox_source", document_name=name, relative_path=f"s/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _catalog(*docs) -> AuthoritativeDatumDocumentCatalogResult:
    return AuthoritativeDatumDocumentCatalogResult(
        tenant_id="fnd", documents=tuple(docs),
        source_files={"sandbox_source": "s/"}, readiness_status={"x": "y"},
    )


class ClosureAdapterTests(unittest.TestCase):
    def test_cross_document_closure_resolves_and_round_trips(self) -> None:
        # anthology doc holds the base; the sandbox doc references it cross-document.
        anthology = _doc("anthology", [
            ("0-0-1", [["0-0-1", "~"], ["top"]]),                         # rudi, refs-only
            ("1-1-1", [["1-1-1", "0-0-1", "128"], ["abstraction"]]),       # tuple → 0-0-1
        ])
        sandbox = _doc("txa", [
            ("4-2-1", [["4-2-1", "rf.1-1-1", "63072000000"], ["event"]]),  # tuple → 1-1-1 (rf.)
        ])
        index = build_catalog_index(_catalog(anthology, sandbox))
        report = MssAdapterReport()
        datums = document_closure_to_mss(sandbox, index=index, report=report)
        # closure pulled in the cross-document anthology datums:
        self.assertEqual({d.address for d in datums}, {"4-2-1", "1-1-1", "0-0-1"})
        self.assertEqual(report.dropped_dangling, 0)
        # and it round-trips through the binary codec:
        canonical, _ = reindex_into_isolated_anthology(datums)
        decoded = decode_document(encode_document(canonical).bitstream)

        def nf(ds):
            return sorted((d.refs, d.tuples) for d in ds)

        self.assertEqual(nf(canonical), nf(decoded))

    def test_dangling_reference_is_dropped_and_counted(self) -> None:
        doc = _doc("txa", [
            ("0-0-1", [["0-0-1", "~"], ["top"]]),
            ("4-2-1", [["4-2-1", "0-0-1", "5", "9-9-9", "7"], ["x"]]),  # 9-9-9 absent
        ])
        index = build_catalog_index(_catalog(doc))
        report = MssAdapterReport()
        datums = document_closure_to_mss(doc, index=index, report=report)
        self.assertEqual(report.dropped_dangling, 1)
        leaf = next(d for d in datums if d.address == "4-2-1")
        self.assertEqual(leaf.tuples, (("0-0-1", 5),))  # only the resolvable tuple kept

    def test_literal_magnitude_coerced_and_hash_stable(self) -> None:
        doc = _doc("entity", [
            ("0-0-1", [["0-0-1", "~"], ["top"]]),
            # entity record: VG1 with two attribute tuples + a literal value.
            ("1-1-1", [["1-1-1", "rf.0-0-1", "elizabeth", "rf.0-0-1", "blake"], ["person"]]),
        ])
        index = build_catalog_index(_catalog(doc))
        datums = document_closure_to_mss(doc, index=index)
        entity = next(d for d in datums if d.address == "1-1-1")
        self.assertEqual(len(entity.tuples), 2)  # arity 2 under value_group 1 (v2)
        h1 = mss_document_hash(datums)
        h2 = mss_document_hash(document_closure_to_mss(doc, index=build_catalog_index(_catalog(doc))))
        self.assertEqual(h1, h2)
        self.assertTrue(h1.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
