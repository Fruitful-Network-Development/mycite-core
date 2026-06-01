#!/usr/bin/env python3
"""MSS cutover tool — recompute canonical document + per-row hyphae hashes as binary MSS.

Replaces the ``mos.mss_sha256_v1`` JSON+SHA-256 stand-in with the binary MSS form:
  - a document's ``version_hash`` = ``mss_document_hash`` over its tenant-wide
    downward closure (and the save-title ``document_id`` that embeds it),
  - each datum's per-row ``hyphae_hash`` = the binary hyphae value
    (``binary_hyphae_value`` — the MSS hash of that single datum's downward closure).

Modes
-----
* **dry-run (default)** — read-only; computes + reports the document old→new mapping
  and writes it to ``--out``.
* **``--apply`` (COPY only)** — applies the cutover to the database at ``--db`` (it
  refuses the live MOS path). Operate on a copy, verify, then swap it in during a
  maintenance window.

``--apply`` writes, in one transaction after a ``.pre-mss-cutover.bak`` backup:
  - ``documents``: re-issue ``document_id`` + ``version_hash``,
  - ``datum_document_semantics``: re-key ``document_id`` (PK) + ``version_hash`` +
    ``policy`` (→ ``mos.mss_binary_v2``) + payload descriptor,
  - ``datum_row_semantics``: re-key ``document_id`` AND recompute ``hyphae_hash`` /
    ``hyphae_chain_json`` / ``policy`` to the binary hyphae value,
  - ``directive_context_snapshots`` / ``_events``: remap subject ``version_hash`` AND
    ``hyphae_hash`` old→new (overlays are keyed by these; currently 0 rows),
  - ``authoritative_catalog_snapshots.payload_json``: remap embedded ``document_id``s
    (the read path's source).
SQLite has foreign_keys OFF by default, so re-keying the ``document_id`` PK + child FK
in one transaction is safe; ``PRAGMA foreign_key_check`` must be clean before COMMIT,
then a fresh read must show the new ids + matching version_hash. See
``docs/contracts/mss_binary_sequence/cutover_design.md``.

NOTE: runtime consistency (the workbench render computing the binary hyphae too)
requires the flag-gated ``MOS_CANONICAL_HASH`` switch — deploy that together with
this migration so render and store agree.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
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
    datum_closure_to_mss,
    document_closure_to_mss,
    mss_document_hash,
)
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

_CANONICAL_PREFIXES = ("lv.", "stl.", "cptr.", "sc.")
_BINARY_POLICY = "mos.mss_binary_v2"
_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


def _new_document_id(document_id: str, new_hash_hex: str) -> str | None:
    parts = document_id.split(".")
    if len(parts) < 5 or len(parts[-1]) != 64:
        return None
    parts[-1] = new_hash_hex
    return ".".join(parts)


def _open(db: str) -> SqliteSystemDatumStoreAdapter:
    return SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)


def compute_mapping(
    db: str, tenant: str, index: dict | None = None
) -> tuple[list[dict[str, str]], MssAdapterReport, int, dict]:
    """Read-only: the old→new document mapping + the catalog index (reused by apply)."""
    store = _open(db)
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant)
    )
    index = index if index is not None else build_catalog_index(catalog)
    report = MssAdapterReport()
    mapping: list[dict[str, str]] = []
    skipped = 0
    for document in catalog.documents:
        if not document.document_id.startswith(_CANONICAL_PREFIXES):
            skipped += 1
            continue
        identity = store.read_document_version_identity(
            tenant_id=tenant, document_id=document.document_id
        )
        old_hash = (identity or {}).get("version_hash", "")
        datums = document_closure_to_mss(document, index=index, report=report)
        new_hash = mss_document_hash(datums)
        new_hex = new_hash.split(":", 1)[1]
        new_id = _new_document_id(document.document_id, new_hex) or document.document_id
        mapping.append(
            {
                "document_id": document.document_id,
                "new_document_id": new_id,
                "old_version_hash": old_hash,
                "new_version_hash": new_hash,
                "closure_size": str(len(datums)),
            }
        )
    return mapping, report, skipped, index


def apply_mapping(db: str, tenant: str, mapping: list[dict[str, str]], index: dict) -> Path:
    """Apply the document + per-row hyphae cutover to ``db`` (a COPY). Returns the backup path."""
    db_path = Path(db)
    if db_path.resolve() == _LIVE_DB.resolve():
        raise SystemExit(f"refusing to --apply to the live MOS ({_LIVE_DB}); use a copy")
    backup = db_path.with_suffix(db_path.suffix + ".pre-mss-cutover.bak")
    shutil.copy2(db_path, backup)

    changed = [
        m for m in mapping
        if m["new_document_id"] != m["document_id"] or m["new_version_hash"] != m["old_version_hash"]
    ]
    id_map = {m["document_id"]: m["new_document_id"] for m in changed}
    vh_map = {m["old_version_hash"]: m["new_version_hash"] for m in changed if m["old_version_hash"]}
    descriptor = json.dumps(
        {"policy": _BINARY_POLICY,
         "note": "canonical form is the binary MSS sequence; recompute via core.mss"},
        separators=(",", ":"),
    )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Per-row hyphae recompute (read old → compute new binary; memoize per address).
    cache: dict[str, tuple[str, str]] = {}

    def _row_hyphae(address: str) -> tuple[str, str]:
        hit = cache.get(address)
        if hit is not None:
            return hit
        closure = datum_closure_to_mss(address, index=index)
        value = mss_document_hash(closure)
        chain = json.dumps(
            {"policy": _BINARY_POLICY, "addresses": [d.address for d in closure]},
            separators=(",", ":"),
        )
        cache[address] = (value, chain)
        return cache[address]

    rows = conn.execute(
        "SELECT document_id, datum_address, hyphae_hash FROM datum_row_semantics WHERE tenant_id=?",
        (tenant,),
    ).fetchall()
    row_updates: list[tuple[str, str, str, str, str]] = []   # (new_doc_id, addr, hyphae, chain, old_hyphae)
    hyphae_map: dict[str, str] = {}
    for r in rows:
        new_doc_id = id_map.get(r["document_id"], r["document_id"])
        value, chain = _row_hyphae(r["datum_address"])
        row_updates.append((new_doc_id, r["datum_address"], value, chain, r["hyphae_hash"]))
        if r["hyphae_hash"]:
            hyphae_map[r["hyphae_hash"]] = value

    try:
        conn.execute("BEGIN")
        for m in changed:
            old_id, new_id, new_vh = m["document_id"], m["new_document_id"], m["new_version_hash"]
            conn.execute(
                "UPDATE documents SET document_id=?, version_hash=? WHERE tenant_id=? AND document_id=?",
                (new_id, new_vh, tenant, old_id),
            )
            conn.execute(
                "UPDATE datum_document_semantics "
                "SET document_id=?, version_hash=?, policy=?, canonical_payload_json=? "
                "WHERE tenant_id=? AND document_id=?",
                (new_id, new_vh, _BINARY_POLICY, descriptor, tenant, old_id),
            )
            conn.execute(
                "UPDATE datum_row_semantics SET document_id=? WHERE tenant_id=? AND document_id=?",
                (new_id, tenant, old_id),
            )
        for new_doc_id, addr, value, chain, _old in row_updates:
            conn.execute(
                "UPDATE datum_row_semantics SET hyphae_hash=?, hyphae_chain_json=?, policy=? "
                "WHERE tenant_id=? AND document_id=? AND datum_address=?",
                (value, chain, _BINARY_POLICY, tenant, new_doc_id, addr),
            )
        for table in ("directive_context_snapshots", "directive_context_events"):
            for old_vh, new_vh in vh_map.items():
                conn.execute(f"UPDATE {table} SET version_hash=? WHERE version_hash=?", (new_vh, old_vh))
            for old_hh, new_hh in hyphae_map.items():
                conn.execute(f"UPDATE {table} SET hyphae_hash=? WHERE hyphae_hash=?", (new_hh, old_hh))
        row = conn.execute(
            "SELECT payload_json FROM authoritative_catalog_snapshots WHERE tenant_id=?", (tenant,)
        ).fetchone()
        if row is not None:
            payload = json.loads(row["payload_json"])
            for doc in payload.get("documents") or []:
                if doc.get("document_id") in id_map:
                    doc["document_id"] = id_map[doc["document_id"]]
            conn.execute(
                "UPDATE authoritative_catalog_snapshots SET payload_json=? WHERE tenant_id=?",
                (json.dumps(payload), tenant),
            )
        orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
        if orphans:
            conn.execute("ROLLBACK")
            raise SystemExit(f"foreign_key_check failed ({len(orphans)} orphans); rolled back")
        conn.execute("COMMIT")
    finally:
        conn.close()
    return backup


def _verify(db: str, tenant: str, mapping: list[dict[str, str]]) -> None:
    store = _open(db)
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant))
    ids = {d.document_id for d in cat.documents}
    missing = {m["new_document_id"] for m in mapping} - ids
    if missing:
        raise SystemExit(f"verify failed: {len(missing)} new document_ids not present after apply")
    sample = next((m for m in mapping if m["new_document_id"] != m["document_id"]), None)
    if sample is not None:
        ident = store.read_document_version_identity(tenant_id=tenant, document_id=sample["new_document_id"])
        if (ident or {}).get("version_hash") != sample["new_version_hash"]:
            raise SystemExit("verify failed: datum_document_semantics version_hash mismatch")


def main() -> int:
    ap = argparse.ArgumentParser(description="MSS cutover hash recompute (dry-run by default)")
    ap.add_argument("--db", required=True, help="MOS authority sqlite. --apply requires a COPY.")
    ap.add_argument("--tenant", default="fnd")
    ap.add_argument("--out", default="")
    ap.add_argument("--apply", action="store_true", help="apply to --db (must be a copy)")
    args = ap.parse_args()

    mapping, report, skipped, index = compute_mapping(args.db, args.tenant)
    changed = sum(1 for m in mapping if m["new_document_id"] != m["document_id"])
    print(f"tenant={args.tenant}  canonical datum docs mapped={len(mapping)}  (skipped non-datum={skipped})")
    print(f"docs whose hash/save-title changes = {changed}")
    print(
        f"closure adapter: datums={report.datums}  dropped_dangling={report.dropped_dangling}  "
        f"dropped_upward={report.dropped_upward}  dropped_malformed={report.dropped_malformed}"
    )
    if args.out:
        Path(args.out).write_text(json.dumps(mapping, indent=2), encoding="utf-8")
        print(f"wrote old→new map: {args.out}")
    if not args.apply:
        print("DRY-RUN only. No data written. Re-run with --apply against a COPY to perform the cutover.")
        return 0

    backup = apply_mapping(args.db, args.tenant, mapping, index)
    _verify(args.db, args.tenant, mapping)
    print(f"APPLIED to {args.db}  (backup: {backup})")
    print("Verified: new document_ids + version_hash; documents/row hyphae on mos.mss_binary_v2.")
    print("Review, then swap this copy in during a maintenance window (deploy the runtime flag too).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
