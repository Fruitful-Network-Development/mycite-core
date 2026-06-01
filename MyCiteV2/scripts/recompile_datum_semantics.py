#!/usr/bin/env python3
"""MSS cutover tool — compute the binary-MSS canonical document hashes.

Recomputes every canonical datum document's ``version_hash`` as the **binary MSS**
hash (``core.mss.mss_document_hash`` over the document's tenant-wide downward
closure, via ``document_closure_to_mss``), replacing the ``mos.mss_sha256_v1``
JSON+SHA-256 stand-in. Emits the old→new ``version_hash`` + save-title
(``document_id``) mapping.

**Default mode is DRY-RUN (read-only).** It computes and reports the mapping and
writes it to ``--out`` for review. ``--apply`` is intentionally **not implemented**:
the write path must reissue save-titles across the ``documents`` index, recompute
``datum_document_semantics`` / ``datum_row_semantics``, and **remap
``directive_context`` overlay keys** (overlays are keyed by ``subject_hyphae_hash``)
atomically + reversibly — that belongs in a dedicated, schema-careful, reviewed
change, run against a DB **copy** in a maintenance window. See
``docs/contracts/mss_binary_sequence/cutover_design.md``.

Usage:
    python -m MyCiteV2.scripts.recompile_datum_semantics --db <path> [--tenant fnd] [--out map.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.set_int_max_str_digits(1_000_000)  # some live magnitudes are 11k+ digits

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.mss import (
    MssAdapterReport,
    build_catalog_index,
    document_closure_to_mss,
    mss_document_hash,
)
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

# Canonical datum-document id prefixes (type.msn.sandbox.name.hash). Operational
# scalar docs (newsletter logs, aws_csm profiles, …) are NOT datum documents and
# are skipped — they keep their existing identity.
_CANONICAL_PREFIXES = ("lv.", "stl.", "cptr.", "sc.")


def _new_document_id(document_id: str, new_hash_hex: str) -> str | None:
    """Replace the trailing 64-hex hash segment of a canonical document_id."""
    parts = document_id.split(".")
    if len(parts) < 5 or len(parts[-1]) != 64:
        return None
    parts[-1] = new_hash_hex
    return ".".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="MSS cutover hash recompute (dry-run by default)")
    ap.add_argument("--db", required=True, help="path to the MOS authority sqlite (use a COPY for safety)")
    ap.add_argument("--tenant", default="fnd")
    ap.add_argument("--out", default="", help="write the old→new map JSON here")
    ap.add_argument("--apply", action="store_true", help="(not implemented — see module docstring)")
    args = ap.parse_args()

    if args.apply:
        print(
            "ERROR: --apply is intentionally not implemented. This tool computes the\n"
            "cutover mapping read-only. The write path (reissue save-titles, recompute\n"
            "datum_document/row_semantics, remap directive_context overlay keys) must be\n"
            "a dedicated reviewed change run against a DB copy in a maintenance window.",
            file=sys.stderr,
        )
        return 2

    store = SqliteSystemDatumStoreAdapter(args.db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=args.tenant)
    )
    index = build_catalog_index(catalog)
    report = MssAdapterReport()

    mapping: list[dict[str, str]] = []
    skipped = 0
    for document in catalog.documents:
        if not document.document_id.startswith(_CANONICAL_PREFIXES):
            skipped += 1
            continue
        identity = store.read_document_version_identity(
            tenant_id=args.tenant, document_id=document.document_id
        )
        old_hash = (identity or {}).get("version_hash", "")
        datums = document_closure_to_mss(document, index=index, report=report)
        new_hash = mss_document_hash(datums)
        new_hex = new_hash.split(":", 1)[1]
        new_id = _new_document_id(document.document_id, new_hex)
        mapping.append(
            {
                "document_id": document.document_id,
                "new_document_id": new_id or document.document_id,
                "old_version_hash": old_hash,
                "new_version_hash": new_hash,
                "closure_size": str(len(datums)),
            }
        )

    print(f"tenant={args.tenant}  documents={len(catalog.documents)}")
    print(f"canonical datum docs mapped = {len(mapping)}   (skipped non-datum/operational = {skipped})")
    print(
        f"closure adapter: datums={report.datums}  "
        f"dropped_dangling={report.dropped_dangling}  "
        f"dropped_upward={report.dropped_upward}  dropped_malformed={report.dropped_malformed}"
    )
    print("examples (document_id → new save-title):")
    for row in mapping[:5]:
        print(f"  {row['document_id']}\n    → {row['new_document_id']}")
    if args.out:
        Path(args.out).write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        print(f"wrote old→new map: {args.out}")
    print("\nDRY-RUN only. No data written. Review the map, then implement + run --apply")
    print("against a DB copy in a maintenance window (see cutover_design.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
