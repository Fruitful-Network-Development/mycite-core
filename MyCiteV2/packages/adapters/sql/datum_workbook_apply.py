"""Store-bound executor for a planned datum-workbook migration.

This is the ONLY SQL-aware piece of the workbook pipeline: the pure planner
(:mod:`MyCiteV2.packages.core.datum_ops.migrate`) produces a :class:`MigrationPlan`;
this module loads a sandbox into a :class:`Workbook`, backs up the DB, writes the
touched sheets in dependency order, updates the ``documents`` index, and verifies —
restoring from the backup if verification fails.

Atomicity caveat: ``replace_single_document_efficient`` opens its own connection
per call, so a multi-doc cascade is not a single transaction. The mitigation is the
mandatory pre-write backup + post-write verify + restore-on-failure, and the standing
discipline of applying in a quiet window (mirrors the ingest scripts).
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from MyCiteV2.packages.core.datum_ops import Workbook, check_step
from MyCiteV2.packages.core.datum_ops.migrate import MigrationPlan
from MyCiteV2.packages.core.document_naming import parse_canonical_document_id
from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

from .datum_store import SqliteSystemDatumStoreAdapter


class WorkbookApplyError(RuntimeError):
    """Raised when a workbook migration fails to write or verify."""


def load_workbook(store: SqliteSystemDatumStoreAdapter, *, tenant_id: str, sandbox: str) -> Workbook:
    """Load every document of one sandbox into a Workbook keyed by document name."""
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=tenant_id))
    sheets = {
        d.document_id.split(".")[3]: d
        for d in catalog.documents
        if f".{sandbox}." in d.document_id
    }
    if not sheets:
        raise WorkbookApplyError(f"no documents found for sandbox {sandbox!r}")
    return Workbook(sandbox=sandbox, sheets=sheets)


def _upsert_documents_index(authority_db: Path, *, tenant_id: str, document_id: str, version_hash: str, is_anchor: bool) -> None:
    """Mirror the ingest scripts' documents-index upsert (keyed by tenant/sandbox/name)."""
    parsed = parse_canonical_document_id(document_id)
    now = int(time.time() * 1000)
    conn = sqlite3.connect(authority_db)
    try:
        conn.execute(
            "DELETE FROM documents WHERE tenant_id=? AND sandbox=? AND name=?",
            (tenant_id, parsed.sandbox, parsed.name),
        )
        conn.execute(
            "INSERT INTO documents (tenant_id, document_id, prefix, msn_id, sandbox, name, "
            "version_hash, is_anchor, origin, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'local', ?)",
            (tenant_id, document_id, parsed.prefix, parsed.msn_id, parsed.sandbox, parsed.name,
             f"sha256:{version_hash}", 1 if is_anchor else 0, now),
        )
        conn.commit()
    finally:
        conn.close()


def _verify(authority_db: Path, plan: MigrationPlan, *, tenant_id: str) -> list[str]:
    """Re-read with a fresh adapter and assert the plan's invariants."""
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    wb = load_workbook(store, tenant_id=tenant_id, sandbox=plan.sandbox)
    failures: list[str] = []

    for name, expected in plan.expectations.get("row_counts", {}).items():
        actual = len(wb.sheet(name).rows) if name in wb.sheets else -1
        if actual != expected:
            failures.append(f"{name} rows={actual} expected {expected}")

    if "anchor" in wb.sheets:
        anchor_rows = {r.datum_address: r for r in wb.sheet("anchor").rows}
        for addr, expected in plan.expectations.get("samras", {}).items():
            row = anchor_rows.get(addr)
            if row is None:
                failures.append(f"anchor {addr} missing")
                continue
            actual = len(decode_canonical_bitstream(str(row.raw[0][2])).addresses)
            if actual != expected:
                failures.append(f"{addr} decoded {actual} nodes, expected {expected}")

    report = check_step(wb)
    if not report.ok:
        failures.extend(f"rule:{h}" for h in report.hard[:10])

    # the touched docs must be persisted under their new ids
    for name, ts in plan.touched.items():
        if name in wb.sheets and wb.sheet(name).document_id != ts.new_document.document_id:
            failures.append(f"{name} id {wb.sheet(name).document_id} != planned {ts.new_document.document_id}")
    return failures


def execute_migration(
    authority_db: Path | str,
    plan: MigrationPlan,
    *,
    tenant_id: str = "fnd",
    backup: bool = True,
    backup_suffix: str = "",
) -> dict[str, Any]:
    """Apply a planned migration to the live DB: backup → write → index → verify.

    Returns a summary dict. On a verify failure (and ``backup=True``) the DB is
    restored from the backup and :class:`WorkbookApplyError` is raised.
    """
    authority_db = Path(authority_db)
    if not authority_db.exists():
        raise WorkbookApplyError(f"authority db missing: {authority_db}")
    if not plan.touched:
        return {"status": "noop", "written": [], "backup": None}

    backup_path: Path | None = None
    if backup:
        stamp = backup_suffix or time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        backup_path = authority_db.with_name(authority_db.name + f".pre-workbook-{stamp}.bak")
        if backup_path.exists():
            raise WorkbookApplyError(f"backup target already exists: {backup_path}")
        shutil.copy2(authority_db, backup_path)

    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    written: list[str] = []
    try:
        for name in plan.write_order:
            ts = plan.touched[name]
            store.replace_single_document_efficient(
                tenant_id=tenant_id, prior_document_id=ts.prior_id or None, updated_document=ts.new_document
            )
            _upsert_documents_index(
                authority_db,
                tenant_id=tenant_id,
                document_id=ts.new_document.document_id,
                version_hash=ts.new_hash,
                is_anchor=ts.new_document.is_anchor,
            )
            written.append(name)
        failures = _verify(authority_db, plan, tenant_id=tenant_id)
    except Exception as exc:
        if backup_path is not None:
            shutil.copy2(backup_path, authority_db)
        raise WorkbookApplyError(f"apply failed ({exc}); restored from backup") from exc

    if failures:
        if backup_path is not None:
            shutil.copy2(backup_path, authority_db)
        raise WorkbookApplyError(
            "post-write verify FAILED; restored from backup:\n  " + "\n  ".join(failures)
        )

    return {
        "status": "applied",
        "written": written,
        "backup": str(backup_path) if backup_path else None,
        "document_ids": {name: ts.new_document.document_id for name, ts in plan.touched.items()},
    }
