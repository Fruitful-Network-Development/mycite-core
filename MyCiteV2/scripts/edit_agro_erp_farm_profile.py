"""Farm-profile editor (write path) — rename a farm_profile feature (Phase 4).

The data-level "save" path for the farm-profile editor: retitle a family-7 feature
(the property feature ``7-3-1`` or a plot feature ``7-(3+i)-1``) by rewriting its
``rf.3-1-2`` title blob + row tail. Writes only farm_profile. Same discipline as the
ingest/builder scripts (dry-run → backup → write → verify). The interactive draw-on-map
geometry editor is a separate UI layer that mints/edits family-4 rings through this same
finalize+write path; this script proves the persistence half end-to-end.

Usage:
    python -m MyCiteV2.scripts.edit_agro_erp_farm_profile --authority-db DB \\
        --feature 7-4-1 --label new_plot_name [--dry-run]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    decode_label,
    encode_label,
    rewrite_title,
)
from MyCiteV2.packages.core.structures.samras.structure import as_text
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    SANDBOX,
    TENANT,
    _as_rows,
    _finalize,
    _upsert_documents_row,
)


@dataclasses.dataclass
class Plan:
    doc: AuthoritativeDatumDocument
    prior_id: str
    version_hash: str
    report: dict


def build(store, *, feature: str, label: str) -> Plan:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    fp = next((d for d in catalog.documents if d.canonical_name == "farm_profile" and f".{SANDBOX}." in d.document_id), None)
    if fp is None:
        raise SystemExit("live agro_erp.farm_profile not found")

    rows = _as_rows(fp)
    target = next((r for r in rows if as_text(r.datum_address) == feature), None)
    if target is None:
        raise SystemExit(f"feature {feature} not found in farm_profile")
    old_label = as_text(target.raw[1][0]) if len(target.raw) > 1 and target.raw[1] else ""
    # Rewrite the rf.3-1-2 title blob + tail echo via the shared lock-step codec
    # helper (preserves any tail siblings / record sidecar; refuses non-title rows).
    try:
        new_raw = rewrite_title(target.raw, label)
    except ValueError as exc:
        raise SystemExit(f"feature {feature}: {exc}") from exc
    new_row = AuthoritativeDatumDocumentRow(datum_address=feature, raw=new_raw)
    new_rows = [new_row if as_text(r.datum_address) == feature else r for r in rows]
    new_doc, version_hash = _finalize(dataclasses.replace(fp, rows=tuple(new_rows)), "farm_profile")

    report = {
        "feature": feature, "old_label": old_label, "new_label": label,
        "title_roundtrip": decode_label(encode_label(label)),
        "changed": new_doc.document_id != fp.document_id,
    }
    return Plan(doc=new_doc, prior_id=fp.document_id, version_hash=version_hash, report=report)


def run(*, authority_db: Path, dry_run: bool, feature: str, label: str) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    plan = build(store, feature=feature, label=label)
    print("\n============ FARM-PROFILE EDIT PLAN ============")
    for k, v in plan.report.items():
        print(f"  {k:16}: {v}")
    print("===============================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")
        return {"status": "dry_run", **plan.report}
    if not plan.report["changed"]:
        print("[skip] no change (same label)")
        return {"status": "noop", **plan.report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-fpedit-{stamp}.bak")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=plan.prior_id, updated_document=plan.doc)
    _upsert_documents_row(authority_db, name="farm_profile", document_id=plan.doc.document_id, version_hash=plan.version_hash, is_anchor=False)
    print(f"[write] farm_profile → …{plan.doc.document_id.split('.')[-1][:14]}")
    store2 = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    cat = store2.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    fp = next(d for d in cat.documents if d.canonical_name == "farm_profile" and f".{SANDBOX}." in d.document_id)
    r = next((x for x in fp.rows if as_text(x.datum_address) == feature), None)
    if r is None or as_text(r.raw[1][0]) != label:
        raise SystemExit("POST-WRITE VERIFY FAILED: label not updated")
    print("[verify] PASSED — feature relabeled")
    return {"status": "applied", "backup": str(backup), **plan.report, "document_id": plan.doc.document_id}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--feature", required=True, help="family-7 feature address, e.g. 7-4-1")
    ap.add_argument("--label", required=True, help="new label")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, dry_run=args.dry_run, feature=args.feature, label=args.label)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
