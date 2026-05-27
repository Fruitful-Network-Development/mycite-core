#!/usr/bin/env python3
"""Promote the re-derived SD-31 district boundary into MOS as a HOPS profile doc.

The 84 ``lv.*.cts_gis.247_17_77_*`` precinct polygons were unioned (shapely) and
cleaned into a single outer-ring outline (sd31_district_boundary.geojson, 1932 pts).
This builds a district-level HOPS profile document that MIRRORS the precinct doc
structure (4->5->6->7 row chain) and writes it via the same path the agro_erp
bootstrap uses:

  1. ``_build_document``: placeholder id -> ``compute_mss_hash`` -> real canonical id.
  2. ``store.replace_single_document_efficient(prior_document_id=<existing or None>,
     updated_document=doc)`` -> catalog snapshot + datum_document_semantics +
     datum_row_semantics (scoped, idempotent).
  3. Upsert the single ``documents`` index row (targeted DELETE-by-name + INSERT;
     NEVER delete-by-sandbox -- that would wipe the 84 precincts).

Idempotent: re-running replaces the prior district doc in place. Point ``--authority-db``
at an ISOLATED COPY for the dry-run; only run against the live DB after the copy verifies.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cts_gis_geojson_hops_utils import encode_hops_coordinate, normalize_ring_open

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.document_naming import format_canonical_document_id
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

TENANT = "fnd"
MSN_ID = "3-2-3-17-77-1-6-4-1-4"
SANDBOX = "cts_gis"
NAME = "247_17_77"  # district group (precincts are 247_17_77_<NNN>)
BINDING_ID = "247-17-77"
LEGACY_ALIAS = "sandbox:cts_gis:sc.3-2-3-17-77-1-6-4-1-4.cts_gis.district-247-17-77.json"
# rf.3-1-5 fixed-width (128-bit) ASCII field. Precinct docs carry a voting-place
# code (e.g. "BAR1-A" = Barberton 1-A). A district-level boundary has no single
# precinct code; "SD31" is a documented placeholder pending authority confirmation.
RF315_TOKEN = "SD31"
RF315_BITS = 128


def _encode_fixed_ascii(token: str, bits: int) -> str:
    """ASCII -> per-char 8-bit, right-null-padded to ``bits`` (mirrors precinct rf.3-1-5)."""
    raw = "".join(format(b, "08b") for b in token.encode("ascii"))
    if len(raw) > bits:
        raise ValueError(f"token {token!r} exceeds {bits} bits")
    return raw.ljust(bits, "0")


def _load_outline(geojson_path: Path) -> list[list[float]]:
    g = json.loads(geojson_path.read_text())
    feats = g.get("features") or [g]
    geom = feats[0].get("geometry", feats[0])
    if geom.get("type") != "Polygon":
        raise SystemExit(f"expected single Polygon, got {geom.get('type')}")
    return normalize_ring_open(geom["coordinates"][0])  # outer ring, open


def _build_rows(coords: list[list[float]]) -> tuple[AuthoritativeDatumDocumentRow, ...]:
    n = len(coords)
    ring_addr = f"4-{n}-1"
    ring_base: list[str] = [ring_addr]
    for lng, lat in coords:
        ring_base.append("rf.3-1-1")
        ring_base.append(encode_hops_coordinate(lng, lat))
    binding_bits = _encode_fixed_ascii(RF315_TOKEN, RF315_BITS)
    return (
        AuthoritativeDatumDocumentRow(datum_address=ring_addr, raw=[ring_base, ["polygon_1"]]),
        AuthoritativeDatumDocumentRow(
            datum_address="5-0-1",
            raw=[["5-0-1", "~", ring_addr], [f"district_{NAME}_polygon_1"]],
        ),
        AuthoritativeDatumDocumentRow(
            datum_address="6-0-1",
            raw=[["6-0-1", "~", "5-0-1"], [f"district_{NAME}_boundary_collection"]],
        ),
        AuthoritativeDatumDocumentRow(
            datum_address="7-3-1",
            raw=[
                ["7-3-1", "rf.3-1-4", BINDING_ID, "rf.3-1-5", binding_bits, "6-0-1", "1"],
                [f"district_{NAME}"],
            ],
        ),
    )


def _build_document(rows) -> tuple[AuthoritativeDatumDocument, str]:
    placeholder = format_canonical_document_id(
        prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=NAME, version_hash="0" * 64
    )
    metadata = {
        "legacy_alias": LEGACY_ALIAS,
        "derivation": "shapely union of 84 lv.*.cts_gis.247_17_77_* precinct polygons, "
        "cleaned to a single outer-ring outline; promote_sd31_district_boundary.py",
    }
    kw = dict(
        source_kind="sandbox_source",
        document_name=f"lv.{MSN_ID}.{SANDBOX}.{NAME}",
        relative_path=f"sandbox/cts-gis/lv.{MSN_ID}.{SANDBOX}.{NAME}.json",
        canonical_name=NAME,
        tool_id=SANDBOX,
        is_anchor=False,
        document_metadata=metadata,
        rows=rows,
    )
    candidate = AuthoritativeDatumDocument(document_id=placeholder, **kw)
    identity = compute_mss_hash(candidate)
    real_hash = identity["version_hash"]
    if real_hash.startswith("sha256:"):
        real_hash = real_hash[len("sha256:"):]
    real_id = format_canonical_document_id(
        prefix="lv", msn_id=MSN_ID, sandbox=SANDBOX, name=NAME, version_hash=real_hash
    )
    return AuthoritativeDatumDocument(document_id=real_id, **kw), real_hash


def _prior_district_id(authority_db: Path) -> str | None:
    conn = sqlite3.connect(authority_db)
    try:
        row = conn.execute(
            "SELECT document_id FROM documents WHERE tenant_id=? AND sandbox=? AND name=?",
            (TENANT, SANDBOX, NAME),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _upsert_documents_row(authority_db: Path, document_id: str, version_hash: str) -> None:
    now = int(time.time() * 1000)
    conn = sqlite3.connect(authority_db)
    try:
        conn.execute(
            "DELETE FROM documents WHERE tenant_id=? AND sandbox=? AND name=?",
            (TENANT, SANDBOX, NAME),
        )
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
            "version_hash, is_anchor, origin, legacy_alias, created_at) "
            "VALUES (?, ?, 'lv', ?, ?, ?, ?, 0, 'local', ?, ?)",
            (TENANT, document_id, MSN_ID, SANDBOX, NAME, f"sha256:{version_hash}", LEGACY_ALIAS, now),
        )
        conn.commit()
    finally:
        conn.close()


def promote(*, authority_db: Path, geojson_path: Path) -> dict:
    coords = _load_outline(geojson_path)
    rows = _build_rows(coords)
    document, real_hash = _build_document(rows)

    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    prior = _prior_district_id(authority_db)
    store.replace_single_document_efficient(
        tenant_id=TENANT, prior_document_id=prior, updated_document=document
    )
    _upsert_documents_row(authority_db, document.document_id, real_hash)
    return {
        "document_id": document.document_id,
        "version_hash": real_hash,
        "ring_coords": len(coords),
        "prior_document_id": prior,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--authority-db", required=True, type=Path)
    ap.add_argument(
        "--geojson",
        type=Path,
        default=Path(
            "/srv/agentic/evidence/cts-gis-authority-garland-epic-2026-05-27/"
            "sd31_district_boundary.geojson"
        ),
    )
    args = ap.parse_args()
    if not args.authority_db.exists():
        raise SystemExit(f"authority db missing: {args.authority_db}")
    result = promote(authority_db=args.authority_db, geojson_path=args.geojson)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
