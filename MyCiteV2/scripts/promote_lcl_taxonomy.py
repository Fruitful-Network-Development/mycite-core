#!/usr/bin/env python3
"""Promote the LCL (Local) taxonomy into the agro_erp ``lcl`` sandbox doc.

LCL is a Trapp-family-farm-LLC taxonomy parallel to ``txa``: 46 hierarchical
entries rooted at ``1`` (trapp_family_farm_llc), branching into ``1-1`` entity,
``1-2`` land, and ``1-3`` product. Each row follows the same SAMRAS-magnitude
shape txa already uses:

    [["4-2-N", "rf.3-1-1", "<dash-id>", "rf.3-1-2", "<512-bit ASCII bits>"],
     ["<plain label>"]]

The ``rf.3-1-2`` magnitude is encoded against the ``niu-baciloid-256-64``
bacilloid declared at agro_erp anchor row 2-1-2 — 64 chars x 8-bit ASCII,
zero-padded to 512 bits.

The script also extends the agro_erp anchor with the file pointer for LCL at
row ``1-0-2`` (mirrors txa's existing ``1-0-1`` pointer). Both doc replacements
re-derive the canonical document_id from the updated content hash, then upsert
the ``documents`` index row by (tenant, sandbox, name) — never by sandbox alone
(would wipe siblings). Idempotent: re-running replaces in place.

Standing discipline (per promote_sd31_district_boundary.py):
  - Back up the live MOS DB first.
  - Run against an isolated copy with --authority-db pointing there.
  - Verify the dry-run before applying live.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.document_naming import format_canonical_document_id
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)

TENANT = "fnd"
MSN_ID = "3-2-3-17-77-1-6-4-1-4"
SANDBOX = "agro_erp"
LCL_NAME = "lcl"
ANCHOR_NAME = "anchor"

# rf.3-1-2 = title-babelette over niu-baciloid-256-64 (anchor row 2-1-2).
# Empirically the magnitude column is 512 bits = 64 chars x 8-bit ASCII,
# zero-right-padded. Verified by decoding a live txa row.
RF312_BITS = 512

# (position_id_with_dashes, plain_label). Taxonomy authored by the operator.
# The 1-2 land branch is renumbered from the draft (1-2-1=property,
# 1-2-2=plot_1, 1-2-3=plot_2; parcels stay under property). The draft's
# `proegule` was corrected to `propagule` (seed/slip/bulb/root/splice
# are propagule forms).
LCL_ENTRIES: tuple[tuple[str, str], ...] = (
    ("1", "trapp_family_farm_llc"),
    ("1-1", "entity"),
    ("1-1-1", "owner"),
    ("1-1-2", "animal"),
    ("1-1-3", "employee"),
    ("1-2", "land"),
    ("1-2-1", "property"),
    ("1-2-1-1", "parcel_1"),
    ("1-2-1-2", "parcel_2"),
    ("1-2-1-3", "parcel_3"),
    ("1-2-2", "plot_1"),
    ("1-2-3", "plot_2"),
    ("1-3", "product"),
    ("1-3-1", "product_type"),
    ("1-3-1-1", "product_1"),
    ("1-3-2", "product_classification"),
    ("1-3-2-1", "rotation_group"),
    ("1-3-2-1-1", "legumes"),
    ("1-3-2-1-2", "nightshades"),
    ("1-3-2-1-3", "brassicas"),
    ("1-3-2-1-4", "alliums"),
    ("1-3-2-1-5", "umbellifers"),
    ("1-3-2-1-6", "cucurbits"),
    ("1-3-2-1-7", "leafy_greens"),
    ("1-3-2-1-8", "chenopods"),
    ("1-3-2-1-9", "grasses"),
    ("1-3-2-1-10", "mallow_family"),
    ("1-3-2-1-11", "mint_family"),
    ("1-3-2-1-12", "sweet_potato"),
    ("1-3-2-1-13", "composites"),
    ("1-3-2-1-14", "other"),
    ("1-3-2-2", "propagule"),
    ("1-3-2-2-1", "seed"),
    ("1-3-2-2-2", "slip"),
    ("1-3-2-2-3", "bulb"),
    ("1-3-2-2-4", "root"),
    ("1-3-2-2-5", "splice"),
    ("1-3-2-3", "genesis"),
    ("1-3-2-3-1", "heirloom"),
    ("1-3-2-3-2", "f1"),
    ("1-3-2-3-3", "gmo"),
    ("1-3-2-4", "ownership"),
    ("1-3-2-4-1", "open"),
    ("1-3-2-4-2", "pbr"),
    ("1-3-2-4-3", "t_gurt"),
    ("1-3-2-4-4", "v_gurt"),
)

# Anchor pointer for the LCL doc, mirroring txa's existing 1-0-1 row. The
# ``<hash>.json`` token is a literal placeholder (txa's row stores it
# verbatim too — the actual content hash isn't carried here).
LCL_ANCHOR_POINTER_ADDR = "1-0-2"
LCL_ANCHOR_POINTER_LABEL = (
    f"sc.{MSN_ID}.{SANDBOX}.{LCL_NAME}.<hash>.json"
)


def _encode_label_bits(label: str, *, bits: int = RF312_BITS) -> str:
    """ASCII → per-char 8-bit, right-zero-padded to ``bits`` (mirrors txa)."""
    raw = "".join(format(b, "08b") for b in label.encode("ascii"))
    if len(raw) > bits:
        raise ValueError(f"label {label!r} exceeds {bits} bits ({bits // 8} chars)")
    return raw.ljust(bits, "0")


def _build_lcl_taxonomy_rows() -> tuple[AuthoritativeDatumDocumentRow, ...]:
    rows: list[AuthoritativeDatumDocumentRow] = []
    for index, (position_id, label) in enumerate(LCL_ENTRIES, start=1):
        datum_address = f"4-2-{index}"
        bits = _encode_label_bits(label)
        rows.append(
            AuthoritativeDatumDocumentRow(
                datum_address=datum_address,
                raw=[
                    [datum_address, "rf.3-1-1", position_id, "rf.3-1-2", bits],
                    [label],
                ],
            )
        )
    return tuple(rows)


def _build_lcl_anchor_pointer_row() -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(
        datum_address=LCL_ANCHOR_POINTER_ADDR,
        raw=[
            [LCL_ANCHOR_POINTER_ADDR, "~", "0-0-11"],
            [LCL_ANCHOR_POINTER_LABEL],
        ],
    )


def _read_existing(
    store: SqliteSystemDatumStoreAdapter, name: str
) -> AuthoritativeDatumDocument:
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=TENANT)
    )
    for doc in catalog.documents:
        if (
            f".{SANDBOX}." in doc.document_id
            and doc.document_id.split(".")[3] == name
        ):
            return doc
    raise SystemExit(f"existing agro_erp.{name} not found in catalog")


def _replace_document_rows(
    existing: AuthoritativeDatumDocument,
    new_rows: tuple[AuthoritativeDatumDocumentRow, ...],
    *,
    replace_address_prefix: str | None,
    name: str,
) -> tuple[AuthoritativeDatumDocument, str]:
    """Build a new ``AuthoritativeDatumDocument`` from ``existing``'s shape
    with ``new_rows`` integrated.

    ``replace_address_prefix`` makes the merge idempotent: existing rows whose
    ``datum_address`` starts with that prefix are dropped before ``new_rows``
    are appended. For LCL the taxonomy lives at ``4-2-*`` — passing that
    prefix swaps the whole taxonomy block on each run instead of stacking
    duplicate rows. Pass ``None`` to keep every existing row (the anchor
    extension takes that path; idempotency is enforced upstream by the
    1-0-2 presence check).
    """
    if replace_address_prefix:
        preserved = tuple(
            r for r in existing.rows
            if not r.datum_address.startswith(replace_address_prefix)
        )
    else:
        preserved = tuple(existing.rows)
    combined = (*preserved, *new_rows)

    placeholder = format_canonical_document_id(
        prefix="lv",
        msn_id=MSN_ID,
        sandbox=SANDBOX,
        name=name,
        version_hash="0" * 64,
    )
    candidate = dataclasses.replace(
        existing,
        document_id=placeholder,
        rows=combined,
    )
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:"):]
    real_id = format_canonical_document_id(
        prefix="lv",
        msn_id=MSN_ID,
        sandbox=SANDBOX,
        name=name,
        version_hash=real_hash,
    )
    return dataclasses.replace(candidate, document_id=real_id), real_hash


def _upsert_documents_row(
    authority_db: Path, *, name: str, document_id: str, version_hash: str
) -> None:
    now = int(time.time() * 1000)
    conn = sqlite3.connect(authority_db)
    try:
        conn.execute(
            "DELETE FROM documents WHERE tenant_id=? AND sandbox=? AND name=?",
            (TENANT, SANDBOX, name),
        )
        is_anchor = 1 if name == ANCHOR_NAME else 0
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
            "version_hash, is_anchor, origin, created_at) "
            "VALUES (?, ?, 'lv', ?, ?, ?, ?, ?, 'local', ?)",
            (
                TENANT,
                document_id,
                MSN_ID,
                SANDBOX,
                name,
                f"sha256:{version_hash}",
                is_anchor,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def promote(*, authority_db: Path) -> dict:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)

    # ------------------------------------------------------------------
    # 1. lcl doc — append the 46 taxonomy rows below the 4 template headers.
    # ------------------------------------------------------------------
    existing_lcl = _read_existing(store, LCL_NAME)
    taxonomy_rows = _build_lcl_taxonomy_rows()
    new_lcl, lcl_hash = _replace_document_rows(
        existing_lcl,
        taxonomy_rows,
        replace_address_prefix="4-2-",
        name=LCL_NAME,
    )
    store.replace_single_document_efficient(
        tenant_id=TENANT,
        prior_document_id=existing_lcl.document_id,
        updated_document=new_lcl,
    )
    _upsert_documents_row(
        authority_db, name=LCL_NAME, document_id=new_lcl.document_id, version_hash=lcl_hash
    )

    # ------------------------------------------------------------------
    # 2. anchor — add the LCL file pointer at row 1-0-2. Idempotent: if
    #    the row is already present, skip; otherwise extend + re-derive id.
    # ------------------------------------------------------------------
    existing_anchor = _read_existing(store, ANCHOR_NAME)
    has_lcl_pointer = any(
        r.datum_address == LCL_ANCHOR_POINTER_ADDR for r in existing_anchor.rows
    )
    if has_lcl_pointer:
        anchor_result = {
            "skipped": "lcl pointer already present at 1-0-2",
            "document_id": existing_anchor.document_id,
        }
    else:
        anchor_pointer = (_build_lcl_anchor_pointer_row(),)
        new_anchor, anchor_hash = _replace_document_rows(
            existing_anchor,
            anchor_pointer,
            replace_address_prefix=None,
            name=ANCHOR_NAME,
        )
        store.replace_single_document_efficient(
            tenant_id=TENANT,
            prior_document_id=existing_anchor.document_id,
            updated_document=new_anchor,
        )
        _upsert_documents_row(
            authority_db,
            name=ANCHOR_NAME,
            document_id=new_anchor.document_id,
            version_hash=anchor_hash,
        )
        anchor_result = {
            "prior_document_id": existing_anchor.document_id,
            "document_id": new_anchor.document_id,
            "version_hash": anchor_hash,
            "new_row_count": len(new_anchor.rows),
        }

    return {
        "lcl": {
            "prior_document_id": existing_lcl.document_id,
            "document_id": new_lcl.document_id,
            "version_hash": lcl_hash,
            "taxonomy_rows_added": len(taxonomy_rows),
            "total_row_count": len(new_lcl.rows),
        },
        "anchor": anchor_result,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--authority-db",
        required=True,
        type=Path,
        help="Path to mos_authority.sqlite3. Point at an isolated copy for dry-run.",
    )
    args = ap.parse_args()
    if not args.authority_db.exists():
        raise SystemExit(f"authority db missing: {args.authority_db}")
    result = promote(authority_db=args.authority_db)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
