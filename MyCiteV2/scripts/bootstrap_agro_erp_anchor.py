"""Bootstrap the AGRO-ERP sandbox content in the MOS authority database.

Materialises two canonical datum documents for the ``agro_erp`` sandbox:

1. **Anchor** (``lv.<msn>.agro_erp.anchor.<hash>``) — 18 rows defining the
   primitive SAMRAS units (0-0-1..0-0-11), the ``txa-SAMRAS`` magnitude
   (1-1-1) regenerated from the actual taxonomy address set, plus
   abstraction (2-0-1, 2-1-2) and babelette (3-1-1, 3-1-2) rows.
2. **Taxonomy source** (``lv.<msn>.agro_erp.txa.<hash>``) — 816 rows
   (815 taxa as 4-2-N four-tuples ``[rf.3-1-1, <node-addr>, rf.3-1-2,
   <512-bit ASCII title>]`` per the ``anthology.json`` 4-2-N precedent,
   plus a 5-0-1 collection naming the full 815-entry id set).

Input: the two legacy-staging JSON files at
``/srv/webapps/mycite/fnd/{lv,sc}.*.agro_erp*.json``.

Side effects: REPLACES any existing ``agro_erp`` rows in
``documents``, ``datum_document_semantics``, ``datum_row_semantics``,
and the cached catalog snapshot.

Idempotent on the row set: re-running with the same inputs produces the
same canonical document_ids and is a no-op.

Usage::

    python -m MyCiteV2.scripts.bootstrap_agro_erp_anchor \\
        --authority-db /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 \\
        --tenant-id fnd \\
        --msn-id 3-2-3-17-77-1-6-4-1-4 \\
        --lv-staging /srv/webapps/mycite/fnd/lv.3-2-3-17-77-2-6-3-1-6.agro_erp.\\<hash\\>.json \\
        --sc-staging /srv/webapps/mycite/fnd/sc.3-2-3-17-77-1-6-4-1-4.agro_erp.txa.\\<hash\\>.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.document_naming import format_canonical_document_id
from MyCiteV2.packages.core.mss import compute_mss_hash
from MyCiteV2.packages.core.structures.samras.codec import (
    decode_canonical_bitstream,
    encode_canonical_structure_from_addresses,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)

SANDBOX = "agro_erp"
DEFAULT_TENANT_ID = "fnd"
DEFAULT_MSN_ID = "3-2-3-17-77-1-6-4-1-4"
DEFAULT_LV_STAGING = Path("/srv/webapps/mycite/fnd/lv.3-2-3-17-77-2-6-3-1-6.agro_erp.<hash>.json")
DEFAULT_SC_STAGING = Path("/srv/webapps/mycite/fnd/sc.3-2-3-17-77-1-6-4-1-4.agro_erp.txa.<hash>.json")

TITLE_BIT_WIDTH = 512  # niu-baciloid-256-64 = 64 base-256 digits = 64 ASCII bytes = 512 bits

PRIMITIVE_ROWS: tuple[tuple[str, str], ...] = (
    ("0-0-1", "time-ordinal-position"),
    ("0-0-2", "time-incramental-unit"),
    ("0-0-3", "spacial-ordinal-position"),
    ("0-0-4", "spacial-incramental-unit"),
    ("0-0-5", "nominal-ordinal-position"),
    ("0-0-6", "nominal-incramental-unit"),
    ("0-0-7", "mass-ordinal-position"),
    ("0-0-8", "miu"),
    ("0-0-9", "fiat-currency-unit"),
    ("0-0-10", "photon-particle-unit"),
    ("0-0-11", "json-file-unit"),
)


def _fix_address(addr: str) -> str:
    """Replace the single known ``_`` → ``-`` typo in the staged source."""
    return addr.replace("_", "-")


def _ascii_to_binary(text: str, width: int) -> str:
    bits = "".join(f"{ord(ch):08b}" for ch in text)
    if len(bits) > width:
        raise ValueError(f"title {text!r} is {len(bits)} bits, exceeds babelette width {width}")
    return bits + "0" * (width - len(bits))


def _binary_to_ascii(bits: str) -> str:
    chars = []
    for i in range(0, len(bits), 8):
        byte = int(bits[i : i + 8], 2)
        if byte == 0:
            break
        chars.append(chr(byte))
    return "".join(chars)


def _load_taxonomy(sc_staging: Path) -> list[tuple[str, str]]:
    """Return [(node_address, ascii_title), ...] in 4-1-N insertion order."""
    with sc_staging.open() as f:
        sc = json.load(f)
    das = sc["datum_addressing_abstraction_space"]
    entries: list[tuple[str, str]] = []
    for key, val in das.items():
        if not key.startswith("4-1-"):
            continue
        addr = _fix_address(val[0][2])
        title = val[1][0]
        entries.append((addr, title))
    return entries


def _build_magnitude_bitstream(taxonomy: list[tuple[str, str]]) -> tuple[str, set[str]]:
    """Return (canonical SAMRAS bitstream, full address set incl. anonymous parents)."""
    named = {addr for addr, _ in taxonomy}
    full: set[str] = set()
    for addr in named:
        segments = addr.split("-")
        for depth in range(1, len(segments) + 1):
            full.add("-".join(segments[: depth + 0]))
    structure = encode_canonical_structure_from_addresses(sorted(full))
    decoded = decode_canonical_bitstream(structure.bitstream)
    if set(decoded.addresses) != full:
        raise SystemExit("SAMRAS magnitude roundtrip address-set mismatch")
    return structure.bitstream, full


def _build_anchor_rows(magnitude_bits: str, sc_legacy_filename: str) -> tuple[AuthoritativeDatumDocumentRow, ...]:
    rows: list[AuthoritativeDatumDocumentRow] = []
    for address, label in PRIMITIVE_ROWS:
        rows.append(AuthoritativeDatumDocumentRow(
            datum_address=address,
            raw=[[address, "~", "0-0-0"], [label]],
        ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="1-0-1",
        raw=[["1-0-1", "~", "0-0-11"], [sc_legacy_filename]],
    ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="1-1-1",
        raw=[["1-1-1", "0-0-5", magnitude_bits], ["txa-SAMRAS"]],
    ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="1-1-2",
        raw=[["1-1-2", "0-0-6", "256"], ["nominal-bacillete-256"]],
    ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="2-0-1",
        raw=[["2-0-1", "~", "1-1-1"], ["SAMRAS-space-txa"]],
    ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="2-1-2",
        raw=[["2-1-2", "1-1-2", "32"], ["niu-baciloid-256-64"]],
    ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="3-1-1",
        raw=[["3-1-1", "2-0-1", "0"], ["SAMRAS-babelette-txa_id"]],
    ))
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="3-1-2",
        raw=[["3-1-2", "2-1-2", "0"], ["title-babelette"]],
    ))
    return tuple(rows)


def _build_txa_rows(taxonomy: list[tuple[str, str]]) -> tuple[AuthoritativeDatumDocumentRow, ...]:
    rows: list[AuthoritativeDatumDocumentRow] = []
    collection_refs: list[str] = []
    for index, (node_addr, title) in enumerate(taxonomy, start=1):
        key = f"4-2-{index}"
        binary_title = _ascii_to_binary(title, TITLE_BIT_WIDTH)
        rows.append(AuthoritativeDatumDocumentRow(
            datum_address=key,
            raw=[[key, "rf.3-1-1", node_addr, "rf.3-1-2", binary_title], [title]],
        ))
        collection_refs.append(key)
    rows.append(AuthoritativeDatumDocumentRow(
        datum_address="5-0-1",
        raw=[["5-0-1", "~", *collection_refs], ["txa_id_collection"]],
    ))
    return tuple(rows)


def _compute_hash(document: AuthoritativeDatumDocument) -> str:
    identity = compute_mss_hash(document)
    version_hash = identity["version_hash"]
    if version_hash.startswith("sha256:"):
        version_hash = version_hash[len("sha256:"):]
    return version_hash


def _build_document(
    *,
    msn_id: str,
    name: str,
    is_anchor: bool,
    rows: tuple[AuthoritativeDatumDocumentRow, ...],
    legacy_alias: str,
    canonical_sc_filename: str = "",
) -> tuple[AuthoritativeDatumDocument, str]:
    placeholder = "0" * 64
    placeholder_id = format_canonical_document_id(
        prefix="lv", msn_id=msn_id, sandbox=SANDBOX, name=name, version_hash=placeholder,
    )
    metadata: dict = {"legacy_alias": legacy_alias}
    candidate = AuthoritativeDatumDocument(
        document_id=placeholder_id,
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"sandbox/agro-erp/lv.{msn_id}.{SANDBOX}.{name}.json",
        canonical_name=name,
        tool_id=SANDBOX,
        is_anchor=is_anchor,
        document_metadata=metadata,
        rows=rows,
    )
    real_hash = _compute_hash(candidate)
    real_id = format_canonical_document_id(
        prefix="lv", msn_id=msn_id, sandbox=SANDBOX, name=name, version_hash=real_hash,
    )
    final = AuthoritativeDatumDocument(
        document_id=real_id,
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"sandbox/agro-erp/lv.{msn_id}.{SANDBOX}.{name}.json",
        canonical_name=name,
        tool_id=SANDBOX,
        is_anchor=is_anchor,
        document_metadata=metadata,
        rows=rows,
    )
    return final, real_hash


def _replace_documents_table_rows(
    *,
    authority_db: Path,
    tenant_id: str,
    msn_id: str,
    anchor_hash: str,
    anchor_alias: str,
    txa_hash: str,
    txa_alias: str,
) -> dict[str, str]:
    """Replace the agro_erp rows in the ``documents`` index table."""
    now = int(time.time() * 1000)
    conn = sqlite3.connect(authority_db)
    try:
        conn.execute(
            "DELETE FROM documents WHERE tenant_id = ? AND sandbox = ?",
            (tenant_id, SANDBOX),
        )
        anchor_id = format_canonical_document_id(
            prefix="lv", msn_id=msn_id, sandbox=SANDBOX, name="anchor", version_hash=anchor_hash,
        )
        txa_id = format_canonical_document_id(
            prefix="lv", msn_id=msn_id, sandbox=SANDBOX, name="txa", version_hash=txa_hash,
        )
        # legacy_alias column retired 2026-05-27; anchor_alias/txa_alias dropped.
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
            "version_hash, is_anchor, origin, created_at) "
            "VALUES (?, ?, 'lv', ?, ?, 'anchor', ?, 1, 'local', ?)",
            (tenant_id, anchor_id, msn_id, SANDBOX, f"sha256:{anchor_hash}", now),
        )
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
            "version_hash, is_anchor, origin, created_at) "
            "VALUES (?, ?, 'lv', ?, ?, 'txa', ?, 0, 'local', ?)",
            (tenant_id, txa_id, msn_id, SANDBOX, f"sha256:{txa_hash}", now),
        )
        conn.commit()
        return {"anchor_id": anchor_id, "txa_id": txa_id}
    finally:
        conn.close()


def bootstrap(
    *,
    authority_db: Path,
    tenant_id: str,
    msn_id: str,
    lv_staging: Path,
    sc_staging: Path,
    dry_run: bool,
) -> dict[str, object]:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    if not lv_staging.exists():
        raise SystemExit(f"lv staging missing: {lv_staging}")
    if not sc_staging.exists():
        raise SystemExit(f"sc staging missing: {sc_staging}")

    taxonomy = _load_taxonomy(sc_staging)
    magnitude_bits, full_address_set = _build_magnitude_bitstream(taxonomy)

    sc_legacy_filename = sc_staging.name
    anchor_alias = f"sandbox:agro-erp:{lv_staging.name}"
    txa_alias = f"sandbox:agro-erp:{sc_staging.name}"

    anchor_rows = _build_anchor_rows(magnitude_bits, sc_legacy_filename)
    anchor_document, anchor_hash = _build_document(
        msn_id=msn_id, name="anchor", is_anchor=True,
        rows=anchor_rows, legacy_alias=anchor_alias,
    )

    txa_rows = _build_txa_rows(taxonomy)
    txa_document, txa_hash = _build_document(
        msn_id=msn_id, name="txa", is_anchor=False,
        rows=txa_rows, legacy_alias=txa_alias,
    )

    summary: dict[str, object] = {
        "anchor_document_id": anchor_document.document_id,
        "anchor_row_count": len(anchor_rows),
        "txa_document_id": txa_document.document_id,
        "txa_row_count": len(txa_rows),
        "magnitude_bits": len(magnitude_bits),
        "magnitude_address_count": len(full_address_set),
        "taxonomy_count": len(taxonomy),
    }
    if dry_run:
        summary["status"] = "dry_run"
        return summary

    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
    )
    prior_anchor_id: str | None = None
    prior_txa_id: str | None = None
    for document in catalog.documents:
        if f".{SANDBOX}." not in document.document_id:
            continue
        if document.is_anchor:
            prior_anchor_id = document.document_id
        else:
            prior_txa_id = document.document_id

    store.replace_single_document_efficient(
        tenant_id=tenant_id,
        prior_document_id=prior_anchor_id,
        updated_document=anchor_document,
    )
    store.replace_single_document_efficient(
        tenant_id=tenant_id,
        prior_document_id=prior_txa_id,
        updated_document=txa_document,
    )

    ids = _replace_documents_table_rows(
        authority_db=authority_db,
        tenant_id=tenant_id,
        msn_id=msn_id,
        anchor_hash=anchor_hash,
        anchor_alias=anchor_alias,
        txa_hash=txa_hash,
        txa_alias=txa_alias,
    )
    summary["status"] = "created"
    summary["documents_table"] = ids
    summary["prior_anchor_id"] = prior_anchor_id or ""
    summary["prior_txa_id"] = prior_txa_id or ""
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-db", type=Path, required=True)
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--msn-id", default=DEFAULT_MSN_ID)
    parser.add_argument("--lv-staging", type=Path, default=DEFAULT_LV_STAGING)
    parser.add_argument("--sc-staging", type=Path, default=DEFAULT_SC_STAGING)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = bootstrap(
        authority_db=args.authority_db,
        tenant_id=args.tenant_id,
        msn_id=args.msn_id,
        lv_staging=args.lv_staging,
        sc_staging=args.sc_staging,
        dry_run=args.dry_run,
    )
    for key, value in result.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
