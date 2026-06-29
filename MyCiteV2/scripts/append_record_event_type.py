#!/usr/bin/env python3
"""Append an event-type reference to agro_erp record entries (invoices / contracts).

Each record entry gains a trailing ``(rf.3-1-5, event_node)`` pair pointing at an lcl
event_classification node (new taxonomy ``1-3-2``):

    invoices  (supply / procurement) → 1-3-2-1 procurement
    contracts (planting / investment) → 1-3-2-3 investment
    (sales / divestment → 1-3-2-2, added later)

To keep the value-group == pair-count invariant (these docs ARE validated on edit by
``classify_row``), the appended pair bumps each entry's value group, so entries MOVE:

    invoices  4-6-k (vg6) → 4-7-k (vg7)
    contracts 4-5-k (vg5) → 4-6-k (vg6)

Header rows (0-0-*) are untouched. Idempotent (skips if the new-prefix rows already
exist). Discipline mirrors restructure_lcl_taxonomy.py: --dry-run default; --apply takes
a timestamped .bak then self-verifies.

Usage::

    python -m MyCiteV2.scripts.append_record_event_type --authority-db DB            # dry-run
    python -m MyCiteV2.scripts.append_record_event_type --authority-db DB --apply
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    RF_LCL_ID,
    SANDBOX,
    TENANT,
    _as_rows,
    _finalize,
    _row,
    _upsert_documents_row,
)

EVENT_PROCUREMENT = "1-3-2-1"
EVENT_INVESTMENT = "1-3-2-3"

# (doc name, old data-row prefix, new data-row prefix, event lcl node)
SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("invoices", "4-6-", "4-7-", EVENT_PROCUREMENT),
    ("contracts", "4-5-", "4-6-", EVENT_INVESTMENT),
)


def _has_event(head: list, event_node: str) -> bool:
    return any(
        str(head[i]).lower() == RF_LCL_ID and str(head[i + 1]) == event_node
        for i in range(1, len(head) - 1, 2)
    )


def _migrate_doc(doc: AuthoritativeDatumDocument, *, old_prefix: str, new_prefix: str, event_node: str):
    """Return (new_doc_or_None, count). None when nothing to do (idempotent)."""
    rows = _as_rows(doc)
    # already migrated? (new-prefix data rows present)
    if any(r.datum_address.startswith(new_prefix) for r in rows):
        return None, 0
    kept = [r for r in rows if not r.datum_address.startswith(old_prefix)]
    moved: list = []
    for r in rows:
        if not r.datum_address.startswith(old_prefix):
            continue
        k = r.datum_address[len(old_prefix):]
        new_addr = f"{new_prefix}{k}"
        head = list(r.raw[0])
        head[0] = new_addr
        if not _has_event(head, event_node):
            head = [*head, RF_LCL_ID, event_node]
        moved.append(_row(new_addr, [head, *list(r.raw)[1:]]))
    return _finalize(dataclasses.replace(doc, rows=tuple([*kept, *moved])), doc.canonical_name or ""), len(moved)


def run(*, authority_db: Path, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}

    plan: list[tuple[str, AuthoritativeDatumDocument, str, str, int]] = []  # name, newdoc, prior_id, hash, count
    report: dict = {}
    for name, old_p, new_p, event in SPECS:
        doc = live.get(name)
        if doc is None:
            report[name] = "missing"
            continue
        result, count = _migrate_doc(doc, old_prefix=old_p, new_prefix=new_p, event_node=event)
        if result is None:
            report[name] = "already migrated (skip)"
            continue
        new_doc, h = result
        plan.append((name, new_doc, doc.document_id, h, count))
        report[name] = f"{count} entries {old_p}*→{new_p}* + event {event}"

    print("\n===== APPEND RECORD EVENT-TYPE =====")
    for spec in SPECS:
        print(f"  {spec[0]:11} {report.get(spec[0])}")
    print("====================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")
        return {"status": "dry_run", **report}
    if not plan:
        return {"status": "noop", **report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-eventtype-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    for name, new_doc, prior_id, h, _count in plan:
        store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=prior_id, updated_document=new_doc)
        _upsert_documents_row(authority_db, name=name, document_id=new_doc.document_id, version_hash=h, is_anchor=False)
        print(f"[write] {name} → …{new_doc.document_id.split('.')[-1][:14]}")
    _verify(authority_db)
    return {"status": "applied", "backup": str(backup), **report,
            "document_ids": {name: nd.document_id for name, nd, _, _, _ in plan}}


def _verify(authority_db: Path) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    failures: list[str] = []
    for name, old_p, new_p, event in SPECS:
        doc = live.get(name)
        if doc is None:
            continue
        for r in _as_rows(doc):
            if r.datum_address.startswith(old_p):
                failures.append(f"{name}: stale {r.datum_address} not moved")
            if r.datum_address.startswith(new_p):
                head = r.raw[0]
                if not _has_event(head, event):
                    failures.append(f"{name} {r.datum_address}: missing event {event}")
    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures[:20]))
    print("[verify] PASSED — record entries moved + event-type appended")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="write (default is a dry-run)")
    args = ap.parse_args(argv)
    print(json.dumps(run(authority_db=args.authority_db, dry_run=not args.apply), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
