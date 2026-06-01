#!/usr/bin/env python3
"""MSS cutover tool — recompute canonical document hashes as the binary MSS form.

Recomputes every canonical datum document's ``version_hash`` as the **binary MSS**
hash (``core.mss.mss_document_hash`` over the document's tenant-wide downward
closure, via ``document_closure_to_mss``), replacing the ``mos.mss_sha256_v1``
JSON+SHA-256 stand-in, and reissues the save-title (``document_id``) that embeds it.

Modes
-----
* **dry-run (default)** — read-only; computes + reports the old→new mapping and
  writes it to ``--out``. No data is written.
* **``--apply`` (COPY only)** — applies the mapping to the database at ``--db``,
  which **must not be the live MOS** (the tool refuses the canonical live path).
  Always operate on a copy, verify, then swap it in during a maintenance window.

What ``--apply`` writes (one transaction, after a ``.pre-mss-cutover.bak`` backup):
  - ``documents``: ``document_id`` + ``version_hash`` (lv/stl/cptr rows),
  - ``datum_document_semantics``: ``document_id`` (PK) + ``version_hash`` + ``policy``
    (→ ``mos.mss_binary_v2``) + a ``canonical_payload_json`` descriptor,
  - ``datum_row_semantics``: re-key ``document_id`` (per-row hyphae VALUES are left
    on the existing scheme — a per-row binary-hyphae cutover is a separate phase),
  - ``directive_context_snapshots`` / ``_events``: remap the subject ``version_hash``
    old→new (overlays are keyed by it; currently 0 rows, so a no-op),
  - ``authoritative_catalog_snapshots.payload_json``: remap embedded ``document_id``s
    (this snapshot is what the read path serves).
Then ``PRAGMA foreign_key_check`` must be clean, and a fresh read must show the new
ids/hashes. See ``docs/contracts/mss_binary_sequence/cutover_design.md``.
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
    document_closure_to_mss,
    mss_document_hash,
)
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

# Canonical datum-document id prefixes (type.msn.sandbox.name.hash). Operational
# scalar docs (newsletter logs, aws_csm profiles, …) are NOT datum documents and
# are skipped — they keep their existing identity.
_CANONICAL_PREFIXES = ("lv.", "stl.", "cptr.", "sc.")
_BINARY_POLICY = "mos.mss_binary_v2"
# The live MOS — --apply refuses to touch it. Operate on a copy.
_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


def _new_document_id(document_id: str, new_hash_hex: str) -> str | None:
    """Replace the trailing 64-hex hash segment of a canonical document_id."""
    parts = document_id.split(".")
    if len(parts) < 5 or len(parts[-1]) != 64:
        return None
    parts[-1] = new_hash_hex
    return ".".join(parts)


def compute_mapping(db: str, tenant: str) -> tuple[list[dict[str, str]], MssAdapterReport, int]:
    """Read-only: the old→new (document_id, version_hash) mapping for every
    canonical datum document. Returns (mapping, adapter_report, skipped_count)."""
    store = SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(
        AuthoritativeDatumDocumentRequest(tenant_id=tenant)
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
    return mapping, report, skipped


def apply_mapping(db: str, tenant: str, mapping: list[dict[str, str]]) -> Path:
    """Apply the cutover to the database at ``db`` (a COPY). Returns the backup path.

    SQLite connections have foreign_keys OFF by default, so re-keying the
    ``document_id`` PK + its child FK in the same transaction is safe; we then run
    ``foreign_key_check`` to confirm no orphans.
    """
    db_path = Path(db)
    if db_path.resolve() == _LIVE_DB.resolve():
        raise SystemExit(f"refusing to --apply to the live MOS ({_LIVE_DB}); use a copy")
    backup = db_path.with_suffix(db_path.suffix + ".pre-mss-cutover.bak")
    shutil.copy2(db_path, backup)

    changed = [m for m in mapping if m["new_document_id"] != m["document_id"]
               or m["new_version_hash"] != m["old_version_hash"]]
    id_map = {m["document_id"]: m["new_document_id"] for m in changed}
    vh_map = {m["old_version_hash"]: m["new_version_hash"] for m in changed if m["old_version_hash"]}
    descriptor = json.dumps(
        {"policy": _BINARY_POLICY,
         "note": "canonical form is the binary MSS sequence; recompute via core.mss.mss_document_hash"},
        separators=(",", ":"),
    )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        for m in changed:
            old_id, new_id = m["document_id"], m["new_document_id"]
            new_vh = m["new_version_hash"]
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
        for old_vh, new_vh in vh_map.items():
            conn.execute("UPDATE directive_context_snapshots SET version_hash=? WHERE version_hash=?", (new_vh, old_vh))
            conn.execute("UPDATE directive_context_events SET version_hash=? WHERE version_hash=?", (new_vh, old_vh))
        # Rewrite the catalog snapshot (the read path's source) with remapped ids.
        row = conn.execute(
            "SELECT payload_json FROM authoritative_catalog_snapshots WHERE tenant_id=?", (tenant,)
        ).fetchone()
        if row is not None:
            payload = json.loads(row["payload_json"])
            for doc in payload.get("documents") or []:
                did = doc.get("document_id")
                if did in id_map:
                    doc["document_id"] = id_map[did]
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
    store = SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant))
    ids = {d.document_id for d in cat.documents}
    expected_new = {m["new_document_id"] for m in mapping}
    missing = expected_new - ids
    if missing:
        raise SystemExit(f"verify failed: {len(missing)} new document_ids not present after apply")
    sample = next((m for m in mapping if m["new_document_id"] != m["document_id"]), None)
    if sample is not None:
        ident = store.read_document_version_identity(tenant_id=tenant, document_id=sample["new_document_id"])
        if (ident or {}).get("version_hash") != sample["new_version_hash"]:
            raise SystemExit("verify failed: datum_document_semantics version_hash mismatch")


def main() -> int:
    ap = argparse.ArgumentParser(description="MSS cutover hash recompute (dry-run by default)")
    ap.add_argument("--db", required=True, help="MOS authority sqlite. --apply requires a COPY (not the live DB).")
    ap.add_argument("--tenant", default="fnd")
    ap.add_argument("--out", default="", help="write the old→new map JSON here")
    ap.add_argument("--apply", action="store_true", help="apply to --db (must be a copy)")
    args = ap.parse_args()

    mapping, report, skipped = compute_mapping(args.db, args.tenant)
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

    backup = apply_mapping(args.db, args.tenant, mapping)
    _verify(args.db, args.tenant, mapping)
    print(f"APPLIED to {args.db}  (backup: {backup})")
    print("Verified: new document_ids present + datum_document_semantics version_hash matches.")
    print("Review, then swap this copy in during a maintenance window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
